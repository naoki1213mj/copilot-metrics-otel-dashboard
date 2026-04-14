# copilot-metrics-otel-dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

[日本語版はこちら](./README.ja.md)

A GitHub Copilot usage metrics dashboard built with **Python + React + Azure**.  
It fetches organization-level Copilot metrics, transforms the raw NDJSON into dashboard-friendly JSON, and serves a tabbed UI backed by Azure App Service and Azure Functions.

## Architecture

![Architecture](./articles/images/architecture.png)

## Screenshots

### Overview tab

![Overview](./articles/images/overview.png)

DAU trends, prompt volume, acceptance rate, language breakdown.

### Agent tab

![Agent](./articles/images/agent.png)

Agent adoption, mode breakdown (Ask / Edit / Agent), coding agent active users.

### Diagnostics tab

![Diagnostics](./articles/images/diagnostics.png)

User-level activity, review engagement, code generation volume.

## What this project does

- Fetches **organization** and **user** metrics from the GitHub Copilot usage metrics API
- Supports both **live GitHub data** and **mock data**
- Transforms raw NDJSON into JSON files for charts and tables
- Renders a dashboard with **Overview**, **Agent**, and **Diagnostics** tabs
- Emits OpenTelemetry traces to Application Insights when configured
- Deploys to Azure with **azd**, **Bicep**, **App Service**, **Azure Functions**, **Blob Storage**, **Cosmos DB**, **Key Vault**, **Application Insights**, and **Log Analytics**

## Architecture (text)

```text
GitHub Copilot usage metrics API
  -> download_links
  -> signed URLs
  -> NDJSON

Python ingestion
  -> fetch_metrics.py
  -> transform.py
  -> generate_mock.py
  -> ingestion_runtime.py

Azure Functions
  -> scheduled/manual ingestion
  -> Blob Storage snapshots
  -> Cosmos DB metadata

Azure App Service
  -> React dashboard
  -> /api/data/* proxy to Functions
```

## Repository layout

| Path | Purpose |
|---|---|
| `src/fetch_metrics.py` | Fetches Copilot metrics from GitHub |
| `src/generate_mock.py` | Generates realistic mock NDJSON |
| `src/transform.py` | Builds dashboard JSON files |
| `src/ingestion_runtime.py` | Shared ingestion workflow for Azure Functions |
| `function_app.py` | Azure Functions entry point |
| `dashboard/` | React + Vite dashboard |
| `infra/` | Bicep templates |
| `azure.yaml` | azd service definition |
| `tests/` | Python test suite |

## Prerequisites

- Python **3.12+** managed with `uv`
- Node.js and npm
- Azure CLI and Azure Developer CLI (`azd`) for cloud deployment
- A GitHub Personal Access Token with access to your organization metrics when using live data

## Environment variables

Copy `.env.example` to `.env` and update the values you need.

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | For live data | GitHub token used by the ingestion job |
| `GITHUB_ORG` | For live data | GitHub organization name |
| `COPILOT_METRICS_SOURCE` | No | `github` or `mock` |
| `COPILOT_METRICS_DAYS` | No | Number of days to fetch/build, `1-100` |
| `METRICS_STORAGE_BLOB_ENDPOINT` | Optional | Blob endpoint for managed-identity-based remote persistence |
| `AZURE_COSMOS_ENDPOINT` | Optional | Cosmos endpoint for managed-identity-based remote persistence |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional | Enables OpenTelemetry export |
| `INGESTION_TIMER_SCHEDULE` | Optional | Azure Functions timer schedule |

See `.env.example` for the full list.

## Local setup

### 1. Install dependencies

```powershell
uv sync
Set-Location dashboard
npm install
Set-Location ..
```

### 2. Create local data

**Mock data**

```powershell
uv run src/generate_mock.py
uv run src/transform.py
```

**Live GitHub data**

```powershell
uv run src/fetch_metrics.py
uv run src/transform.py
```

### 3. Run the dashboard

```powershell
Set-Location dashboard
npm run dev
```

The local Vite app reads JSON files from `dashboard/public/data/`.

## Useful commands

| Command | Purpose |
|---|---|
| `uv run ruff check .` | Lint Python code |
| `uv run pytest` | Run Python tests |
| `cd dashboard && npm run build` | Build the dashboard |
| `az bicep build --file infra\main.bicep` | Validate Bicep compilation |

## Release checklist

Use this checklist before publishing a new validation result or updating the Zenn article.

### Local validation

1. `uv run ruff check .`
2. `uv run pytest tests\ -v`
3. `cd dashboard && npm run build`
4. `az bicep build --file infra\main.bicep`

### Azure validation with mock data

1. Deploy the latest code to Azure
2. Call `POST /api/ingestion/run` with `{"source":"mock"}`
3. Confirm `GET /api/ingestion/status` returns `ready`
4. Confirm `GET /api/data/daily_summary.json` returns `200`
5. Confirm the App Service dashboard returns `200`

### What this checklist proves

- Azure App Service and Azure Functions are both alive
- The ingestion path works end to end with mock data
- Dashboard JSON snapshots are written and served correctly
- The article can describe a working Azure validation flow without using live organization data

## Dashboard tabs

- **Overview**: DAU, prompt trends, top language mix, high-level adoption
- **Agent**: Agent-related usage signals and organization trends
- **Diagnostics**: Code generation, acceptance, review engagement, and user-level analysis

## Azure deployment

This repository uses `azd` with two services:

- `dashboard` -> Azure App Service
- `ingestion` -> Azure Functions

Typical workflow:

```powershell
azd env new <environment-name>
azd env set --file .env
azd provision
azd deploy
```

The Azure Function app is configured to use **mock data by default** and accesses Storage/Cosmos through **managed identity** instead of connection strings. This keeps the deployment compatible with subscriptions that block shared-key and local-auth access.

## OpenTelemetry

When `APPLICATIONINSIGHTS_CONNECTION_STRING` is set:

- `configure_azure_monitor()` is enabled
- `HTTPXClientInstrumentor` instruments `httpx.Client()` calls

When the connection string is absent, the ingestion code runs without Azure Monitor setup.

## Notes and troubleshooting

- The GitHub Copilot usage metrics API returns **download links**, not the final dataset directly. The raw data is NDJSON behind signed URLs.
- The 100-day view is built from repeated **1-day report** fetches instead of a single 100-day endpoint.
- On Windows, `azd` may need `.venv\Scripts` on `PATH` so that Python can be resolved correctly.
- App Service quota is **region-specific**. If one region fails with an App Service quota error, another region may still work.
- Some enterprise subscriptions disable **Storage shared key auth** and **Cosmos local auth**. This repo's Azure path now uses **managed identity** for Function host storage, Blob artifact access, and Cosmos DB access, and it defaults to **mock-only ingestion** in Azure.

## Related files

- Azure service definition: [`azure.yaml`](./azure.yaml)
- Example environment file: [`.env.example`](./.env.example)

## License

This project is licensed under the [MIT License](./LICENSE).
