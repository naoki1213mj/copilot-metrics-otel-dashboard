"""src.transform モジュールのテスト。"""

import json

import polars as pl
import pytest

from src.transform import (
    DashboardSnapshotBundle,
    LANGUAGE_METRIC_COLUMNS,
    METRIC_COLUMNS,
    ORG_DAILY_METRIC_COLUMNS,
    USER_FLAG_COLUMNS,
    build_dashboard_snapshot_bundle,
    ensure_columns,
    main,
    serialize_json_bytes,
    transform_daily_summary,
    transform_language_summary,
    transform_user_daily_summary,
    transform_user_summary,
    write_dashboard_snapshot_bundle,
)


# ---------------------------------------------------------------------------
# ensure_columns
# ---------------------------------------------------------------------------


def test_ensure_columns_adds_missing():
    """数値・真偽値カラムが欠けている場合、既定値で補完される。"""
    df = pl.DataFrame({"day": ["2025-01-01"], "total_active_users": [5]})
    result = ensure_columns(
        df,
        {
            **{col: 0 for col in METRIC_COLUMNS},
            **{col: 0 for col in ORG_DAILY_METRIC_COLUMNS},
            **{col: False for col in USER_FLAG_COLUMNS},
        },
    )

    for col in METRIC_COLUMNS:
        assert col in result.columns, f"{col} が追加されていない"
    for col in ORG_DAILY_METRIC_COLUMNS:
        assert col in result.columns, f"{col} が追加されていない"
    for col in USER_FLAG_COLUMNS:
        assert col in result.columns, f"{col} が追加されていない"

    # 新規追加されたカラムの値は 0
    row = result.to_dicts()[0]
    assert row["chat_panel_agent_mode"] == 0
    assert row["agent_edit"] == 0
    assert row["monthly_active_agent_users"] == 0
    assert row["used_copilot_coding_agent"] is False


def test_ensure_columns_preserves_existing():
    """既存カラムの値が上書きされないこと。"""
    df = pl.DataFrame(
        {
            "day": ["2025-01-01"],
            "total_active_users": [42],
            "user_initiated_interaction_count": [100],
            "used_copilot_coding_agent": [True],
        }
    )
    result = ensure_columns(
        df,
        {
            **{col: 0 for col in METRIC_COLUMNS},
            **{col: False for col in USER_FLAG_COLUMNS},
        },
    )
    row = result.to_dicts()[0]

    assert row["total_active_users"] == 42
    assert row["user_initiated_interaction_count"] == 100
    assert row["used_copilot_coding_agent"] is True


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
    expected_keys = {"day", *METRIC_COLUMNS, *ORG_DAILY_METRIC_COLUMNS}
    assert set(result[0].keys()) == expected_keys


def test_transform_daily_summary_returns_empty_without_day():
    """day カラムが無い場合は空配列で返す。"""
    assert transform_daily_summary(pl.DataFrame({"value": [1]})) == []


def test_transform_daily_summary_fills_missing_official_metrics():
    """新しい公式日次メトリクスが欠けていても 0 で補完されること。"""
    df = _make_org_df(
        [{"day": "2025-01-01", "total_active_users": 5}]
    )
    result = transform_daily_summary(df)

    assert result[0]["monthly_active_agent_users"] == 0
    assert result[0]["copilot_coding_agent_active_users_1d"] == 0
    assert result[0]["copilot_coding_agent_active_users_7d"] == 0
    assert result[0]["copilot_coding_agent_active_users_28d"] == 0


def test_transform_language_summary_flattens_nested_breakdown():
    """totals_by_language_feature を日次の言語別レコードに展開できること。"""
    df = _make_org_df(
        [
            {
                "day": "2025-01-01",
                "totals_by_language_feature": [
                    {
                        "language": "python",
                        "feature": "code_completion",
                        "user_initiated_interaction_count": 6,
                        "code_generation_activity_count": 10,
                        "code_acceptance_activity_count": 4,
                    },
                    {
                        "language": "hcl",
                        "feature": "chat_panel_agent_mode",
                        "user_initiated_interaction_count": 2,
                        "code_generation_activity_count": 8,
                        "code_acceptance_activity_count": 3,
                    },
                ],
            }
        ]
    )

    result = transform_language_summary(df)

    assert len(result) == 2
    assert result[0]["day"] == "2025-01-01"
    assert result[0]["language"] == "python"
    assert result[1]["language"] == "hcl"
    assert all(metric in result[0] for metric in LANGUAGE_METRIC_COLUMNS)


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


def test_transform_user_summary_aggregates_official_flags():
    """公式フラグは日数集計と観測期間内の利用有無に集約されること。"""
    df = _make_user_df(
        [
            {
                "user_login": "alice",
                "day": "2025-01-01",
                "user_initiated_interaction_count": 10,
                "used_copilot_coding_agent": True,
                "used_copilot_code_review_active": False,
                "used_copilot_code_review_passive": True,
            },
            {
                "user_login": "alice",
                "day": "2025-01-02",
                "user_initiated_interaction_count": 10,
                "used_copilot_coding_agent": False,
                "used_copilot_code_review_active": True,
                "used_copilot_code_review_passive": False,
            },
            {
                "user_login": "bob",
                "day": "2025-01-01",
                "user_initiated_interaction_count": 1,
            },
        ]
    )
    result = transform_user_summary(df)

    by_user = {r["user_login"]: r for r in result}
    assert by_user["alice"]["used_copilot_coding_agent"] is True
    assert by_user["alice"]["used_copilot_coding_agent_days"] == 1
    assert by_user["alice"]["used_copilot_code_review_active"] is True
    assert by_user["alice"]["used_copilot_code_review_active_days"] == 1
    assert by_user["alice"]["used_copilot_code_review_passive"] is True
    assert by_user["alice"]["used_copilot_code_review_passive_days"] == 1
    assert by_user["bob"]["used_copilot_coding_agent"] is False
    assert by_user["bob"]["used_copilot_coding_agent_days"] == 0


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


def test_transform_user_summary_returns_empty_without_user_login():
    """user_login が無い場合は空配列で返す。"""
    assert transform_user_summary(pl.DataFrame({"day": ["2025-01-01"]})) == []


def test_transform_user_daily_summary_removes_user_id_and_sorts():
    """日次ユーザーデータは user_id を除外し、day / user_login で並ぶこと。"""
    df = _make_user_df(
        [
            {
                "user_login": "bob",
                "user_id": 2,
                "day": "2025-01-02",
                "user_initiated_interaction_count": 3,
            },
            {
                "user_login": "alice",
                "user_id": 1,
                "day": "2025-01-01",
                "user_initiated_interaction_count": 2,
            },
        ]
    )

    result = transform_user_daily_summary(df)

    assert [row["user_login"] for row in result] == ["alice", "bob"]
    assert all("user_id" not in row for row in result)
    assert "used_copilot_coding_agent" in result[0]


def test_build_dashboard_snapshot_bundle_contains_all_sections():
    """bundle 化したスナップショットに各セクションが揃うこと。"""
    org_df = _make_org_df([{"day": "2025-01-01", "total_active_users": 1}])
    user_df = _make_user_df(
        [
            {
                "day": "2025-01-01",
                "user_login": "alice",
                "user_initiated_interaction_count": 2,
            }
        ]
    )

    bundle = build_dashboard_snapshot_bundle(org_df, user_df)

    assert isinstance(bundle, DashboardSnapshotBundle)
    assert len(bundle.daily_summary) == 1
    assert len(bundle.user_summary) == 1
    assert len(bundle.user_daily_summary) == 1
    assert bundle.language_summary == []


def test_write_dashboard_snapshot_bundle_creates_files(tmp_path):
    """スナップショット bundle を JSON ファイルとして保存できること。"""
    bundle = DashboardSnapshotBundle(
        daily_summary=[{"day": "2025-01-01"}],
        user_summary=[{"user_login": "alice"}],
        user_daily_summary=[{"day": "2025-01-01", "user_login": "alice"}],
        language_summary=[{"day": "2025-01-01", "language": "python"}],
    )

    output_paths = write_dashboard_snapshot_bundle(bundle, tmp_path)

    assert set(output_paths) == {
        "daily_summary",
        "user_summary",
        "user_daily_summary",
        "language_summary",
    }
    for path in output_paths.values():
        assert path.exists()


def test_serialize_json_bytes_preserves_unicode():
    """JSON バイト列化しても日本語が保持されること。"""
    payload = [{"message": "こんにちは"}]
    content = serialize_json_bytes(payload)

    assert json.loads(content.decode("utf-8")) == payload


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
    assert "monthly_active_agent_users" in daily[0]
    assert "copilot_coding_agent_active_users_28d" in daily[0]

    # user_summary.json の検証
    user_path = out_dir / "user_summary.json"
    assert user_path.exists()
    users = json.loads(user_path.read_text(encoding="utf-8"))
    assert len(users) == 2
    for row in users:
        assert "user_login" in row
        assert "active_days" in row
        assert "user_id" not in row
        assert "used_copilot_coding_agent" in row
        assert "used_copilot_coding_agent_days" in row

    user_daily_path = out_dir / "user_daily_summary.json"
    assert user_daily_path.exists()
    user_daily = json.loads(user_daily_path.read_text(encoding="utf-8"))
    assert len(user_daily) == 4
    assert all("user_id" not in row for row in user_daily)

    language_path = out_dir / "language_summary.json"
    assert language_path.exists()
    languages = json.loads(language_path.read_text(encoding="utf-8"))
    assert isinstance(languages, list)
