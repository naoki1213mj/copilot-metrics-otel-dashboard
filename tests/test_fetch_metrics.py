"""fetch_metrics.py のユニットテスト。

すべての HTTP 通信を mock し、ネットワークアクセスなしでテストする。
"""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import polars as pl
import pytest

from src.fetch_metrics import (
    RawMetricsBundle,
    build_api_client,
    build_download_client,
    concat_data_frames,
    dataframe_to_ndjson_bytes,
    download_ndjson,
    fetch_daily_reports,
    fetch_metrics_bundle,
    fetch_report,
    generate_report_days,
    get_report_window_days,
    main,
    parse_report_window_days,
    save_ndjson,
    setup_telemetry,
    write_raw_metrics_bundle,
)


# ---------- helpers ----------


def _make_ndjson_bytes(records: list[dict]) -> bytes:
    """dict のリストを NDJSON バイト列に変換する。"""
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _mock_httpx_response(
    status_code: int = 200,
    *,
    json_data: dict | list | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    """テスト用の httpx.Response を生成する。"""
    if json_data is not None:
        content = json.dumps(json_data).encode("utf-8")
        headers = {"content-type": "application/json"}
    else:
        headers = {"content-type": "application/x-ndjson"}
    return httpx.Response(
        status_code=status_code,
        content=content or b"",
        headers=headers,
        request=httpx.Request("GET", "https://example.com"),
    )


# ---------- build_api_client ----------


class TestBuildApiClient:
    def test_headers(self) -> None:
        """Authorization, Accept, X-GitHub-Api-Version が正しく設定される。"""
        client = build_api_client("token123")
        h = client.headers
        assert h["authorization"] == "Bearer token123"
        assert h["accept"] == "application/vnd.github+json"
        assert h["x-github-api-version"] == "2026-03-10"
        client.close()


# ---------- build_download_client ----------


class TestBuildDownloadClient:
    def test_no_auth_header(self) -> None:
        """ダウンロード用クライアントに Authorization ヘッダーが無い。"""
        client = build_download_client()
        assert "authorization" not in client.headers
        client.close()


# ---------- fetch_report ----------


class TestFetchReport:
    def test_parses_download_links(self) -> None:
        """download_links を辿って NDJSON を DataFrame に変換する。"""
        ndjson_bytes = _make_ndjson_bytes(
            [{"day": "2025-01-01", "total_acceptances_count": 42}]
        )

        api_client = MagicMock(spec=httpx.Client)
        api_client.get.return_value = _mock_httpx_response(
            json_data={"download_links": ["https://example.com/data.ndjson"]}
        )

        dl_client = MagicMock(spec=httpx.Client)
        dl_client.get.return_value = _mock_httpx_response(content=ndjson_bytes)

        df = fetch_report(
            api_client,
            dl_client,
            "/orgs/test/copilot/metrics/reports/organization-1-day?day=2025-01-01",
        )

        assert len(df) == 1
        assert df["day"][0] == "2025-01-01"
        assert df["total_acceptances_count"][0] == 42

    def test_no_content_returns_empty_df(self) -> None:
        """daily report が 204 の場合は空 DataFrame を返す。"""
        api_client = MagicMock(spec=httpx.Client)
        api_client.get.return_value = _mock_httpx_response(status_code=204)
        dl_client = MagicMock(spec=httpx.Client)

        df = fetch_report(
            api_client,
            dl_client,
            "/orgs/test/copilot/metrics/reports/organization-1-day?day=2025-01-01",
        )

        assert len(df) == 0
        dl_client.get.assert_not_called()

    def test_empty_links_returns_empty_df(self, caplog: pytest.LogCaptureFixture) -> None:
        """download_links が空の場合、空 DataFrame を返し warning を出す。"""
        api_client = MagicMock(spec=httpx.Client)
        api_client.get.return_value = _mock_httpx_response(
            json_data={"download_links": []}
        )
        dl_client = MagicMock(spec=httpx.Client)

        with caplog.at_level("WARNING"):
            df = fetch_report(api_client, dl_client, "/orgs/test/report")

        assert len(df) == 0
        assert "download_links が空です" in caplog.text


# ---------- download_ndjson ----------


class TestDownloadNdjson:
    def test_concatenates_multiple_links(self) -> None:
        """複数リンクの NDJSON を結合して 1 つの DataFrame にする。"""
        ndjson_1 = _make_ndjson_bytes([{"id": 1, "val": "a"}])
        ndjson_2 = _make_ndjson_bytes([{"id": 2, "val": "b"}])

        client = MagicMock(spec=httpx.Client)
        client.get.side_effect = [
            _mock_httpx_response(content=ndjson_1),
            _mock_httpx_response(content=ndjson_2),
        ]

        df = download_ndjson(client, ["https://link1", "https://link2"])

        assert len(df) == 2
        assert df["id"].to_list() == [1, 2]
        assert df["val"].to_list() == ["a", "b"]


class TestConcatDataFrames:
    def test_returns_empty_df_for_no_frames(self) -> None:
        df = concat_data_frames([])
        assert len(df) == 0


class TestGenerateReportDays:
    def test_returns_requested_days_in_ascending_order(self) -> None:
        report_days = generate_report_days(5)
        assert len(report_days) == 5
        assert report_days == sorted(report_days)
        assert report_days[-1] == date.today() - timedelta(days=2)


class TestGetReportWindowDays:
    def test_parse_helper_reads_default(self) -> None:
        assert parse_report_window_days(None) == 100

    def test_defaults_to_100(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COPILOT_METRICS_DAYS", raising=False)
        assert get_report_window_days() == 100

    def test_reads_env_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_METRICS_DAYS", "30")
        assert get_report_window_days() == 30

    def test_rejects_invalid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPILOT_METRICS_DAYS", "abc")
        with pytest.raises(SystemExit) as exc_info:
            get_report_window_days()
        assert exc_info.value.code == 1


class TestDataFrameToNdjsonBytes:
    def test_serializes_rows(self) -> None:
        df = pl.DataFrame({"id": [1, 2], "name": ["alice", "bob"]})
        content = dataframe_to_ndjson_bytes(df).decode("utf-8").splitlines()

        assert [json.loads(line)["name"] for line in content] == ["alice", "bob"]


class TestFetchMetricsBundle:
    def test_fetches_org_and_user_reports(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expected_org_df = pl.DataFrame({"day": ["2025-01-01"], "value": [1]})
        expected_user_df = pl.DataFrame(
            {"day": ["2025-01-01"], "user_login": ["alice"]}
        )

        monkeypatch.setattr(
            "src.fetch_metrics.build_api_client",
            lambda token: httpx.Client(),
        )
        monkeypatch.setattr(
            "src.fetch_metrics.build_download_client",
            lambda: httpx.Client(),
        )
        monkeypatch.setattr("src.fetch_metrics.setup_telemetry", lambda client: None)
        monkeypatch.setattr(
            "src.fetch_metrics.fetch_daily_reports",
            MagicMock(side_effect=[expected_org_df, expected_user_df]),
        )

        bundle = fetch_metrics_bundle(
            "token123",
            "octo-org",
            [date(2025, 1, 1)],
        )

        assert bundle.org_metrics.to_dicts() == expected_org_df.to_dicts()
        assert bundle.user_metrics.to_dicts() == expected_user_df.to_dicts()


class TestFetchDailyReports:
    def test_concatenates_specific_day_reports(self) -> None:
        api_client = MagicMock(spec=httpx.Client)
        download_client = MagicMock(spec=httpx.Client)
        report_days = [date(2025, 1, 1), date(2025, 1, 2)]

        api_client.get.side_effect = [
            _mock_httpx_response(
                json_data={"download_links": ["https://example.com/day1.ndjson"]}
            ),
            _mock_httpx_response(
                json_data={"download_links": ["https://example.com/day2.ndjson"]}
            ),
        ]
        download_client.get.side_effect = [
            _mock_httpx_response(content=_make_ndjson_bytes([{"day": "2025-01-01", "value": 1}])),
            _mock_httpx_response(content=_make_ndjson_bytes([{"day": "2025-01-02", "value": 2}])),
        ]

        df = fetch_daily_reports(
            api_client,
            download_client,
            "/orgs/test/copilot/metrics/reports/organization-1-day?day={day}",
            report_days,
        )

        assert df["day"].to_list() == ["2025-01-01", "2025-01-02"]
        assert df["value"].to_list() == [1, 2]


# ---------- save_ndjson ----------


class TestSaveNdjson:
    def test_writes_correct_format(self, tmp_path: Path) -> None:
        """DataFrame を NDJSON で書き出し、各行が有効な JSON であることを確認する。"""
        df = pl.DataFrame({"name": ["alice", "bob"], "score": [10, 20]})
        out = tmp_path / "out.ndjson"

        save_ndjson(df, out)

        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "name" in parsed
            assert "score" in parsed

        first = json.loads(lines[0])
        assert first["name"] == "alice"
        assert first["score"] == 10


class TestWriteRawMetricsBundle:
    def test_writes_both_raw_files(
        self,
        tmp_path: Path,
    ) -> None:
        bundle = RawMetricsBundle(
            org_metrics=pl.DataFrame({"day": ["2025-01-01"]}),
            user_metrics=pl.DataFrame(
                {"day": ["2025-01-01"], "user_login": ["alice"]}
            ),
        )

        output_paths = write_raw_metrics_bundle(
            bundle,
            tmp_path,
            remove_legacy_public_raw=False,
        )

        assert output_paths["org_metrics"].exists()
        assert output_paths["user_metrics"].exists()


# ---------- setup_telemetry ----------


class TestSetupTelemetry:
    def test_skips_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """接続文字列が未設定なら azure モジュールをインポートせずに返る。"""
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        client = MagicMock(spec=httpx.Client)

        with patch.dict("sys.modules", {
            "azure.monitor.opentelemetry": None,
            "opentelemetry.instrumentation.httpx": None,
        }):
            # azure モジュールが None（import 不可）の状態でもエラーにならない
            setup_telemetry(client)


# ---------- main ----------


class TestMain:
    def test_exits_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GITHUB_TOKEN / GITHUB_ORG が無い場合、SystemExit(1) で終了する。"""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_ORG", raising=False)
        # dotenv が .env を読まないように空ファイルに向ける
        monkeypatch.setattr("src.fetch_metrics.load_dotenv", lambda: None)

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
