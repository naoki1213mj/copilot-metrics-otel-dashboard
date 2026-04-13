"""fetch_metrics.py のユニットテスト。

すべての HTTP 通信を mock し、ネットワークアクセスなしでテストする。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

pl = pytest.importorskip("polars")

from src.fetch_metrics import (
    build_api_client,
    build_download_client,
    download_ndjson,
    fetch_report,
    main,
    save_ndjson,
    setup_telemetry,
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
        assert h["accept"] == "application/json"
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

        df = fetch_report(api_client, dl_client, "/orgs/test/copilot/metrics/reports/organization-28-day/latest")

        assert len(df) == 1
        assert df["day"][0] == "2025-01-01"
        assert df["total_acceptances_count"][0] == 42

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
