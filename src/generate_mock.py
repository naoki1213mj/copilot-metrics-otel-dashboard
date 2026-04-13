"""モックデータを NDJSON 形式で生成する。

実 API を叩けない環境でもダッシュボードの動作確認ができるように、
Organization レベル・ユーザーレベルの 28 日レポートを生成する。
出力先は実データと同じ非公開ディレクトリ data/raw/。
"""

import json
import logging
import random
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

MOCK_ORG_ID = 123456789
RAW_DATA_DIR = Path("data") / "raw"
LEGACY_PUBLIC_RAW_FILES = (
    Path("dashboard") / "public" / "data" / "org_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "user_metrics.ndjson",
    Path("dashboard") / "public" / "data" / "org_metrics.json",
    Path("dashboard") / "public" / "data" / "user_metrics.json",
)
MOCK_USERS = [
    {"user_id": 1001, "user_login": "alice"},
    {"user_id": 1002, "user_login": "bob"},
    {"user_id": 1003, "user_login": "charlie"},
    {"user_id": 1004, "user_login": "diana"},
    {"user_id": 1005, "user_login": "eve"},
    {"user_id": 1006, "user_login": "frank"},
    {"user_id": 1007, "user_login": "grace"},
    {"user_id": 1008, "user_login": "henry"},
    {"user_id": 1009, "user_login": "iris"},
    {"user_id": 1010, "user_login": "jack"},
]
NUM_DAYS = 28

# SKILL.md に記載のレンジ目安
FIELD_RANGES: dict[str, tuple[int, int]] = {
    "total_active_users": (5, 15),
    "user_initiated_interaction_count": (50, 300),
    "code_generation_activity_count": (100, 500),
    "code_acceptance_activity_count": (60, 350),
    "chat_panel_agent_mode": (0, 50),
    "chat_panel_ask_mode": (20, 100),
    "chat_panel_edit_mode": (10, 80),
    "chat_panel_custom_mode": (0, 20),
    "agent_edit": (5, 30),
}


def generate_dates() -> list[date]:
    """過去 28 日分の日付リストを生成する。実 API は 2 日遅れなので today - 2 から遡る。"""
    end = date.today() - timedelta(days=2)
    return [end - timedelta(days=i) for i in range(NUM_DAYS - 1, -1, -1)]


def generate_org_row(day: date) -> dict:
    """Organization レベルの 1 日分データを生成する。"""
    row: dict = {
        "day": day.isoformat(),
        "organization_id": MOCK_ORG_ID,
    }
    for field, (lo, hi) in FIELD_RANGES.items():
        row[field] = random.randint(lo, hi)
    return row


def generate_user_row(day: date, user: dict) -> dict:
    """ユーザーレベルの 1 日 1 ユーザー分データを生成する。

    Organization レベルより小さい値にする（1 ユーザー分なので）。
    """
    row: dict = {
        "day": day.isoformat(),
        "organization_id": MOCK_ORG_ID,
        "user_id": user["user_id"],
        "user_login": user["user_login"],
    }
    for field, (lo, hi) in FIELD_RANGES.items():
        if field == "total_active_users":
            # ユーザーレベルでは常に 1（自分自身）
            row[field] = 1
        else:
            # Organization レベルの 1/10 ～ 1/3 程度の値
            user_lo = max(0, lo // 10)
            user_hi = max(1, hi // 3)
            row[field] = random.randint(user_lo, user_hi)
    return row


def write_ndjson(rows: list[dict], path: Path) -> None:
    """行のリストを NDJSON ファイルに書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.info("保存: %s (%d 行)", path, len(rows))


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

    random.seed(42)

    output_dir = RAW_DATA_DIR
    days = generate_dates()
    remove_legacy_public_raw_files()

    # Organization 28 日レポート
    org_rows = [generate_org_row(day) for day in days]
    write_ndjson(org_rows, output_dir / "org_metrics.ndjson")

    # ユーザー 28 日レポート（10 人 × 28 日 = 280 行）
    user_rows = [
        generate_user_row(day, user) for day in days for user in MOCK_USERS
    ]
    write_ndjson(user_rows, output_dir / "user_metrics.ndjson")


if __name__ == "__main__":
    main()
