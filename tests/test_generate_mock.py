"""generate_mock モジュールのテスト。"""

import json
import random
from datetime import date, timedelta

import pytest

from src.generate_mock import (
    FIELD_RANGES,
    MOCK_USERS,
    NUM_DAYS,
    generate_dates,
    generate_org_row,
    generate_user_row,
    main,
    write_ndjson,
)


class TestGenerateDates:
    def test_returns_28_days(self) -> None:
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


class TestGenerateOrgRow:
    @pytest.fixture()
    def org_row(self) -> dict:
        random.seed(0)
        return generate_org_row(date(2025, 7, 1))

    def test_has_all_fields(self, org_row: dict) -> None:
        assert "day" in org_row
        assert "organization_id" in org_row
        for field in FIELD_RANGES:
            assert field in org_row, f"{field} が欠けている"

    def test_values_in_range(self, org_row: dict) -> None:
        for field, (lo, hi) in FIELD_RANGES.items():
            value = org_row[field]
            assert lo <= value <= hi, f"{field}={value} が [{lo}, {hi}] の範囲外"


class TestGenerateUserRow:
    @pytest.fixture()
    def user_row(self) -> dict:
        random.seed(0)
        return generate_user_row(date(2025, 7, 1), MOCK_USERS[0])

    def test_has_user_fields(self, user_row: dict) -> None:
        assert "user_id" in user_row
        assert "user_login" in user_row
        assert user_row["total_active_users"] == 1

    def test_values_smaller_than_org(self, user_row: dict) -> None:
        """ユーザーレベルの各フィールドは Organization レベルの上限以下。"""
        for field, (_lo, hi) in FIELD_RANGES.items():
            assert user_row[field] <= hi, (
                f"{field}={user_row[field]} が org 上限 {hi} を超えている"
            )


class TestWriteNdjson:
    def test_creates_valid_file(self, tmp_path: object) -> None:
        rows = [{"a": 1}, {"b": 2}, {"c": 3}]
        out = tmp_path / "test.ndjson"  # type: ignore[operator]
        write_ndjson(rows, out)

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == len(rows)
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)


class TestMain:
    def test_creates_ndjson_files(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.generate_mock.RAW_DATA_DIR", tmp_path)
        # remove_legacy_public_raw_files は存在しないパスを削除しようとするだけなのでスキップ
        monkeypatch.setattr("src.generate_mock.remove_legacy_public_raw_files", lambda: None)
        main()

        org_file = tmp_path / "org_metrics.ndjson"  # type: ignore[operator]
        user_file = tmp_path / "user_metrics.ndjson"  # type: ignore[operator]

        assert org_file.exists()
        assert user_file.exists()

        org_lines = org_file.read_text(encoding="utf-8").splitlines()
        user_lines = user_file.read_text(encoding="utf-8").splitlines()

        assert len(org_lines) == NUM_DAYS  # 28 行
        assert len(user_lines) == NUM_DAYS * len(MOCK_USERS)  # 280 行


class TestSeedDeterminism:
    def test_same_seed_same_output(self) -> None:
        """同じシードで 2 回実行すると同一の結果になる。"""
        day = date(2025, 7, 1)

        random.seed(99)
        run1 = [generate_org_row(day) for _ in range(5)]

        random.seed(99)
        run2 = [generate_org_row(day) for _ in range(5)]

        assert run1 == run2
