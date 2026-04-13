---
name: 'Python httpx ルール'
description: 'Python コードの規約。httpx, polars, uv を使う'
applyTo: 'src/**/*.py, tests/**/*.py'
---

## Python ルール

- パッケージ管理は uv。`pip install` や `requirements.txt` を使わない
- リンター・フォーマッターは ruff
- 型ヒント必須。`str | None` 形式を使う
- docstring は日本語で書く。変数名・関数名は英語
- エラーは具体的な例外型で catch する

## httpx

- 非同期が不要なら `httpx.Client()` を使う（`httpx.get()` などのモジュール関数は OTel 計装が効かないので避ける）
- タイムアウトは明示的に設定する（`timeout=30`）
- `response.raise_for_status()` でエラーチェックする

## GitHub API 呼び出し

- API バージョンヘッダー: `X-GitHub-Api-Version: 2026-03-10`
- レスポンスは `download_links` を含む JSON → リンク先は NDJSON
- NDJSON は `pl.read_ndjson(io.BytesIO(response.content))` で直接 DataFrame 化する（手動ループは不要）
- ダウンロードリンクは署名付き URL で有効期限あり。取得後すぐにダウンロードする

## polars

- NDJSON のパースは `pl.read_ndjson(io.BytesIO(content))` を使う
- 存在しないカラムへのアクセスは `ColumnNotFoundError` になるので、事前に `with_columns(pl.lit(0).alias(col))` で対処する
- `group_by` + `agg` で集計する（pandas の `groupby` ではない）
- JSON 出力は `df.write_json()` で行指向 JSON を出力する（Polars v1 ではデフォルトが行指向）
- `df.to_dicts()` + `json.dumps()` も使える

## httpx の OTel 計装

- `opentelemetry-instrumentation-httpx` を使って httpx の HTTP 呼び出しを自動トレースする
- クラス名は `HTTPXClientInstrumentor`（末尾 -or）。`HTTPXClientInstrumentation` ではない
- `HTTPXClientInstrumentor().instrument()` で有効化する
- `configure_azure_monitor()` だけでは httpx は計装されない。明示的にインストルメンターを追加する
- 自動計装は `httpx.Client()` インスタンス経由の呼び出しにのみ効く。`httpx.get()` などのモジュール関数は計装されない
