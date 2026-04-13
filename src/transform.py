"""NDJSON データを React ダッシュボード向けの JSON に変換する。

入力:
  - data/raw/org_metrics.ndjson   (Organization 28 日レポート)
  - data/raw/user_metrics.ndjson  (ユーザー 28 日レポート)

出力:
  - dashboard/public/data/daily_summary.json   (日次サマリー。日付昇順)
  - dashboard/public/data/user_summary.json    (ユーザー別 28 日間集計)
"""

import io
import json
import logging
import sys
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path("data") / "raw"
PUBLIC_DATA_DIR = Path("dashboard") / "public" / "data"
LEGACY_PUBLIC_RAW_FILES = (
    PUBLIC_DATA_DIR / "org_metrics.ndjson",
    PUBLIC_DATA_DIR / "user_metrics.ndjson",
    PUBLIC_DATA_DIR / "org_metrics.json",
    PUBLIC_DATA_DIR / "user_metrics.json",
)

# 集計対象のメトリクスカラム
METRIC_COLUMNS = [
    "total_active_users",
    "user_initiated_interaction_count",
    "code_generation_activity_count",
    "chat_panel_agent_mode",
    "chat_panel_ask_mode",
    "chat_panel_edit_mode",
    "chat_panel_custom_mode",
    "agent_edit",
]


def read_ndjson(path: Path) -> pl.DataFrame:
    """NDJSON ファイルを DataFrame として読み込む。"""
    content = path.read_bytes()
    df = pl.read_ndjson(io.BytesIO(content))
    logger.info("読み込み: %s (%d 行)", path, len(df))
    return df


def ensure_columns(df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    """DataFrame に必要なカラムが無い場合、0 で埋めて追加する。"""
    for col in columns:
        if col not in df.columns:
            df = df.with_columns(pl.lit(0).alias(col))
    return df


def transform_daily_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """Organization NDJSON を日付昇順の日次サマリーに変換する。"""
    df = ensure_columns(df, METRIC_COLUMNS)
    df = df.sort("day")
    return df.select(["day", *METRIC_COLUMNS]).to_dicts()


def transform_user_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """ユーザー NDJSON を user_login ごとに 28 日間の合計値で集計する。

    total_active_users はユーザーレベルでは常に 1 なので、
    アクティブだった日数（= 行数）を active_days として集計する。
    """
    df = ensure_columns(df, METRIC_COLUMNS)

    agg_cols = [col for col in METRIC_COLUMNS if col != "total_active_users"]
    result = df.group_by("user_login").agg(
        pl.len().alias("active_days"),
        *[pl.col(col).sum().alias(col) for col in agg_cols],
    )
    # インタラクション合計で降順ソート
    result = result.sort("user_initiated_interaction_count", descending=True)
    return result.to_dicts()


def save_json(data: list[dict[str, object]], path: Path) -> None:
    """JSON ファイルに保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("保存: %s (%d 件)", path, len(data))


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

    org_ndjson = RAW_DATA_DIR / "org_metrics.ndjson"
    user_ndjson = RAW_DATA_DIR / "user_metrics.ndjson"
    missing_inputs = [path for path in (org_ndjson, user_ndjson) if not path.exists()]
    if missing_inputs:
        for path in missing_inputs:
            logger.error("%s が見つかりません。先に generate_mock.py か fetch_metrics.py を実行してください。", path)
        sys.exit(1)

    org_df = read_ndjson(org_ndjson)
    daily = transform_daily_summary(org_df)
    save_json(daily, PUBLIC_DATA_DIR / "daily_summary.json")

    user_df = read_ndjson(user_ndjson)
    users = transform_user_summary(user_df)
    save_json(users, PUBLIC_DATA_DIR / "user_summary.json")
    remove_legacy_public_raw_files()


if __name__ == "__main__":
    main()
