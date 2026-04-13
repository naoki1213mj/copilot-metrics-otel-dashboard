"""ingestion_runtime モジュールのテスト。"""

from __future__ import annotations

import copy
from pathlib import Path

from azure.core.exceptions import AzureError
import pytest

from src.ingestion_runtime import (
    IngestionSettings,
    get_ingestion_status,
    load_ingestion_settings,
    load_dashboard_snapshot_bytes,
    run_ingestion,
)


class FakeCosmosMetadataStore:
    """Cosmos DB 書き込みをメモリーに記録するテストダブル。"""

    instances: list["FakeCosmosMetadataStore"] = []
    latest_by_source: dict[str, dict[str, object]] = {}

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.documents: list[dict[str, object]] = []
        self.closed = False
        self.__class__.instances.append(self)

    def upsert_document(self, document: dict[str, object]) -> None:
        stored = copy.deepcopy(document)
        self.documents.append(stored)
        if str(stored["id"]).startswith("latest:"):
            self.__class__.latest_by_source[str(stored["source"])] = stored

    def read_latest_state(self, source: str) -> dict[str, object] | None:
        latest = self.__class__.latest_by_source.get(source)
        return copy.deepcopy(latest) if latest is not None else None

    def close(self) -> None:
        self.closed = True

    @classmethod
    def reset(cls) -> None:
        cls.instances.clear()
        cls.latest_by_source.clear()


class FakeDownloadStream:
    """Blob download の読み出し結果を返すダブル。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def readall(self) -> bytes:
        return self._payload


class FakeBlobClient:
    """BlobClient 相当の最小ダブル。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def download_blob(self) -> FakeDownloadStream:
        return FakeDownloadStream(self._payload)


class FakeContainerClient:
    """ContainerClient 相当の最小ダブル。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def get_blob_client(self, _blob_name: str) -> FakeBlobClient:
        return FakeBlobClient(self._payload)


class FakeBlobServiceClient:
    """BlobServiceClient 相当の最小ダブル。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def get_container_client(self, _container_name: str) -> FakeContainerClient:
        return FakeContainerClient(self._payload)

    def close(self) -> None:
        return None


def clear_ingestion_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """ingestion 関連の環境変数をテスト用にクリアする。"""
    for env_name in [
        "GITHUB_TOKEN",
        "GITHUB_ORG",
        "COPILOT_METRICS_SOURCE",
        "COPILOT_METRICS_DAYS",
        "COPILOT_METRICS_STORAGE_CONNECTION_STRING",
        "AzureWebJobsStorage",
        "METRICS_STORAGE_BLOB_ENDPOINT",
        "AzureWebJobsStorage__blobServiceUri",
        "COSMOSDB_CONNECTION_STRING",
        "AZURE_COSMOS_ENDPOINT",
        "COSMOS_ENDPOINT",
        "INGESTION_RAW_OUTPUT_DIR",
        "INGESTION_SNAPSHOT_OUTPUT_DIR",
    ]:
        monkeypatch.delenv(env_name, raising=False)


def make_settings(tmp_path: Path, *, write_local_outputs: bool) -> IngestionSettings:
    """テスト用の ingestion 設定を返す。"""
    return IngestionSettings(
        source="mock",
        report_window_days=3,
        github_token=None,
        github_org=None,
        blob_connection_string="UseDevelopmentStorage=true",
        blob_service_endpoint=None,
        raw_container_name="raw-metrics",
        curated_container_name="curated-metrics",
        dashboard_container_name="dashboard-data",
        cosmos_connection_string="AccountEndpoint=https://example.com:443/;AccountKey=test-key;",
        cosmos_endpoint=None,
        cosmos_database_name="copilot-metrics",
        cosmos_metrics_container_name="usageMetrics",
        cosmos_ingestion_runs_container_name="ingestionRuns",
        cosmos_dashboard_views_container_name="dashboardViews",
        raw_output_dir=tmp_path / "raw",
        snapshot_output_dir=tmp_path / "snapshots",
        timer_schedule="0 15 2 * * *",
        write_local_outputs=write_local_outputs,
        mock_seed=42,
    )


def test_run_ingestion_with_mock_persists_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """mock ソースでも Blob/Cosmos まで含めて 1 回分の実行情報を返す。"""
    FakeCosmosMetadataStore.reset()
    settings = make_settings(tmp_path, write_local_outputs=True)
    uploaded: list[tuple[str, dict[str, bytes], dict[str, bytes]]] = []

    def fake_upload(
        current_settings: IngestionSettings,
        run_id: str,
        raw_bytes: dict[str, bytes],
        snapshot_bytes: dict[str, bytes],
    ) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        uploaded.append((run_id, raw_bytes, snapshot_bytes))
        raw_artifacts = {
            name: {
                "history": {"blobName": f"raw/{current_settings.source}/runs/{run_id}/{name}.ndjson"},
                "latest": {"blobName": f"raw/{current_settings.source}/latest/{name}.ndjson"},
            }
            for name in raw_bytes
        }
        snapshot_artifacts = {
            name: {
                "latest": {
                    "blobName": f"snapshots/{current_settings.source}/latest/{name}.json"
                }
            }
            for name in snapshot_bytes
        }
        return raw_artifacts, snapshot_artifacts

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        lambda require_remote_persistence: settings,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.CosmosMetadataStore",
        FakeCosmosMetadataStore,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.upload_artifacts_to_blob",
        fake_upload,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.persist_projection_documents",
        lambda *_args, **_kwargs: None,
    )

    result = run_ingestion(
        trigger="test",
        invocation_id="abcdef123456",
        require_remote_persistence=True,
    )

    assert result["status"] == "succeeded"
    assert result["source"] == "mock"
    assert result["rawRecords"]["org_metrics"] == 3
    assert "daily_summary" in result["snapshotRecords"]
    assert "org_metrics" in result["rawBlobs"]
    assert Path(str(result["localOutputs"]["org_metrics"])).exists()
    assert Path(str(result["localOutputs"]["daily_summary"])).exists()
    assert uploaded, "Blob Storage へアップロードされていない"

    run_documents = [
        document
        for document in FakeCosmosMetadataStore.instances[0].documents
        if document["documentType"] == "ingestion-run"
    ]
    assert [document["status"] for document in run_documents] == ["running", "succeeded"]


def test_run_ingestion_records_failure_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """アップロード失敗時は Cosmos DB に failed 状態が残る。"""
    FakeCosmosMetadataStore.reset()
    settings = make_settings(tmp_path, write_local_outputs=False)

    def raise_upload_error(
        _settings: IngestionSettings,
        _run_id: str,
        _raw_bytes: dict[str, bytes],
        _snapshot_bytes: dict[str, bytes],
    ) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        raise AzureError("blob upload failed")

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        lambda require_remote_persistence: settings,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.CosmosMetadataStore",
        FakeCosmosMetadataStore,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.upload_artifacts_to_blob",
        raise_upload_error,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.persist_projection_documents",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(AzureError):
        run_ingestion(
            trigger="test",
            invocation_id="failed123456",
            require_remote_persistence=True,
        )

    run_documents = [
        document
        for document in FakeCosmosMetadataStore.instances[0].documents
        if document["documentType"] == "ingestion-run"
    ]
    assert run_documents[-1]["status"] == "failed"
    assert "blob upload failed" in str(run_documents[-1]["error"])


def test_get_ingestion_status_includes_latest_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """status API 用の payload に latestRun が含まれる。"""
    FakeCosmosMetadataStore.reset()
    settings = make_settings(tmp_path, write_local_outputs=False)
    settings.blob_connection_string = None
    settings.blob_service_endpoint = "https://example.blob.core.windows.net"
    settings.cosmos_connection_string = None
    settings.cosmos_endpoint = "https://example.documents.azure.com:443/"
    FakeCosmosMetadataStore.latest_by_source["mock"] = {
        "id": "latest:mock",
        "source": "mock",
        "status": "succeeded",
        "runId": "run-123",
    }

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        lambda require_remote_persistence: settings,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.CosmosMetadataStore",
        FakeCosmosMetadataStore,
    )

    payload = get_ingestion_status()

    assert payload["status"] == "ready"
    assert payload["remotePersistenceConfigured"] is True
    assert payload["latestRun"]["runId"] == "run-123"


def test_get_ingestion_status_reports_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """設定エラーは status payload にまとめられる。"""

    def raise_config_error(*, require_remote_persistence: bool) -> IngestionSettings:
        raise ValueError("invalid configuration")

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        raise_config_error,
    )

    payload = get_ingestion_status()

    assert payload["status"] == "configuration-error"
    assert "invalid configuration" in str(payload["error"])


def test_load_dashboard_snapshot_bytes_reads_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blob 未設定時はローカル snapshot を返す。"""
    settings = make_settings(tmp_path, write_local_outputs=False)
    settings.blob_connection_string = None
    settings.blob_service_endpoint = None
    settings.snapshot_output_dir.mkdir(parents=True, exist_ok=True)
    expected = b'{"status":"ok"}'
    (settings.snapshot_output_dir / "daily_summary.json").write_bytes(expected)

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        lambda require_remote_persistence: settings,
    )

    assert load_dashboard_snapshot_bytes("daily_summary.json") == expected


def test_load_ingestion_settings_accepts_identity_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """managed identity 前提の endpoint 設定でも validation を通せる。"""
    clear_ingestion_env(monkeypatch)
    monkeypatch.setenv("COPILOT_METRICS_SOURCE", "mock")
    monkeypatch.setenv(
        "METRICS_STORAGE_BLOB_ENDPOINT",
        "https://example.blob.core.windows.net",
    )
    monkeypatch.setenv(
        "AZURE_COSMOS_ENDPOINT",
        "https://example.documents.azure.com:443/",
    )
    monkeypatch.setenv("INGESTION_RAW_OUTPUT_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("INGESTION_SNAPSHOT_OUTPUT_DIR", str(tmp_path / "snapshots"))

    settings = load_ingestion_settings(require_remote_persistence=True)

    assert settings.blob_connection_string is None
    assert settings.blob_service_endpoint == "https://example.blob.core.windows.net"
    assert settings.cosmos_connection_string is None
    assert settings.cosmos_endpoint == "https://example.documents.azure.com:443/"


def test_load_dashboard_snapshot_bytes_reads_remote_blob_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blob endpoint + managed identity 構成でも最新 snapshot を読める。"""
    settings = make_settings(tmp_path, write_local_outputs=False)
    settings.blob_connection_string = None
    settings.blob_service_endpoint = "https://example.blob.core.windows.net"
    expected = b'{"status":"remote"}'

    monkeypatch.setattr(
        "src.ingestion_runtime.load_ingestion_settings",
        lambda require_remote_persistence: settings,
    )
    monkeypatch.setattr(
        "src.ingestion_runtime.create_blob_service_client",
        lambda current_settings: (FakeBlobServiceClient(expected), None),
    )

    assert load_dashboard_snapshot_bytes("daily_summary.json") == expected
