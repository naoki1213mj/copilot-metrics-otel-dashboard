"""function_app モジュールのテスト。"""

import json
from types import SimpleNamespace

import azure.functions as func

import function_app


def make_request(
    *,
    method: str = "GET",
    params: dict[str, str] | None = None,
    body: bytes = b"",
) -> func.HttpRequest:
    """HttpRequest のテストデータを作る。"""
    return func.HttpRequest(
        method=method,
        url="https://example.com/api/test",
        params=params or {},
        body=body,
    )


def test_read_manual_run_request_parses_body() -> None:
    """body の source / writeLocalOutputs を解釈できる。"""
    request = make_request(
        method="POST",
        body=json.dumps(
            {
                "source": "mock",
                "writeLocalOutputs": True,
            }
        ).encode("utf-8"),
    )

    source_override, write_local_outputs = function_app.read_manual_run_request(request)

    assert source_override == "mock"
    assert write_local_outputs is True


def test_manual_run_returns_400_for_invalid_source() -> None:
    """source が不正なら 400 を返す。"""
    request = make_request(method="POST", params={"source": "invalid"})
    context = SimpleNamespace(invocation_id="ctx-123456")

    response = function_app.copilot_metrics_ingestion_run(request, context)

    assert response.status_code == 400
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload["status"] == "bad-request"


def test_status_route_returns_503_for_configuration_error(
    monkeypatch,
) -> None:
    """status が ready 以外の時は 503 を返す。"""
    monkeypatch.setattr(
        "function_app.get_ingestion_status",
        lambda: {
            "status": "configuration-error",
            "error": "missing storage",
        },
    )

    response = function_app.copilot_metrics_ingestion_status(make_request())

    assert response.status_code == 503
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload["error"] == "missing storage"


def test_dashboard_data_route_returns_json(monkeypatch) -> None:
    """dashboard data endpoint が JSON を返す。"""
    monkeypatch.setattr(
        "function_app.load_dashboard_snapshot_bytes",
        lambda file_name: json.dumps({"file": file_name}).encode("utf-8"),
    )
    request = make_request(params={"file_name": "daily_summary.json"})

    response = function_app.copilot_metrics_dashboard_data(request)

    assert response.status_code == 200
    payload = json.loads(response.get_body().decode("utf-8"))
    assert payload["file"] == "daily_summary.json"
