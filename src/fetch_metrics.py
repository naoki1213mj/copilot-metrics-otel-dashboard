"""GitHub Copilot usage metrics API から raw NDJSON を取得する。

Organization レベルの 28 日レポート（組織全体・ユーザー別）を取得し、
非公開ディレクトリ data/raw/ に NDJSON ファイルとして出力する。
"""

import io
import json
import logging
import os
import sys
from pathlib import Path

import httpx
import polars as pl
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

API_VERSION = "2026-03-10"
BASE_URL = "https://api.github.com"
RAW_DATA_DIR = Path("data") / "raw"
LEGACY_PUBLIC_RAW_FILES = (
    Path("dashboard") / "public" / "data" / "org_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "user_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "org_metrics.json",
    Path("dashboard") / "public" / "data" / "user_metrics.json",
)


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

    configure_azure_monitor(connection_string=conn_str)
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
            "Accept": "application/json",
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
    resp.raise_for_status()
    data = resp.json()

    links: list[str] = data.get("download_links", [])
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
    return pl.concat(frames) if frames else pl.DataFrame()


def save_ndjson(df: pl.DataFrame, output_path: Path) -> None:
    """DataFrame を NDJSON ファイルに保存する。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in df.to_dicts():
            file.write(json.dumps(row, ensure_ascii=False))
            file.write("\n")
    logger.info("保存: %s (%d 行)", output_path, len(df))


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
    token = os.getenv("GITHUB_TOKEN")
    org = os.getenv("GITHUB_ORG")
    if not token or not org:
        logger.error("GITHUB_TOKEN と GITHUB_ORG を .env に設定してください。")
        sys.exit(1)

    output_dir = RAW_DATA_DIR

    with build_api_client(token) as api_client, build_download_client() as dl_client:
        setup_telemetry(api_client)
        remove_legacy_public_raw_files()

        # Organization 28 日レポート
        org_df = fetch_report(
            api_client,
            dl_client,
            f"/orgs/{org}/copilot/metrics/reports/organization-28-day/latest",
        )
        save_ndjson(org_df, output_dir / "org_metrics.ndjson")

        # ユーザー 28 日レポート
        user_df = fetch_report(
            api_client,
            dl_client,
            f"/orgs/{org}/copilot/metrics/reports/users-28-day/latest",
        )
        save_ndjson(user_df, output_dir / "user_metrics.ndjson")


if __name__ == "__main__":
    main()
