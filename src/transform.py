"""NDJSON データを React ダッシュボード向けの JSON に変換する。

入力:
  - data/raw/org_metrics.ndjson   (Organization daily reports を束ねた NDJSON)
  - data/raw/user_metrics.ndjson  (ユーザー daily reports を束ねた NDJSON)

出力:
  - dashboard/public/data/daily_summary.json   (日次サマリー。日付昇順)
  - dashboard/public/data/user_summary.json    (ユーザー別の観測期間集計)
  - dashboard/public/data/user_daily_summary.json (user_id を除いたユーザー日次データ)
  - dashboard/public/data/language_summary.json (言語別の日次 breakdown)
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
    "code_acceptance_activity_count",
    "chat_panel_agent_mode",
    "chat_panel_ask_mode",
    "chat_panel_edit_mode",
    "chat_panel_custom_mode",
    "agent_edit",
]
ORG_DAILY_METRIC_COLUMNS = [
    "monthly_active_agent_users",
    "copilot_coding_agent_active_users_1d",
    "copilot_coding_agent_active_users_7d",
    "copilot_coding_agent_active_users_28d",
]
USER_FLAG_COLUMNS = [
    "used_copilot_coding_agent",
    "used_copilot_code_review_active",
    "used_copilot_code_review_passive",
]
LANGUAGE_METRIC_COLUMNS = [
    "user_initiated_interaction_count",
    "code_generation_activity_count",
    "code_acceptance_activity_count",
]


def read_ndjson(path: Path) -> pl.DataFrame:
    """NDJSON ファイルを DataFrame として読み込む。"""
    content = path.read_bytes()
    df = pl.read_ndjson(io.BytesIO(content))
    logger.info("読み込み: %s (%d 行)", path, len(df))
    return df


def ensure_columns(df: pl.DataFrame, defaults: dict[str, object]) -> pl.DataFrame:
    """DataFrame に必要なカラムが無い場合、既定値で埋めて追加する。"""
    missing_columns = [
        pl.lit(default).alias(col)
        for col, default in defaults.items()
        if col not in df.columns
    ]
    if missing_columns:
        df = df.with_columns(missing_columns)
    return df


def transform_daily_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """Organization NDJSON を日付昇順の日次サマリーに変換する。"""
    df = ensure_columns(
        df,
        {
            **{col: 0 for col in METRIC_COLUMNS},
            **{col: 0 for col in ORG_DAILY_METRIC_COLUMNS},
        },
    )
    df = df.sort("day")
    return df.select(["day", *METRIC_COLUMNS, *ORG_DAILY_METRIC_COLUMNS]).to_dicts()


def transform_user_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """ユーザー NDJSON を user_login ごとに観測期間の合計値で集計する。

    total_active_users はユーザーレベルでは常に 1 なので、
    アクティブだった日数（= 行数）を active_days として集計する。
    """
    df = ensure_columns(
        df,
        {
            **{col: 0 for col in METRIC_COLUMNS},
            **{col: False for col in USER_FLAG_COLUMNS},
        },
    )

    agg_cols = [col for col in METRIC_COLUMNS if col != "total_active_users"]
    result = df.group_by("user_login").agg(
        pl.len().alias("active_days"),
        *[pl.col(col).sum().alias(col) for col in agg_cols],
        *[
            pl.col(col).cast(pl.Int64).sum().alias(f"{col}_days")
            for col in USER_FLAG_COLUMNS
        ],
        *[pl.col(col).any().alias(col) for col in USER_FLAG_COLUMNS],
    )
    # インタラクション合計で降順ソート
    result = result.sort("user_initiated_interaction_count", descending=True)
    return result.to_dicts()


def transform_user_daily_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """user_id を除いたユーザー日次データを UI 向けに整形する。"""
    df = ensure_columns(
        df,
        {
            **{col: 0 for col in METRIC_COLUMNS},
            **{col: False for col in USER_FLAG_COLUMNS},
        },
    )
    return (
        df.sort(["day", "user_login"])
        .select(["day", "user_login", *METRIC_COLUMNS, *USER_FLAG_COLUMNS])
        .to_dicts()
    )


def transform_language_summary(df: pl.DataFrame) -> list[dict[str, object]]:
    """Organization の language breakdown を UI 向けに平坦化する。"""
    if "totals_by_language_feature" not in df.columns:
        return []

    language_rows: list[dict[str, object]] = []
    for row in df.select(["day", "totals_by_language_feature"]).to_dicts():
        day = str(row["day"])
        totals = row.get("totals_by_language_feature", [])
        if not isinstance(totals, list):
            continue
        for language_entry in totals:
            if not isinstance(language_entry, dict):
                continue
            language_rows.append(
                {
                    "day": day,
                    "language": str(language_entry.get("language", "unknown")),
                    "feature": str(language_entry.get("feature", "code_completion")),
                    **{
                        metric: int(language_entry.get(metric, 0))
                        for metric in LANGUAGE_METRIC_COLUMNS
                    },
                }
            )

    if not language_rows:
        return []

    language_df = pl.DataFrame(language_rows)
    aggregated = (
        language_df.group_by(["day", "language"])
        .agg(
            *[
                pl.col(metric).sum().alias(metric)
                for metric in LANGUAGE_METRIC_COLUMNS
            ]
        )
        .with_columns(
            (
                pl.col("user_initiated_interaction_count")
                + pl.col("code_generation_activity_count")
                + pl.col("code_acceptance_activity_count")
            ).alias("activity_score")
        )
        .sort(["day", "activity_score"], descending=[False, True])
    )
    return aggregated.to_dicts()


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
    language_summary = transform_language_summary(org_df)
    save_json(language_summary, PUBLIC_DATA_DIR / "language_summary.json")

    user_df = read_ndjson(user_ndjson)
    users = transform_user_summary(user_df)
    save_json(users, PUBLIC_DATA_DIR / "user_summary.json")
    user_daily = transform_user_daily_summary(user_df)
    save_json(user_daily, PUBLIC_DATA_DIR / "user_daily_summary.json")
    remove_legacy_public_raw_files()


if __name__ == "__main__":
    main()
