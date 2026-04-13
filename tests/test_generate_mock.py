"""generate_mock モジュールのテスト。"""

import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.generate_mock import (
    FIELD_RANGES,
    MOCK_USERS,
    NUM_DAYS,
    ORG_DAILY_ROLLUP_FIELDS,
    USER_FLAG_FIELDS,
    USER_METRIC_FIELDS,
    generate_dates,
    generate_mock_data,
    generate_org_row,
    generate_user_row,
    main,
    write_ndjson,
)


class TestGenerateDates:
    def test_returns_configured_days(self) -> None:
        dates = generate_dates()
        assert len(dates) == NUM_DAYS

    def test_ends_at_today_minus_2(self) -> None:
        dates = generate_dates()
        expected_end = date.today() - timedelta(days=2)
        assert dates[-1] == expected_end

    def test_ascending(self) -> None:
        dates = generate_dates()
        assert dates[0] < dates[-1]
        assert dates == sorted(dates)


class TestGenerateUserRow:
    @pytest.fixture()
    def user_row(self) -> dict[str, object]:
        random.seed(0)
        return generate_user_row(date(2025, 7, 1), MOCK_USERS[0])

    def test_has_user_fields(self, user_row: dict[str, object]) -> None:
        assert "user_id" in user_row
        assert "user_login" in user_row
        assert user_row["total_active_users"] == 1
        for field in USER_FLAG_FIELDS:
            assert field in user_row

    def test_values_smaller_than_org_upper_bound(
        self,
        user_row: dict[str, object],
    ) -> None:
        """ユーザーレベルの各フィールドは Organization 想定上限を超えない。"""
        for field, (_lo, hi) in FIELD_RANGES.items():
            assert int(user_row[field]) <= hi, (
                f"{field}={user_row[field]} が org 上限 {hi} を超えている"
            )

    def test_acceptance_not_greater_than_generation(
        self,
        user_row: dict[str, object],
    ) -> None:
        assert (
            int(user_row["code_acceptance_activity_count"])
            <= int(user_row["code_generation_activity_count"])
        )

    def test_flag_fields_are_boolean(self, user_row: dict[str, object]) -> None:
        for field in USER_FLAG_FIELDS:
            assert isinstance(user_row[field], bool)


class TestGenerateMockData:
    @pytest.fixture()
    def generated(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        random.seed(42)
        return generate_mock_data()

    def test_returns_all_days(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, _user_rows = generated
        assert len(org_rows) == NUM_DAYS

    def test_user_rows_vary_by_day_and_user(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        _org_rows, user_rows = generated
        active_days_by_user: defaultdict[str, int] = defaultdict(int)
        for row in user_rows:
            active_days_by_user[str(row["user_login"])] += 1

        assert len(set(active_days_by_user.values())) > 1
        assert min(active_days_by_user.values()) < NUM_DAYS
        assert max(active_days_by_user.values()) <= NUM_DAYS

    def test_org_rows_match_user_rollups(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, user_rows = generated
        user_rows_by_day: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
        for row in user_rows:
            user_rows_by_day[str(row["day"])].append(row)

        rolling_rows: list[list[dict[str, object]]] = []
        for org_row in org_rows:
            day_rows = user_rows_by_day[str(org_row["day"])]
            rolling_rows.append(day_rows)
            expected = generate_org_row(
                date.fromisoformat(str(org_row["day"])),
                day_rows,
                rolling_rows,
            )
            for field in USER_METRIC_FIELDS:
                assert org_row[field] == expected[field]
            for field in ORG_DAILY_ROLLUP_FIELDS:
                assert org_row[field] == expected[field]

    def test_org_metrics_stay_within_expected_ranges(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, _user_rows = generated
        for row in org_rows:
            for field, (low, high) in FIELD_RANGES.items():
                value = int(row[field])
                allowed_high = max(high, int(round(high * 1.3)))
                assert low <= value <= allowed_high, (
                    f"{field}={value} が [{low}, {allowed_high}] の範囲外"
                )

    def test_review_and_agent_flags_have_real_variation(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        _org_rows, user_rows = generated
        coding_agent_users = {
            str(row["user_login"])
            for row in user_rows
            if bool(row["used_copilot_coding_agent"])
        }
        active_review_users = {
            str(row["user_login"])
            for row in user_rows
            if bool(row["used_copilot_code_review_active"])
        }
        passive_review_users = {
            str(row["user_login"])
            for row in user_rows
            if bool(row["used_copilot_code_review_passive"])
        }

        assert 1 < len(coding_agent_users) < len(MOCK_USERS)
        assert 1 < len(active_review_users) < len(MOCK_USERS)
        assert len(active_review_users) <= len(passive_review_users) < len(MOCK_USERS)

    def test_recent_period_has_more_activity_than_early_period(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, _user_rows = generated
        early_period = org_rows[:20]
        recent_period = org_rows[-20:]

        early_prompts = sum(int(row["user_initiated_interaction_count"]) for row in early_period)
        recent_prompts = sum(
            int(row["user_initiated_interaction_count"]) for row in recent_period
        )
        early_agent_days = sum(int(row["chat_panel_agent_mode"]) for row in early_period)
        recent_agent_days = sum(int(row["chat_panel_agent_mode"]) for row in recent_period)

        assert recent_prompts > early_prompts
        assert recent_agent_days > early_agent_days

    def test_series_has_visible_swings(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, _user_rows = generated
        prompt_values = [int(row["user_initiated_interaction_count"]) for row in org_rows]
        agent_values = [int(row["chat_panel_agent_mode"]) for row in org_rows]
        acceptance_rates = [
            (
                int(row["code_acceptance_activity_count"])
                / int(row["code_generation_activity_count"])
                * 100
            )
            if int(row["code_generation_activity_count"]) > 0
            else 0
            for row in org_rows
        ]

        assert max(prompt_values) - min(prompt_values) >= 30
        assert max(agent_values) - min(agent_values) >= 8
        assert max(acceptance_rates) - min(acceptance_rates) >= 6

    def test_language_breakdown_contains_infra_and_script_languages(
        self,
        generated: tuple[list[dict[str, object]], list[dict[str, object]]],
    ) -> None:
        org_rows, user_rows = generated

        org_languages = {
            str(language_row["language"])
            for row in org_rows
            for language_row in row["totals_by_language_feature"]
        }
        user_languages = {
            str(language_row["language"])
            for row in user_rows
            for language_row in row["totals_by_language_feature"]
        }

        assert {
            "python",
            "typescript",
            "hcl",
            "bicep",
            "bash",
            "powershell",
            "pwsh",
            "shellscript",
        } <= org_languages
        assert {"hcl", "bicep", "bash", "powershell", "pwsh", "shellscript"} <= user_languages


class TestWriteNdjson:
    def test_creates_valid_file(self, tmp_path: Path) -> None:
        rows = [{"a": 1}, {"b": 2}, {"c": 3}]
        out = tmp_path / "test.ndjson"
        write_ndjson(rows, out)

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == len(rows)
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)


class TestMain:
    def test_creates_ndjson_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("src.generate_mock.RAW_DATA_DIR", tmp_path)
        monkeypatch.setattr("src.generate_mock.remove_legacy_public_raw_files", lambda: None)
        main()

        org_file = tmp_path / "org_metrics.ndjson"
        user_file = tmp_path / "user_metrics.ndjson"

        assert org_file.exists()
        assert user_file.exists()

        org_lines = org_file.read_text(encoding="utf-8").splitlines()
        user_lines = user_file.read_text(encoding="utf-8").splitlines()

        assert len(org_lines) == NUM_DAYS
        assert NUM_DAYS * 3 <= len(user_lines) <= NUM_DAYS * len(MOCK_USERS)


class TestSeedDeterminism:
    def test_same_seed_same_output(self) -> None:
        """同じシードで 2 回実行すると同一の結果になる。"""
        random.seed(99)
        run1 = generate_mock_data()

        random.seed(99)
        run2 = generate_mock_data()

        assert run1 == run2
