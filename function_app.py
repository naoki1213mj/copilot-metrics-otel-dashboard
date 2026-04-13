"""Azure Functions のエントリポイント。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import azure.functions as func
from dotenv import load_dotenv

if TYPE_CHECKING:
    from src.ingestion_runtime import SourceType

load_dotenv()

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def parse_bool_value(raw_value: str) -> bool:
    """真偽値文字列を runtime 実装で解釈する。"""
    from src.ingestion_runtime import parse_bool_value as runtime_parse_bool_value

    return runtime_parse_bool_value(raw_value)


def parse_source(raw_source: str) -> SourceType:
    """source 指定を runtime 実装で解釈する。"""
    from src.ingestion_runtime import parse_source as runtime_parse_source

    return runtime_parse_source(raw_source)


def json_response_body(payload: object) -> str:
    """JSON レスポンス本文を runtime 実装で組み立てる。"""
    from src.ingestion_runtime import json_response_body as runtime_json_response_body

    return runtime_json_response_body(payload)


def run_ingestion(
    *,
    trigger: str,
    source_override: SourceType | None = None,
    write_local_outputs_override: bool | None = None,
    invocation_id: str | None = None,
) -> dict[str, object]:
    """ingestion 実行を runtime 実装へ委譲する。"""
    from src.ingestion_runtime import run_ingestion as runtime_run_ingestion

    return runtime_run_ingestion(
        trigger=trigger,
        source_override=source_override,
        write_local_outputs_override=write_local_outputs_override,
        invocation_id=invocation_id,
    )


def get_ingestion_status() -> dict[str, object]:
    """ingestion 状態取得を runtime 実装へ委譲する。"""
    from src.ingestion_runtime import get_ingestion_status as runtime_get_ingestion_status

    return runtime_get_ingestion_status()


def load_dashboard_snapshot_bytes(file_name: str) -> bytes:
    """dashboard スナップショット取得を runtime 実装へ委譲する。"""
    from src.ingestion_runtime import (
        load_dashboard_snapshot_bytes as runtime_load_dashboard_snapshot_bytes,
    )

    return runtime_load_dashboard_snapshot_bytes(file_name)


def read_manual_run_request(
    req: func.HttpRequest,
) -> tuple[SourceType | None, bool | None]:
    """手動実行用のオプションを HTTP リクエストから読む。"""
    request_body: dict[str, object] = {}
    try:
        parsed_body = req.get_json()
    except ValueError:
        parsed_body = None
    if isinstance(parsed_body, dict):
        request_body = parsed_body

    raw_source = req.params.get("source")
    if raw_source is None and "source" in request_body:
        body_source = request_body.get("source")
        if body_source is None:
            raw_source = None
        elif isinstance(body_source, str):
            raw_source = body_source
        else:
            raise ValueError("source は文字列で指定してください。")

    source_override = parse_source(raw_source) if raw_source is not None else None

    raw_write_local_outputs = req.params.get("writeLocalOutputs")
    if raw_write_local_outputs is None and "writeLocalOutputs" in request_body:
        body_value = request_body.get("writeLocalOutputs")
        if body_value is None:
            return source_override, None
        if isinstance(body_value, bool):
            return source_override, body_value
        if isinstance(body_value, str):
            return source_override, parse_bool_value(body_value)
        raise ValueError("writeLocalOutputs は真偽値で指定してください。")

    if raw_write_local_outputs is None:
        return source_override, None
    return source_override, parse_bool_value(raw_write_local_outputs)


def read_requested_snapshot_file(req: func.HttpRequest) -> str:
    """スナップショット取得対象のファイル名を解釈する。"""
    route_params = getattr(req, "route_params", None)
    if isinstance(route_params, dict):
        route_file_name = route_params.get("file_name")
        if isinstance(route_file_name, str) and route_file_name:
            return route_file_name
    query_file_name = req.params.get("file_name")
    if query_file_name:
        return query_file_name
    return req.url.rstrip("/").split("/")[-1]


@app.function_name(name="copilotMetricsIngestionTimer")
@app.timer_trigger(
    schedule=os.getenv("INGESTION_TIMER_SCHEDULE", "0 15 2 * * *"),
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
@app.retry(strategy="fixed_delay", max_retry_count="3", delay_interval="00:05:00")
def copilot_metrics_ingestion_timer(
    timer: func.TimerRequest,
    context: func.Context,
) -> None:
    """定期 ingestion を実行する。"""
    if timer.past_due:
        logger.warning("タイマー実行が遅延しています。")
    run_ingestion(trigger="timer", invocation_id=context.invocation_id)


@app.function_name(name="copilotMetricsIngestionRun")
@app.route(route="ingestion/run", methods=["POST"])
def copilot_metrics_ingestion_run(
    req: func.HttpRequest,
    context: func.Context,
) -> func.HttpResponse:
    """HTTP 経由で ingestion を手動実行する。"""
    from azure.core.exceptions import AzureError
    from azure.cosmos import exceptions as cosmos_exceptions
    import httpx
    import polars as pl

    try:
        source_override, write_local_outputs = read_manual_run_request(req)
        result = run_ingestion(
            trigger="http",
            source_override=source_override,
            write_local_outputs_override=write_local_outputs,
            invocation_id=context.invocation_id,
        )
    except ValueError as exc:
        return func.HttpResponse(
            json_response_body(
                {
                    "status": "bad-request",
                    "error": str(exc),
                }
            ),
            status_code=400,
            mimetype="application/json",
        )
    except (
        OSError,
        httpx.HTTPError,
        pl.exceptions.PolarsError,
        AzureError,
        cosmos_exceptions.CosmosHttpResponseError,
    ) as exc:
        logger.exception("手動 ingestion に失敗しました。")
        return func.HttpResponse(
            json_response_body(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            ),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json_response_body(result),
        status_code=200,
        mimetype="application/json",
    )


@app.function_name(name="copilotMetricsIngestionStatus")
@app.route(route="ingestion/status", methods=["GET"])
def copilot_metrics_ingestion_status(_req: func.HttpRequest) -> func.HttpResponse:
    """現在の設定と最新実行結果を返す。"""
    payload = get_ingestion_status()
    status_code = 200 if payload.get("status") == "ready" else 503
    return func.HttpResponse(
        json_response_body(payload),
        status_code=status_code,
        mimetype="application/json",
    )


@app.function_name(name="copilotMetricsDashboardData")
@app.route(
    route="data/{file_name}",
    methods=["GET", "HEAD"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def copilot_metrics_dashboard_data(req: func.HttpRequest) -> func.HttpResponse:
    """最新の dashboard JSON スナップショットを返す。"""
    from azure.core.exceptions import AzureError

    file_name = read_requested_snapshot_file(req)
    try:
        body = load_dashboard_snapshot_bytes(file_name)
    except ValueError:
        return func.HttpResponse(status_code=404)
    except FileNotFoundError as exc:
        return func.HttpResponse(str(exc), status_code=404)
    except AzureError as exc:
        logger.exception("dashboard data の取得に失敗しました。")
        return func.HttpResponse(str(exc), status_code=500)

    return func.HttpResponse(
        body if req.method != "HEAD" else b"",
        status_code=200,
        mimetype="application/json",
    )
