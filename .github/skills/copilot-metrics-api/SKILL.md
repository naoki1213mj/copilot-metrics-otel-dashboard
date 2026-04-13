---
name: copilot-metrics-api
description: >-
  GitHub Copilot usage metrics API（Organization レベル）のデータ取得パターン。
  エンドポイント、認証、NDJSON パース、フィールド定義をカバーする。
  「API」「メトリクス」「データ取得」「NDJSON」「fetch」のリクエストで使う。
---

# Copilot Usage Metrics API スキル

2026 年 4 月時点の公式ドキュメントに基づく。

## エンドポイント（Organization レベル）

| 用途 | メソッド | パス |
|------|---------|------|
| Org 28 日レポート | GET | `/orgs/{org}/copilot/metrics/reports/organization-28-day/latest` |
| Org 1 日レポート | GET | `/orgs/{org}/copilot/metrics/reports/organization-1-day?day=YYYY-MM-DD` |
| ユーザー 28 日レポート | GET | `/orgs/{org}/copilot/metrics/reports/users-28-day/latest` |
| ユーザー 1 日レポート | GET | `/orgs/{org}/copilot/metrics/reports/users-1-day?day=YYYY-MM-DD` |

## 認証

- PAT（classic）: `read:org` スコープ
- Fine-grained PAT: 「Organization Copilot metrics」read 権限
- ヘッダー: `Authorization: Bearer <TOKEN>`
- API バージョン: `X-GitHub-Api-Version: 2026-03-10`

## レスポンス形式

API は直接データを返さない。ダウンロードリンクの一覧を返す:

```json
{
  "download_links": [
    "https://example.com/copilot-usage-report-1.json",
    "https://example.com/copilot-usage-report-2.json"
  ],
  "report_start_day": "2026-03-01",
  "report_end_day": "2026-03-28"
}
```

- ダウンロードリンクは署名付き URL で有効期限あり
- リンク先のファイルは NDJSON 形式（1 行 = 1 JSON オブジェクト）
- 複数ファイルに分割される場合がある（スキーマは同じ）

## NDJSON パースパターン

```python
import io
import httpx
import polars as pl

def download_ndjson(client: httpx.Client, links: list[str]) -> pl.DataFrame:
    frames = []
    for link in links:
        resp = client.get(link, timeout=60)
        resp.raise_for_status()
        df = pl.read_ndjson(io.BytesIO(resp.content))
        frames.append(df)
    return pl.concat(frames) if frames else pl.DataFrame()

# 呼び出し側で httpx.Client() を作る
# with httpx.Client() as client:
#     df = download_ndjson(client, links)
```

polars は NDJSON をネイティブにパースできる。`json.loads()` のループは不要。
`httpx.Client()` を渡すのは `HTTPXClientInstrumentor` の自動計装を効かせるため（モジュール関数の `httpx.get()` は計装されない）。

## 主要フィールド（Organization レベル）

| フィールド | 説明 |
|-----------|------|
| `day` | 日付（YYYY-MM-DD） |
| `organization_id` | Organization の ID |
| `total_active_users` | アクティブユーザー数 |
| `user_initiated_interaction_count` | ユーザーが送信したプロンプト数 |
| `code_generation_activity_count` | コード生成イベント数 |
| `chat_panel_agent_mode` | Agent モードのインタラクション数 |
| `chat_panel_ask_mode` | Ask モードのインタラクション数 |
| `chat_panel_edit_mode` | Edit モードのインタラクション数 |
| `chat_panel_custom_mode` | Custom Agent のインタラクション数 |
| `agent_edit` | Agent/Edit モードでの行追加・削除 |

## 主要フィールド（ユーザーレベル）

上記に加えて:

| フィールド | 説明 |
|-----------|------|
| `user_id` | ユーザーの ID |
| `user_login` | GitHub ユーザー名 |

## 注意事項

- データは 2 日遅れ（2 full UTC days）で反映される
- Organization に 5 人以上のアクティブライセンスユーザーが必要
- IDE テレメトリが無効のユーザーはデータに含まれない
- CLI の利用データは `totals_by_cli` に別途格納される（Enterprise / User レベルのみ）
- Organization レベルのデータは 2025 年 12 月 12 日以降が取得可能

## モックデータ生成

実 API を叩けない環境（Organization の管理権限がない、など）でも動作確認できるように、`src/generate_mock.py` でモックデータを生成する。出力先は実 API と同じ NDJSON 形式にして、以降のコードが同じ経路を通るようにする。

現実的な値のレンジ目安:

| フィールド | レンジ |
|-----------|--------|
| `total_active_users` | 5〜15 |
| `user_initiated_interaction_count` | 50〜300 / 日 |
| `code_generation_activity_count` | 100〜500 / 日 |
| `chat_panel_agent_mode` | 0〜50 / 日 |
| `chat_panel_ask_mode` | 20〜100 / 日 |
| `chat_panel_edit_mode` | 10〜80 / 日 |
| `agent_edit` | 5〜30 / 日 |

28 日分の daily データと 10 人分のユーザーデータを生成する。`day` フィールドは過去 28 日の日付を入れる（実 API は 2 日遅れなので、今日-2 から遡るのが自然）。
