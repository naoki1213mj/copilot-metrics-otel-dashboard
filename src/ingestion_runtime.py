"""Azure Functions から利用する ingestion ランタイム。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError
from azure.cosmos import CosmosClient, PartitionKey, exceptions as cosmos_exceptions
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient, ContentSettings
from dotenv import load_dotenv
import httpx
import polars as pl

from src.fetch_metrics import (
    RAW_DATA_DIR,
    RawMetricsBundle,
    dataframe_to_ndjson_bytes,
    fetch_metrics_bundle,
    generate_report_days,
    parse_report_window_days,
    write_raw_metrics_bundle,
)
from src.generate_mock import generate_dates, generate_mock_bundle, rows_to_ndjson_bytes
from src.transform import (
    DashboardSnapshotBundle,
    PUBLIC_DATA_DIR,
    build_dashboard_snapshot_bundle,
    serialize_json_bytes,
    write_dashboard_snapshot_bundle,
)

logger = logging.getLogger(__name__)

SourceType = Literal["github", "mock"]

DEFAULT_TIMER_SCHEDULE = "0 15 2 * * *"
DEFAULT_RAW_CONTAINER_NAME = "raw-metrics"
DEFAULT_CURATED_CONTAINER_NAME = "curated-metrics"
DEFAULT_DASHBOARD_CONTAINER_NAME = "dashboard-data"
DEFAULT_COSMOS_DATABASE_NAME = "copilot-metrics"
DEFAULT_COSMOS_METRICS_CONTAINER_NAME = "usageMetrics"
DEFAULT_COSMOS_INGESTION_RUNS_CONTAINER_NAME = "ingestionRuns"
DEFAULT_COSMOS_DASHBOARD_VIEWS_CONTAINER_NAME = "dashboardViews"
DEFAULT_MOCK_SEED = 42
RAW_FILE_NAMES = {
    "org_metrics": "org_metrics.ndjson",
    "user_metrics": "user_metrics.ndjson",
}
SNAPSHOT_FILE_NAMES = {
    "daily_summary": "daily_summary.json",
    "user_summary": "user_summary.json",
    "user_daily_summary": "user_daily_summary.json",
    "language_summary": "language_summary.json",
}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
ALLOWED_DASHBOARD_SNAPSHOT_FILES = frozenset(SNAPSHOT_FILE_NAMES.values())


@dataclass(slots=True)
class IngestionSettings:
    """ingestion 実行に必要な設定。"""

    source: SourceType
    report_window_days: int
    github_token: str | None
    github_org: str | None
    blob_connection_string: str | None
    blob_service_endpoint: str | None
    raw_container_name: str
    curated_container_name: str
    dashboard_container_name: str
    cosmos_connection_string: str | None
    cosmos_endpoint: str | None
    cosmos_database_name: str
    cosmos_metrics_container_name: str
    cosmos_ingestion_runs_container_name: str
    cosmos_dashboard_views_container_name: str
    raw_output_dir: Path
    snapshot_output_dir: Path
    timer_schedule: str
    write_local_outputs: bool
    mock_seed: int


class BlobArtifactStore:
    """Blob Storage へ raw/snapshot を保存する。"""

    def __init__(self, container_client: ContainerClient) -> None:
        self._container_client = container_client
        self._container_ready = False

    def upload_artifact(
        self,
        blob_name: str,
        content: bytes,
        *,
        content_type: str,
    ) -> dict[str, object]:
        """バイト列を Blob Storage に保存する。"""
        self._ensure_container()
        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            content,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return {
            "blobName": blob_name,
            "contentType": content_type,
            "sizeBytes": len(content),
            "url": blob_client.url,
        }

    def download_artifact(self, blob_name: str) -> bytes:
        """指定された blob を読み込む。"""
        blob_client = self._container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()

    def _ensure_container(self) -> None:
        """必要に応じてコンテナーを作成する。"""
        if self._container_ready:
            return
        try:
            self._container_client.create_container()
        except ResourceExistsError:
            pass
        self._container_ready = True


class CosmosMetadataStore:
    """Cosmos DB へ run metadata を保存する。"""

    def __init__(
        self,
        connection: str,
        database_name: str,
        container_name: str,
        *,
        credential: DefaultAzureCredential | None = None,
    ) -> None:
        self._credential = credential
        if credential is None:
            self._client = CosmosClient.from_connection_string(connection)
        else:
            self._client = CosmosClient(connection, credential=credential)
        database = self._client.create_database_if_not_exists(id=database_name)
        self._container = database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/runType"),
        )

    def upsert_document(self, document: dict[str, object]) -> None:
        """ドキュメントを upsert する。"""
        self._container.upsert_item(document)

    def read_latest_state(self, source: SourceType) -> dict[str, object] | None:
        """最新状態ドキュメントを取得する。"""
        try:
            return self._container.read_item(
                item=f"latest:{source}",
                partition_key=source,
            )
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    def close(self) -> None:
        """内部クライアントを閉じる。"""
        close_resource(self._client)
        close_resource(self._credential)


def parse_source(raw_value: str | None) -> SourceType:
    """データソース設定を検証して返す。"""
    normalized = (raw_value or "github").strip().lower()
    if normalized in {"github", "mock"}:
        return normalized
    raise ValueError("COPILOT_METRICS_SOURCE は github か mock を指定してください。")


def parse_bool_value(raw_value: str | None, *, default: bool = False) -> bool:
    """真偽値の環境変数や HTTP パラメーターを解釈する。"""
    if raw_value is None or raw_value.strip() == "":
        return default
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"真偽値として解釈できません: {raw_value}")


def parse_int_env(env_name: str, default: int) -> int:
    """整数環境変数を解釈する。"""
    raw_value = os.getenv(env_name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} は整数で指定してください: {raw_value}") from exc


def close_resource(resource: object | None) -> None:
    """close() を持つ Azure SDK クライアントを安全に閉じる。"""
    close_method = getattr(resource, "close", None)
    if callable(close_method):
        close_method()


def create_default_azure_credential() -> DefaultAzureCredential:
    """Azure SDK 用の既定資格情報を生成する。"""
    return DefaultAzureCredential()


def is_blob_remote_persistence_configured(settings: IngestionSettings) -> bool:
    """Blob Storage の接続先が設定済みかを返す。"""
    return bool(settings.blob_connection_string or settings.blob_service_endpoint)


def is_cosmos_remote_persistence_configured(settings: IngestionSettings) -> bool:
    """Cosmos DB の接続先が設定済みかを返す。"""
    return bool(settings.cosmos_connection_string or settings.cosmos_endpoint)


def create_blob_service_client(
    settings: IngestionSettings,
) -> tuple[BlobServiceClient, DefaultAzureCredential | None]:
    """設定に応じた BlobServiceClient を生成する。"""
    if settings.blob_connection_string:
        return BlobServiceClient.from_connection_string(settings.blob_connection_string), None

    if settings.blob_service_endpoint:
        credential = create_default_azure_credential()
        return (
            BlobServiceClient(
                account_url=settings.blob_service_endpoint,
                credential=credential,
            ),
            credential,
        )

    raise ValueError(
        "Blob Storage への保存には AzureWebJobsStorage / "
        "COPILOT_METRICS_STORAGE_CONNECTION_STRING、または "
        "METRICS_STORAGE_BLOB_ENDPOINT を設定してください。"
    )


def create_cosmos_client(
    settings: IngestionSettings,
) -> tuple[CosmosClient, DefaultAzureCredential | None]:
    """設定に応じた CosmosClient を生成する。"""
    if settings.cosmos_connection_string:
        return CosmosClient.from_connection_string(settings.cosmos_connection_string), None

    if settings.cosmos_endpoint:
        credential = create_default_azure_credential()
        return CosmosClient(settings.cosmos_endpoint, credential=credential), credential

    raise ValueError(
        "Cosmos DB への保存には COSMOSDB_CONNECTION_STRING または "
        "AZURE_COSMOS_ENDPOINT を設定してください。"
    )


def create_cosmos_metadata_store(
    settings: IngestionSettings,
    container_name: str,
) -> CosmosMetadataStore:
    """run metadata 用の Cosmos DB ストアを生成する。"""
    if settings.cosmos_connection_string:
        return CosmosMetadataStore(
            settings.cosmos_connection_string,
            settings.cosmos_database_name,
            container_name,
        )

    if settings.cosmos_endpoint:
        return CosmosMetadataStore(
            settings.cosmos_endpoint,
            settings.cosmos_database_name,
            container_name,
            credential=create_default_azure_credential(),
        )

    raise ValueError(
        "Cosmos DB への保存には COSMOSDB_CONNECTION_STRING または "
        "AZURE_COSMOS_ENDPOINT を設定してください。"
    )


def load_ingestion_settings(*, require_remote_persistence: bool) -> IngestionSettings:
    """環境変数から ingestion 設定を組み立てる。"""
    load_dotenv()
    legacy_blob_container_name = os.getenv("INGESTION_BLOB_CONTAINER_NAME")
    legacy_cosmos_container_name = os.getenv("INGESTION_COSMOS_CONTAINER_NAME")
    settings = IngestionSettings(
        source=parse_source(os.getenv("COPILOT_METRICS_SOURCE")),
        report_window_days=parse_report_window_days(os.getenv("COPILOT_METRICS_DAYS")),
        github_token=os.getenv("GITHUB_TOKEN"),
        github_org=os.getenv("GITHUB_ORG"),
        blob_connection_string=(
            os.getenv("COPILOT_METRICS_STORAGE_CONNECTION_STRING")
            or os.getenv("AzureWebJobsStorage")
        ),
        blob_service_endpoint=(
            os.getenv("METRICS_STORAGE_BLOB_ENDPOINT")
            or os.getenv("AzureWebJobsStorage__blobServiceUri")
        ),
        raw_container_name=(
            os.getenv("METRICS_RAW_CONTAINER")
            or legacy_blob_container_name
            or DEFAULT_RAW_CONTAINER_NAME
        ),
        curated_container_name=(
            os.getenv("METRICS_CURATED_CONTAINER")
            or legacy_blob_container_name
            or DEFAULT_CURATED_CONTAINER_NAME
        ),
        dashboard_container_name=(
            os.getenv("METRICS_DASHBOARD_CONTAINER")
            or legacy_blob_container_name
            or DEFAULT_DASHBOARD_CONTAINER_NAME
        ),
        cosmos_connection_string=os.getenv("COSMOSDB_CONNECTION_STRING"),
        cosmos_endpoint=os.getenv("AZURE_COSMOS_ENDPOINT") or os.getenv("COSMOS_ENDPOINT"),
        cosmos_database_name=os.getenv(
            "AZURE_COSMOS_DATABASE_NAME",
            os.getenv("INGESTION_COSMOS_DATABASE_NAME", DEFAULT_COSMOS_DATABASE_NAME),
        ),
        cosmos_metrics_container_name=os.getenv(
            "AZURE_COSMOS_METRICS_CONTAINER_NAME",
            DEFAULT_COSMOS_METRICS_CONTAINER_NAME,
        ),
        cosmos_ingestion_runs_container_name=os.getenv(
            "AZURE_COSMOS_INGESTION_RUNS_CONTAINER_NAME",
            legacy_cosmos_container_name or DEFAULT_COSMOS_INGESTION_RUNS_CONTAINER_NAME,
        ),
        cosmos_dashboard_views_container_name=os.getenv(
            "AZURE_COSMOS_DASHBOARD_VIEWS_CONTAINER_NAME",
            DEFAULT_COSMOS_DASHBOARD_VIEWS_CONTAINER_NAME,
        ),
        raw_output_dir=Path(os.getenv("INGESTION_RAW_OUTPUT_DIR", str(RAW_DATA_DIR))),
        snapshot_output_dir=Path(
            os.getenv("INGESTION_SNAPSHOT_OUTPUT_DIR", str(PUBLIC_DATA_DIR))
        ),
        timer_schedule=os.getenv("INGESTION_TIMER_SCHEDULE", DEFAULT_TIMER_SCHEDULE),
        write_local_outputs=parse_bool_value(
            os.getenv("INGESTION_WRITE_LOCAL_OUTPUTS"),
            default=False,
        ),
        mock_seed=parse_int_env("INGESTION_MOCK_SEED", DEFAULT_MOCK_SEED),
    )
    validate_ingestion_settings(
        settings,
        require_remote_persistence=require_remote_persistence,
    )
    return settings


def validate_ingestion_settings(
    settings: IngestionSettings,
    *,
    require_remote_persistence: bool,
) -> None:
    """ingestion 設定が実行可能かを検証する。"""
    if settings.source == "github" and (
        not settings.github_token or not settings.github_org
    ):
        raise ValueError(
            "github ソースを使うには GITHUB_TOKEN と GITHUB_ORG を設定してください。"
        )
    if require_remote_persistence and not is_blob_remote_persistence_configured(settings):
        raise ValueError(
            "Blob Storage への保存には AzureWebJobsStorage / "
            "COPILOT_METRICS_STORAGE_CONNECTION_STRING、または "
            "METRICS_STORAGE_BLOB_ENDPOINT を設定してください。"
        )
    if require_remote_persistence and not is_cosmos_remote_persistence_configured(settings):
        raise ValueError(
            "Cosmos DB への保存には COSMOSDB_CONNECTION_STRING または "
            "AZURE_COSMOS_ENDPOINT を設定してください。"
        )


def get_organization_key(settings: IngestionSettings) -> str:
    """Cosmos DB のパーティションキーに使う organization 名を返す。"""
    return settings.github_org or "mock"


def upsert_cosmos_documents(
    settings: IngestionSettings,
    container_name: str,
    partition_key_path: str,
    documents: list[dict[str, object]],
) -> None:
    """任意の Cosmos DB コンテナーへドキュメントを upsert する。"""
    client, credential = create_cosmos_client(settings)
    try:
        database = client.create_database_if_not_exists(id=settings.cosmos_database_name)
        container = database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path=partition_key_path),
        )
        for document in documents:
            container.upsert_item(document)
    finally:
        close_resource(client)
        close_resource(credential)


def build_dashboard_view_documents(
    settings: IngestionSettings,
    run_document: dict[str, object],
    snapshot_bundle: DashboardSnapshotBundle,
) -> list[dict[str, object]]:
    """dashboardViews コンテナー向けの最新・履歴ドキュメントを組み立てる。"""
    organization = get_organization_key(settings)
    completed_at = run_document["completedAt"]
    documents: list[dict[str, object]] = []
    for view_type, items in {
        "daily_summary": snapshot_bundle.daily_summary,
        "user_summary": snapshot_bundle.user_summary,
        "user_daily_summary": snapshot_bundle.user_daily_summary,
        "language_summary": snapshot_bundle.language_summary,
    }.items():
        base_document = {
            "documentType": "dashboard-view",
            "organization": organization,
            "runId": run_document["id"],
            "source": run_document["source"],
            "updatedAt": completed_at,
            "viewType": view_type,
            "items": items,
        }
        documents.append(
            {
                "id": f"latest:{view_type}",
                **base_document,
            }
        )
        documents.append(
            {
                "id": f"{run_document['id']}:{view_type}",
                **base_document,
            }
        )
    return documents


def build_metrics_documents(
    settings: IngestionSettings,
    run_document: dict[str, object],
) -> list[dict[str, object]]:
    """usageMetrics コンテナー向けの run サマリーを組み立てる。"""
    organization = get_organization_key(settings)
    return [
        {
            "id": f"run:{run_document['id']}",
            "documentType": "usage-metrics-run",
            "organization": organization,
            "source": run_document["source"],
            "runId": run_document["id"],
            "trigger": run_document["trigger"],
            "startedAt": run_document["startedAt"],
            "completedAt": run_document["completedAt"],
            "status": run_document["status"],
            "rawRecords": run_document.get("rawRecords", {}),
            "snapshotRecords": run_document.get("snapshotRecords", {}),
            "rawBlobs": run_document.get("rawBlobs", {}),
            "snapshotBlobs": run_document.get("snapshotBlobs", {}),
        }
    ]


def persist_projection_documents(
    settings: IngestionSettings,
    run_document: dict[str, object],
    snapshot_bundle: DashboardSnapshotBundle,
) -> None:
    """dashboard views と metrics の補助ドキュメントを Cosmos DB へ保存する。"""
    if not is_cosmos_remote_persistence_configured(settings):
        return
    upsert_cosmos_documents(
        settings,
        settings.cosmos_dashboard_views_container_name,
        "/viewType",
        build_dashboard_view_documents(settings, run_document, snapshot_bundle),
    )
    upsert_cosmos_documents(
        settings,
        settings.cosmos_metrics_container_name,
        "/organization",
        build_metrics_documents(settings, run_document),
    )


def isoformat_utc(value: datetime) -> str:
    """UTC の ISO 8601 文字列へ正規化する。"""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def build_run_id(started_at: datetime, invocation_id: str | None) -> str:
    """実行 ID を生成する。"""
    suffix = (invocation_id or uuid4().hex)[:8]
    return f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-{suffix}"


def get_raw_record_counts(bundle: RawMetricsBundle) -> dict[str, int]:
    """raw メトリクスの行数を返す。"""
    return {
        "org_metrics": len(bundle.org_metrics),
        "user_metrics": len(bundle.user_metrics),
    }


def get_snapshot_record_counts(bundle: DashboardSnapshotBundle) -> dict[str, int]:
    """スナップショットの件数を返す。"""
    return {
        "daily_summary": len(bundle.daily_summary),
        "user_summary": len(bundle.user_summary),
        "user_daily_summary": len(bundle.user_daily_summary),
        "language_summary": len(bundle.language_summary),
    }


def build_snapshot_bytes(bundle: DashboardSnapshotBundle) -> dict[str, bytes]:
    """スナップショット JSON をバイト列に変換する。"""
    return {
        "daily_summary": serialize_json_bytes(bundle.daily_summary),
        "user_summary": serialize_json_bytes(bundle.user_summary),
        "user_daily_summary": serialize_json_bytes(bundle.user_daily_summary),
        "language_summary": serialize_json_bytes(bundle.language_summary),
    }


def build_raw_payload(
    settings: IngestionSettings,
) -> tuple[RawMetricsBundle, dict[str, bytes]]:
    """ソースに応じて raw データと NDJSON バイト列を用意する。"""
    if settings.source == "mock":
        mock_days = generate_dates()[-settings.report_window_days :]
        org_rows, user_rows = generate_mock_bundle(
            seed=settings.mock_seed,
            days=mock_days,
        )
        bundle = RawMetricsBundle(
            org_metrics=pl.DataFrame(org_rows),
            user_metrics=pl.DataFrame(user_rows),
        )
        return bundle, {
            "org_metrics": rows_to_ndjson_bytes(org_rows),
            "user_metrics": rows_to_ndjson_bytes(user_rows),
        }

    if not settings.github_token or not settings.github_org:
        raise ValueError(
            "github ソースを使うには GITHUB_TOKEN と GITHUB_ORG を設定してください。"
        )

    report_days = generate_report_days(settings.report_window_days)
    bundle = fetch_metrics_bundle(
        settings.github_token,
        settings.github_org,
        report_days,
    )
    return bundle, {
        "org_metrics": dataframe_to_ndjson_bytes(bundle.org_metrics),
        "user_metrics": dataframe_to_ndjson_bytes(bundle.user_metrics),
    }


def upload_artifacts_to_blob(
    settings: IngestionSettings,
    run_id: str,
    raw_bytes: dict[str, bytes],
    snapshot_bytes: dict[str, bytes],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    """Blob Storage へ raw/snapshot を保存する。"""
    if not is_blob_remote_persistence_configured(settings):
        raise ValueError(
            "Blob Storage への保存には AzureWebJobsStorage / "
            "COPILOT_METRICS_STORAGE_CONNECTION_STRING、または "
            "METRICS_STORAGE_BLOB_ENDPOINT を設定してください。"
        )

    service_client, credential = create_blob_service_client(settings)
    raw_store = BlobArtifactStore(service_client.get_container_client(settings.raw_container_name))
    curated_store = BlobArtifactStore(
        service_client.get_container_client(settings.curated_container_name)
    )
    dashboard_store = BlobArtifactStore(
        service_client.get_container_client(settings.dashboard_container_name)
    )
    try:
        raw_artifacts: dict[str, dict[str, object]] = {}
        for artifact_name, content in raw_bytes.items():
            filename = RAW_FILE_NAMES[artifact_name]
            raw_artifacts[artifact_name] = {
                "history": raw_store.upload_artifact(
                    f"{settings.source}/runs/{run_id}/{filename}",
                    content,
                    content_type="application/x-ndjson",
                ),
                "latest": raw_store.upload_artifact(
                    f"{settings.source}/latest/{filename}",
                    content,
                    content_type="application/x-ndjson",
                ),
            }

        snapshot_artifacts: dict[str, dict[str, object]] = {}
        for artifact_name, content in snapshot_bytes.items():
            filename = SNAPSHOT_FILE_NAMES[artifact_name]
            snapshot_artifacts[artifact_name] = {
                "history": curated_store.upload_artifact(
                    f"{settings.source}/runs/{run_id}/{filename}",
                    content,
                    content_type="application/json",
                ),
                "latest": dashboard_store.upload_artifact(
                    f"latest/{filename}",
                    content,
                    content_type="application/json",
                ),
            }

        return raw_artifacts, snapshot_artifacts
    finally:
        close_resource(service_client)
        close_resource(credential)


def write_local_outputs(
    settings: IngestionSettings,
    raw_bundle: RawMetricsBundle,
    snapshot_bundle: DashboardSnapshotBundle,
) -> dict[str, str]:
    """既存のローカルワークフロー互換でファイルを書き出す。"""
    raw_paths = write_raw_metrics_bundle(raw_bundle, settings.raw_output_dir)
    snapshot_paths = write_dashboard_snapshot_bundle(
        snapshot_bundle,
        settings.snapshot_output_dir,
    )
    return {
        **{name: str(path) for name, path in raw_paths.items()},
        **{name: str(path) for name, path in snapshot_paths.items()},
    }


def build_latest_state_document(run_document: dict[str, object]) -> dict[str, object]:
    """最新実行状態ドキュメントを組み立てる。"""
    return {
        "id": f"latest:{run_document['source']}",
        "documentType": "ingestion-latest",
        "runType": run_document["source"],
        "source": run_document["source"],
        "runId": run_document["id"],
        "status": run_document["status"],
        "trigger": run_document["trigger"],
        "startedAt": run_document["startedAt"],
        "completedAt": run_document.get("completedAt"),
        "updatedAt": run_document.get("completedAt") or run_document["startedAt"],
        "reportWindowDays": run_document["reportWindowDays"],
        "org": run_document.get("org"),
        "rawRecords": run_document.get("rawRecords", {}),
        "snapshotRecords": run_document.get("snapshotRecords", {}),
        "rawBlobs": run_document.get("rawBlobs", {}),
        "snapshotBlobs": run_document.get("snapshotBlobs", {}),
        "error": run_document.get("error"),
    }


def persist_run_state(
    metadata_store: CosmosMetadataStore | None,
    run_document: dict[str, object],
) -> None:
    """run ドキュメントと最新状態ドキュメントを保存する。"""
    if metadata_store is None:
        return
    metadata_store.upsert_document(run_document)
    metadata_store.upsert_document(build_latest_state_document(run_document))


def run_ingestion(
    *,
    trigger: str,
    source_override: SourceType | None = None,
    write_local_outputs_override: bool | None = None,
    invocation_id: str | None = None,
    require_remote_persistence: bool = True,
) -> dict[str, object]:
    """ingestion パイプラインを実行する。"""
    settings = load_ingestion_settings(
        require_remote_persistence=require_remote_persistence,
    )
    if source_override is not None:
        settings = replace(settings, source=source_override)
    if write_local_outputs_override is not None:
        settings = replace(
            settings,
            write_local_outputs=write_local_outputs_override,
        )
    validate_ingestion_settings(
        settings,
        require_remote_persistence=require_remote_persistence,
    )

    started_at = datetime.now(timezone.utc)
    run_id = build_run_id(started_at, invocation_id)
    run_document: dict[str, object] = {
        "id": run_id,
        "documentType": "ingestion-run",
        "runType": settings.source,
        "source": settings.source,
        "status": "running",
        "trigger": trigger,
        "startedAt": isoformat_utc(started_at),
        "reportWindowDays": settings.report_window_days,
        "org": settings.github_org,
        "invocationId": invocation_id,
    }
    logger.info(
        "Ingestion を開始します: run_id=%s source=%s trigger=%s",
        run_id,
        settings.source,
        trigger,
    )

    metadata_store: CosmosMetadataStore | None = None
    try:
        if is_cosmos_remote_persistence_configured(settings):
            metadata_store = create_cosmos_metadata_store(
                settings,
                settings.cosmos_ingestion_runs_container_name,
            )
            persist_run_state(metadata_store, run_document)

        raw_bundle, raw_bytes = build_raw_payload(settings)
        snapshot_bundle = build_dashboard_snapshot_bundle(
            raw_bundle.org_metrics,
            raw_bundle.user_metrics,
        )
        snapshot_bytes = build_snapshot_bytes(snapshot_bundle)

        run_document["rawRecords"] = get_raw_record_counts(raw_bundle)
        run_document["snapshotRecords"] = get_snapshot_record_counts(snapshot_bundle)

        local_outputs: dict[str, str] = {}
        if settings.write_local_outputs:
            local_outputs = write_local_outputs(
                settings,
                raw_bundle,
                snapshot_bundle,
            )
            run_document["localOutputs"] = local_outputs

        raw_blobs: dict[str, dict[str, object]] = {}
        snapshot_blobs: dict[str, dict[str, object]] = {}
        if is_blob_remote_persistence_configured(settings):
            raw_blobs, snapshot_blobs = upload_artifacts_to_blob(
                settings,
                run_id,
                raw_bytes,
                snapshot_bytes,
            )
        elif require_remote_persistence:
            raise ValueError(
                "Blob Storage への保存には AzureWebJobsStorage / "
                "COPILOT_METRICS_STORAGE_CONNECTION_STRING、または "
                "METRICS_STORAGE_BLOB_ENDPOINT を設定してください。"
            )

        completed_at = datetime.now(timezone.utc)
        run_document.update(
            {
                "status": "succeeded",
                "completedAt": isoformat_utc(completed_at),
                "rawBlobs": raw_blobs,
                "snapshotBlobs": snapshot_blobs,
            }
        )
        persist_projection_documents(settings, run_document, snapshot_bundle)
        persist_run_state(metadata_store, run_document)
        logger.info("Ingestion が完了しました: run_id=%s", run_id)
        return run_document
    except (
        ValueError,
        OSError,
        httpx.HTTPError,
        pl.exceptions.PolarsError,
        AzureError,
        cosmos_exceptions.CosmosHttpResponseError,
    ) as exc:
        completed_at = datetime.now(timezone.utc)
        run_document.update(
            {
                "status": "failed",
                "completedAt": isoformat_utc(completed_at),
                "error": str(exc),
            }
        )
        if metadata_store is not None:
            try:
                persist_run_state(metadata_store, run_document)
            except cosmos_exceptions.CosmosHttpResponseError as persist_exc:
                logger.warning(
                    "Cosmos DB に失敗状態を書き込めませんでした: %s",
                    persist_exc,
                )
        logger.exception("Ingestion に失敗しました: run_id=%s", run_id)
        raise
    finally:
        if metadata_store is not None:
            metadata_store.close()


def get_ingestion_status() -> dict[str, object]:
    """現在の設定と最新実行状態を返す。"""
    try:
        settings = load_ingestion_settings(require_remote_persistence=False)
    except ValueError as exc:
        return {
            "status": "configuration-error",
            "error": str(exc),
        }

    status_payload: dict[str, object] = {
        "status": "ready",
        "source": settings.source,
        "reportWindowDays": settings.report_window_days,
        "timerSchedule": settings.timer_schedule,
        "writeLocalOutputs": settings.write_local_outputs,
        "githubConfigured": settings.source == "mock"
        or bool(settings.github_token and settings.github_org),
        "remotePersistenceConfigured": bool(
            is_blob_remote_persistence_configured(settings)
            and is_cosmos_remote_persistence_configured(settings)
        ),
        "rawContainerName": settings.raw_container_name,
        "curatedContainerName": settings.curated_container_name,
        "dashboardContainerName": settings.dashboard_container_name,
        "cosmosDatabaseName": settings.cosmos_database_name,
        "cosmosMetricsContainerName": settings.cosmos_metrics_container_name,
        "cosmosIngestionRunsContainerName": settings.cosmos_ingestion_runs_container_name,
        "cosmosDashboardViewsContainerName": settings.cosmos_dashboard_views_container_name,
    }

    if not is_cosmos_remote_persistence_configured(settings):
        return status_payload

    metadata_store: CosmosMetadataStore | None = None
    try:
        metadata_store = create_cosmos_metadata_store(
            settings,
            settings.cosmos_ingestion_runs_container_name,
        )
        latest_run = metadata_store.read_latest_state(settings.source)
    except (AzureError, cosmos_exceptions.CosmosHttpResponseError) as exc:
        status_payload["status"] = "degraded"
        status_payload["latestRunError"] = str(exc)
        return status_payload
    finally:
        if metadata_store is not None:
            metadata_store.close()

    if latest_run is not None:
        status_payload["latestRun"] = latest_run
    return status_payload


def load_dashboard_snapshot_bytes(file_name: str) -> bytes:
    """dashboard 用の最新 JSON スナップショットを取得する。"""
    if file_name not in ALLOWED_DASHBOARD_SNAPSHOT_FILES:
        raise ValueError(f"未対応のスナップショットです: {file_name}")

    settings = load_ingestion_settings(require_remote_persistence=False)
    if is_blob_remote_persistence_configured(settings):
        service_client, credential = create_blob_service_client(settings)
        dashboard_store = BlobArtifactStore(
            service_client.get_container_client(settings.dashboard_container_name)
        )
        try:
            return dashboard_store.download_artifact(f"latest/{file_name}")
        except ResourceNotFoundError:
            pass
        finally:
            close_resource(service_client)
            close_resource(credential)

    local_path = settings.snapshot_output_dir / file_name
    if local_path.exists():
        return local_path.read_bytes()

    raise FileNotFoundError(f"{file_name} がまだ生成されていません。")


def json_response_body(payload: dict[str, object]) -> str:
    """HTTP 応答向けの JSON 文字列を返す。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)
