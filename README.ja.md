# copilot-metrics-otel-dashboard

[English version](./README.md)

GitHub Copilot usage metrics API を使って、**Python + React + Azure** で作ったダッシュボードです。  
Organization レベルの Copilot メトリクスを取得し、NDJSON をダッシュボード向け JSON に変換して、Azure App Service / Azure Functions 構成で配信します。

## このリポジトリでできること

- GitHub Copilot usage metrics API から **Organization / user メトリクス** を取得する
- **実データ** と **モックデータ** の両方に対応する
- raw NDJSON をグラフ向け JSON に変換する
- **Overview / Agent / Diagnostics** の 3 タブ UI で可視化する
- 設定時だけ Application Insights に OpenTelemetry を送る
- `azd` と Bicep で Azure にデプロイする

## 構成

```text
GitHub Copilot usage metrics API
  -> download_links
  -> 署名付き URL
  -> NDJSON

Python ingestion
  -> fetch_metrics.py
  -> transform.py
  -> generate_mock.py
  -> ingestion_runtime.py

Azure Functions
  -> 定期/手動 ingestion
  -> Blob Storage へ snapshot 保存
  -> Cosmos DB へ metadata 保存

Azure App Service
  -> React ダッシュボード配信
  -> /api/data/* を Functions にプロキシ
```

## ディレクトリ構成

| パス | 役割 |
|---|---|
| `src/fetch_metrics.py` | GitHub API から metrics を取得 |
| `src/generate_mock.py` | NDJSON のモックデータを生成 |
| `src/transform.py` | ダッシュボード用 JSON を生成 |
| `src/ingestion_runtime.py` | Azure Functions から使う ingestion 本体 |
| `function_app.py` | Azure Functions のエントリポイント |
| `dashboard/` | React + Vite のダッシュボード |
| `infra/` | Bicep テンプレート |
| `azure.yaml` | azd のサービス定義 |
| `tests/` | Python テスト |

## 前提

- `uv` で管理する Python **3.12+**
- Node.js / npm
- Azure CLI / Azure Developer CLI (`azd`)
- 実データを使う場合は Organization メトリクスにアクセスできる GitHub PAT

## 環境変数

`.env.example` を `.env` にコピーして必要な値を設定してください。

| 変数 | 必須 | 説明 |
|---|---|---|
| `GITHUB_TOKEN` | 実データ時 | ingestion で使う GitHub token |
| `GITHUB_ORG` | 実データ時 | GitHub Organization 名 |
| `COPILOT_METRICS_SOURCE` | 任意 | `github` または `mock` |
| `COPILOT_METRICS_DAYS` | 任意 | 取得/生成する日数。`1-100` |
| `METRICS_STORAGE_BLOB_ENDPOINT` | 任意 | managed identity で Blob Storage に接続する時の endpoint |
| `AZURE_COSMOS_ENDPOINT` | 任意 | managed identity で Cosmos DB に接続する時の endpoint |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | 任意 | 設定すると OpenTelemetry を送る |
| `INGESTION_TIMER_SCHEDULE` | 任意 | Azure Functions の timer trigger |

完全な一覧は `.env.example` を見てください。

## ローカルセットアップ

### 1. 依存関係を入れる

```powershell
uv sync
Set-Location dashboard
npm install
Set-Location ..
```

### 2. データを用意する

**モックデータを使う場合**

```powershell
uv run src/generate_mock.py
uv run src/transform.py
```

**GitHub の実データを使う場合**

```powershell
uv run src/fetch_metrics.py
uv run src/transform.py
```

### 3. ダッシュボードを起動する

```powershell
Set-Location dashboard
npm run dev
```

ローカルの Vite アプリは `dashboard/public/data/` の JSON を読み込みます。

## よく使うコマンド

| コマンド | 目的 |
|---|---|
| `uv run ruff check .` | Python の lint |
| `uv run pytest` | Python テスト実行 |
| `cd dashboard && npm run build` | ダッシュボードのビルド |
| `az bicep build --file infra\main.bicep` | Bicep のコンパイル確認 |

## リリース前チェックリスト

Zenn の検証記事を更新する前や、検証結果を公開する前に次を確認します。

### ローカル確認

1. `uv run ruff check .`
2. `uv run pytest tests\ -v`
3. `cd dashboard && npm run build`
4. `az bicep build --file infra\main.bicep`

### Azure 上の mock 検証

1. 最新コードを Azure にデプロイする
2. `POST /api/ingestion/run` に `{"source":"mock"}` を送る
3. `GET /api/ingestion/status` が `ready` を返すことを確認する
4. `GET /api/data/daily_summary.json` が `200` を返すことを確認する
5. App Service のダッシュボードが `200` を返すことを確認する

### このチェックで確認できること

- Azure App Service と Azure Functions の両方が生きている
- mock データで ingestion が end-to-end で動く
- ダッシュボード用 JSON が生成・配信できる
- 実データを使わなくても、Azure 実機検証の記事が書ける

## ダッシュボードの見どころ

- **Overview**: DAU、prompt trend、language mix、全体傾向
- **Agent**: Agent 系の利用シグナルと日次トレンド
- **Diagnostics**: コード生成、acceptance、review engagement、ユーザー分析

## Azure デプロイ

このリポジトリは `azd` で 2 つのサービスを扱います。

- `dashboard` -> Azure App Service
- `ingestion` -> Azure Functions

基本の流れは次のとおりです。

```powershell
azd env new <environment-name>
azd env set --file .env
azd provision
azd deploy
```

Azure にデプロイする Function App は、既定で **mock データ** を使い、Storage / Cosmos DB へは connection string ではなく **managed identity** で接続するようにしてあります。shared key や local auth が禁止された subscription でも動かしやすくするためです。

## OpenTelemetry

`APPLICATIONINSIGHTS_CONNECTION_STRING` が設定されている場合だけ:

- `configure_azure_monitor()` を有効化
- `HTTPXClientInstrumentor` で `httpx.Client()` を自動計装

接続文字列が無い場合は、Azure Monitor を使わずにそのまま動きます。

## 補足とトラブルシュート

- GitHub Copilot usage metrics API は最終データをそのまま返さず、まず `download_links` を返します。実データは署名付き URL 先の NDJSON です。
- 100 日表示は単一 endpoint ではなく、**1-day report** を日ごとに集めて作っています。
- Windows では `azd` が Python を見つけられないことがあるので、`.venv\Scripts` を `PATH` に通しておくと安全です。
- App Service の quota は **リージョンごと** です。あるリージョンで quota に当たっても、別リージョンでは通ることがあります。
- 一部の enterprise subscription では **Storage の shared key auth** や **Cosmos DB の local auth** が無効化されています。このリポジトリの Azure 構成は、Function host storage / Blob / Cosmos DB を **managed identity** で扱い、Azure 上では **mock-only ingestion** を既定にしています。

## 関連ファイル

- Azure サービス定義: [`azure.yaml`](./azure.yaml)
- 環境変数サンプル: [`.env.example`](./.env.example)
