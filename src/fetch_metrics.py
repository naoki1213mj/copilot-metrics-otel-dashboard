"""GitHub Copilot usage metrics API から raw NDJSON を取得する。

Organization の daily report を直近 100 日分取得し、
非公開ディレクトリ data/raw/ に NDJSON ファイルとして出力する。
"""

from collections.abc import Sequence
from dataclasses import dataclass
import io
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx
import polars as pl
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

API_VERSION = "2026-03-10"
BASE_URL = "https://api.github.com"
RAW_DATA_DIR = Path("data") / "raw"
DEFAULT_REPORT_DAYS = 100
MAX_REPORT_DAYS = 100
LEGACY_PUBLIC_RAW_FILES = (
    Path("dashboard") / "public" / "data" / "org_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "user_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "org_metrics.json",
    Path("dashboard") / "public" / "data" / "user_metrics.json",
)
_TELEMETRY_CONFIGURED = False


@dataclass(slots=True)
class RawMetricsBundle:
    """取得した raw メトリクスの DataFrame をまとめる。"""

    org_metrics: pl.DataFrame
    user_metrics: pl.DataFrame


def setup_telemetry(api_client: httpx.Client) -> None:
    """OTel + Application Insights を設定する。

    APPLICATIONINSIGHTS_CONNECTION_STRING が設定されている時だけ有効化する。
    azure-monitor-opentelemetry だけでは httpx は計装されないので、
    GitHub API 用のクライアントだけを HTTPXClientInstrumentor で計装する。
    """
    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING 未設定。OTel は無効。")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    global _TELEMETRY_CONFIGURED
    if not _TELEMETRY_CONFIGURED:
        configure_azure_monitor(connection_string=conn_str)
        _TELEMETRY_CONFIGURED = True
    HTTPXClientInstrumentor().instrument_client(api_client)
    logger.info("OTel + Application Insights を有効化しました（GitHub API クライアントのみ）。")


def build_api_client(token: str) -> httpx.Client:
    """GitHub API 用の httpx.Client を生成する。

    認証ヘッダーと API バージョンヘッダーを設定する。
    署名付き URL のダウンロードには使わないこと（トークン漏えい防止）。
    """
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        },
        timeout=30,
    )


def build_download_client() -> httpx.Client:
    """NDJSON ダウンロード用の httpx.Client を生成する。

    署名付き URL にアクセスするため、認証ヘッダーや OTel 計装は付けない。
    """
    return httpx.Client(timeout=60)


def fetch_report(
    api_client: httpx.Client,
    download_client: httpx.Client,
    path: str,
) -> pl.DataFrame:
    """レポートエンドポイントを呼び出し、NDJSON をダウンロードして DataFrame にする。"""
    resp = api_client.get(path)
    if resp.status_code == httpx.codes.NO_CONTENT:
        logger.info("データなしのためスキップ: %s", path)
        return pl.DataFrame()
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"download_links を含む JSON ではありません: {path}")

    links_raw = data.get("download_links", [])
    if not isinstance(links_raw, list):
        raise ValueError(f"download_links の形式が不正です: {path}")
    links = [str(link) for link in links_raw]
    if not links:
        logger.warning("download_links が空です: %s", path)
        return pl.DataFrame()

    logger.info("%s: %d 件のダウンロードリンクを取得", path, len(links))
    return download_ndjson(download_client, links)


def download_ndjson(client: httpx.Client, links: list[str]) -> pl.DataFrame:
    """署名付き URL から NDJSON をダウンロードして結合する。"""
    frames: list[pl.DataFrame] = []
    for link in links:
        resp = client.get(link)
        resp.raise_for_status()
        df = pl.read_ndjson(io.BytesIO(resp.content))
        frames.append(df)
    return concat_data_frames(frames)


def concat_data_frames(frames: list[pl.DataFrame]) -> pl.DataFrame:
    """スキーマ差分を許容しつつ DataFrame を結合する。"""
    if not frames:
        return pl.DataFrame()
    if len(frames) == 1:
        return frames[0]
    return pl.concat(frames, how="diagonal")


def parse_report_window_days(raw_value: str | None) -> int:
    """取得する日数を検証して返す。"""
    parsed_value = raw_value or str(DEFAULT_REPORT_DAYS)
    try:
        window_days = int(parsed_value)
    except ValueError as exc:
        raise ValueError(
            f"COPILOT_METRICS_DAYS は整数で指定してください: {parsed_value}"
        ) from exc

    if not 1 <= window_days <= MAX_REPORT_DAYS:
        raise ValueError(
            f"COPILOT_METRICS_DAYS は 1〜{MAX_REPORT_DAYS} の範囲で指定してください: {window_days}"
        )
    return window_days


def get_report_window_days() -> int:
    """取得する日数を環境変数から決定する。"""
    try:
        return parse_report_window_days(os.getenv("COPILOT_METRICS_DAYS"))
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)


def generate_report_days(window_days: int) -> list[date]:
    """直近 N 日分の report_day 一覧を古い順で返す。"""
    end = date.today() - timedelta(days=2)
    return [end - timedelta(days=i) for i in range(window_days - 1, -1, -1)]


def fetch_daily_reports(
    api_client: httpx.Client,
    download_client: httpx.Client,
    path_template: str,
    report_days: Sequence[date],
) -> pl.DataFrame:
    """特定日の daily report を複数日ぶん取得して結合する。"""
    frames: list[pl.DataFrame] = []
    for report_day in report_days:
        path = path_template.format(day=report_day.isoformat())
        df = fetch_report(api_client, download_client, path)
        if len(df) > 0:
            frames.append(df)
    return concat_data_frames(frames)


def fetch_metrics_bundle(
    token: str,
    org: str,
    report_days: Sequence[date],
) -> RawMetricsBundle:
    """Organization / User の daily report をまとめて取得する。"""
    with build_api_client(token) as api_client, build_download_client() as download_client:
        setup_telemetry(api_client)
        logger.info("Organization daily reports を %d 日分取得します。", len(report_days))
        org_metrics = fetch_daily_reports(
            api_client,
            download_client,
            f"/orgs/{org}/copilot/metrics/reports/organization-1-day?day={{day}}",
            report_days,
        )
        user_metrics = fetch_daily_reports(
            api_client,
            download_client,
            f"/orgs/{org}/copilot/metrics/reports/users-1-day?day={{day}}",
            report_days,
        )
    return RawMetricsBundle(org_metrics=org_metrics, user_metrics=user_metrics)


def dataframe_to_ndjson_bytes(df: pl.DataFrame) -> bytes:
    """DataFrame を NDJSON バイト列に変換する。"""
    if len(df) == 0:
        return b""
    lines = [json.dumps(row, ensure_ascii=False) for row in df.to_dicts()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def save_ndjson(df: pl.DataFrame, output_path: Path) -> None:
    """DataFrame を NDJSON ファイルに保存する。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(dataframe_to_ndjson_bytes(df))
    logger.info("保存: %s (%d 行)", output_path, len(df))


def write_raw_metrics_bundle(
    bundle: RawMetricsBundle,
    output_dir: Path = RAW_DATA_DIR,
    *,
    remove_legacy_public_raw: bool = True,
) -> dict[str, Path]:
    """raw メトリクスをローカルファイルへ書き出す。"""
    if remove_legacy_public_raw:
        remove_legacy_public_raw_files()
    output_paths = {
        "org_metrics": output_dir / "org_metrics.ndjson",
        "user_metrics": output_dir / "user_metrics.ndjson",
    }
    save_ndjson(bundle.org_metrics, output_paths["org_metrics"])
    save_ndjson(bundle.user_metrics, output_paths["user_metrics"])
    return output_paths


def get_github_configuration_from_env() -> tuple[str, str]:
    """GitHub API 呼び出しに必要な設定を環境変数から取得する。"""
    token = os.getenv("GITHUB_TOKEN")
    org = os.getenv("GITHUB_ORG")
    if not token or not org:
        raise ValueError("GITHUB_TOKEN と GITHUB_ORG を .env に設定してください。")
    return token, org


def remove_legacy_public_raw_files() -> None:
    """旧ワークフローが public に残した raw データを削除する。"""
    for path in LEGACY_PUBLIC_RAW_FILES:
        if not path.exists():
            continue
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("古い raw データを削除できませんでした: %s (%s)", path, exc)
        else:
            logger.info("古い raw データを削除: %s", path)


def main() -> None:
    """メインエントリポイント。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    load_dotenv()
    try:
        token, org = get_github_configuration_from_env()
        report_days = generate_report_days(get_report_window_days())
        bundle = fetch_metrics_bundle(token, org, report_days)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    write_raw_metrics_bundle(bundle, RAW_DATA_DIR)


if __name__ == "__main__":
    main()
