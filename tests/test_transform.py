"""src.transform モジュールのテスト。"""

import json
import sys

import polars as pl
import pytest

from src.transform import (
    METRIC_COLUMNS,
    ensure_columns,
    main,
    transform_daily_summary,
    transform_user_summary,
)


# ---------------------------------------------------------------------------
# ensure_columns
# ---------------------------------------------------------------------------


def test_ensure_columns_adds_missing():
    """METRIC_COLUMNS に含まれるカラムが欠けている場合、0 で補完される。"""
    df = pl.DataFrame({"day": ["2025-01-01"], "total_active_users": [5]})
    result = ensure_columns(df, METRIC_COLUMNS)

    for col in METRIC_COLUMNS:
        assert col in result.columns, f"{col} が追加されていない"

    # 新規追加されたカラムの値は 0
    row = result.to_dicts()[0]
    assert row["chat_panel_agent_mode"] == 0
    assert row["agent_edit"] == 0


def test_ensure_columns_preserves_existing():
    """既存カラムの値が上書きされないこと。"""
    df = pl.DataFrame(
        {
            "day": ["2025-01-01"],
            "total_active_users": [42],
            "user_initiated_interaction_count": [100],
        }
    )
    result = ensure_columns(df, METRIC_COLUMNS)
    row = result.to_dicts()[0]

    assert row["total_active_users"] == 42
    assert row["user_initiated_interaction_count"] == 100


# ---------------------------------------------------------------------------
# transform_daily_summary
# ---------------------------------------------------------------------------


def _make_org_df(rows: list[dict]) -> pl.DataFrame:
    """テスト用の Organization DataFrame を作る。"""
    return pl.DataFrame(rows)


def test_transform_daily_summary_sorted_ascending():
    """日次サマリーが day 昇順でソートされていること。"""
    df = _make_org_df(
        [
            {"day": "2025-01-03", "total_active_users": 1},
            {"day": "2025-01-01", "total_active_users": 2},
            {"day": "2025-01-02", "total_active_users": 3},
        ]
    )
    result = transform_daily_summary(df)
    days = [r["day"] for r in result]
    assert days == ["2025-01-01", "2025-01-02", "2025-01-03"]


def test_transform_daily_summary_has_correct_keys():
    """各レコードに day + 全 METRIC_COLUMNS のキーが含まれること。"""
    df = _make_org_df(
        [{"day": "2025-01-01", "total_active_users": 5}]
    )
    result = transform_daily_summary(df)
    expected_keys = {"day", *METRIC_COLUMNS}
    assert set(result[0].keys()) == expected_keys


# ---------------------------------------------------------------------------
# transform_user_summary
# ---------------------------------------------------------------------------


def _make_user_df(rows: list[dict]) -> pl.DataFrame:
    """テスト用の User DataFrame を作る。"""
    return pl.DataFrame(rows)


def test_transform_user_summary_groups_by_user():
    """2 ユーザー × 3 日 → 2 行に集約され、値が合計されること。"""
    rows = []
    for user in ("alice", "bob"):
        for day_num in range(1, 4):
            rows.append(
                {
                    "user_login": user,
                    "day": f"2025-01-0{day_num}",
                    "user_initiated_interaction_count": 10,
                    "code_generation_activity_count": 5,
                }
            )
    df = _make_user_df(rows)
    result = transform_user_summary(df)

    assert len(result) == 2

    by_user = {r["user_login"]: r for r in result}
    assert by_user["alice"]["user_initiated_interaction_count"] == 30
    assert by_user["alice"]["code_generation_activity_count"] == 15
    assert by_user["bob"]["user_initiated_interaction_count"] == 30


def test_transform_user_summary_no_user_id():
    """出力に user_id が含まれないこと（プライバシー対応）。"""
    df = _make_user_df(
        [
            {
                "user_login": "alice",
                "user_id": 12345,
                "day": "2025-01-01",
                "user_initiated_interaction_count": 1,
            }
        ]
    )
    result = transform_user_summary(df)
    for row in result:
        assert "user_id" not in row, "user_id が出力に含まれている"


def test_transform_user_summary_has_active_days():
    """active_days がユーザーごとの行数と一致すること。"""
    rows = [
        {"user_login": "alice", "day": f"2025-01-0{d}", "user_initiated_interaction_count": 1}
        for d in range(1, 4)
    ] + [
        {"user_login": "bob", "day": "2025-01-01", "user_initiated_interaction_count": 1}
    ]
    df = _make_user_df(rows)
    result = transform_user_summary(df)

    by_user = {r["user_login"]: r for r in result}
    assert by_user["alice"]["active_days"] == 3
    assert by_user["bob"]["active_days"] == 1


def test_transform_user_summary_sorted_by_interactions():
    """user_initiated_interaction_count 降順でソートされること。"""
    rows = [
        {"user_login": "low", "day": "2025-01-01", "user_initiated_interaction_count": 1},
        {"user_login": "high", "day": "2025-01-01", "user_initiated_interaction_count": 100},
        {"user_login": "mid", "day": "2025-01-01", "user_initiated_interaction_count": 50},
    ]
    df = _make_user_df(rows)
    result = transform_user_summary(df)
    logins = [r["user_login"] for r in result]
    assert logins == ["high", "mid", "low"]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_exits_nonzero_on_missing_input(monkeypatch, tmp_path):
    """入力ファイルが存在しない場合、sys.exit(1) で終了すること。"""
    import src.transform as mod

    monkeypatch.setattr(mod, "RAW_DATA_DIR", tmp_path / "nonexistent")
    monkeypatch.setattr(mod, "PUBLIC_DATA_DIR", tmp_path / "out")

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_end_to_end(monkeypatch, tmp_path):
    """NDJSON → JSON 変換の E2E テスト。"""
    import src.transform as mod

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Organization NDJSON
    org_lines = [
        json.dumps(
            {"day": f"2025-01-0{d}", "total_active_users": d * 10}
        )
        for d in range(1, 4)
    ]
    (raw_dir / "org_metrics.ndjson").write_text(
        "\n".join(org_lines), encoding="utf-8"
    )

    # User NDJSON
    user_lines = [
        json.dumps(
            {
                "user_login": user,
                "day": f"2025-01-0{d}",
                "user_initiated_interaction_count": 5,
                "code_generation_activity_count": 3,
            }
        )
        for user in ("alice", "bob")
        for d in range(1, 3)
    ]
    (raw_dir / "user_metrics.ndjson").write_text(
        "\n".join(user_lines), encoding="utf-8"
    )

    monkeypatch.setattr(mod, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(mod, "PUBLIC_DATA_DIR", out_dir)

    main()

    # daily_summary.json の検証
    daily_path = out_dir / "daily_summary.json"
    assert daily_path.exists()
    daily = json.loads(daily_path.read_text(encoding="utf-8"))
    assert len(daily) == 3
    assert daily[0]["day"] == "2025-01-01"
    assert "total_active_users" in daily[0]

    # user_summary.json の検証
    user_path = out_dir / "user_summary.json"
    assert user_path.exists()
    users = json.loads(user_path.read_text(encoding="utf-8"))
    assert len(users) == 2
    for row in users:
        assert "user_login" in row
        assert "active_days" in row
        assert "user_id" not in row
