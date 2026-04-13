---
title: "Copilot CLI で Copilot メトリクスダッシュボードを自作した話"
emoji: "📊"
type: "tech"
topics: ["GitHubCopilot", "Python", "React", "Azure"]
published: false
---

こんにちは、日本マイクロソフトの中尾です。

この記事は [GitHub Copilot 活用選手権](https://zenn.dev/contests/github-2026-spring)への投稿です。

2026年4月2日に、GitHub Copilot のレガシーな Metrics API（`/orgs/{org}/copilot/metrics`）がサンセットしました。代わりに登場したのが Copilot usage metrics API で、2026年2月27日に GA になっています。

Microsoft が公開しているダッシュボードのリポジトリ（[microsoft/copilot-metrics-dashboard](https://github.com/microsoft/copilot-metrics-dashboard)）もこの影響を受けていて、Issue #87 で新 API への対応が議論されています。

で、せっかくなら新しい API を理解しながら自前のダッシュボードを作ってみよう、しかも開発プロセス自体に GitHub Copilot CLI を使ってみよう、というのがこの記事の趣旨です。

:::message
本記事は 2026 年 4 月時点の公式ドキュメントをもとにしています。
Copilot usage metrics API は GA 直後のため、今後フィールドやエンドポイントが変わる可能性があります。

また、本記事のダッシュボードには API のフィールド定義に準拠したモックデータを使っています。所属 Organization の管理権限の都合で実データでの動作は未検証です。API 仕様の理解と Copilot CLI での開発体験の共有が主目的のため、モックデータでも内容が成立するように書いています。実データへの差し替えは `fetch_metrics.py` を使う経路を用意しているので、権限が揃った環境ではそのまま動くはずです。
:::

## なぜ Copilot CLI で作ったか

今回は開発のほぼ全工程を GitHub Copilot CLI で進めました。具体的にはこんな流れです。

リポジトリを作ったらまず `/init` でプロジェクトの構造を認識させて、`copilot-instructions.md` を生成しました。そこから「新しい Copilot usage metrics API のエンドポイント仕様を確認して、Python でデータ取得スクリプトを書いて」と自然言語で指示を出すと、API ドキュメントを参照しながらコードを生成してくれます。

正直なところ、API のレスポンスが NDJSON（後述します）という少し変わった形式で、公式ドキュメントを読んだ最初の段階で「これ `response.json()` では読めないやつだ」と気づくのに時間がかかりました。Copilot CLI に「新 API のレスポンス形式を公式ドキュメントで確認して、正しいパースコードを書いて」と指示したら、NDJSON 用の処理を最初から書いてくれたので、私が最初に陥った勘違いは回避できました。AGENTS.md に「間違えやすい API」テーブルを書いておいたのが効いた場面です。

カスタム命令（AGENTS.md、instructions、skills）をあらかじめ整備しておくと、プロジェクト固有の文脈を Copilot CLI が理解した状態で動いてくれるので、指示の精度がかなり上がります。この記事の後半で触れるコードも、大部分は Copilot CLI とのやり取りの中で書いたものです。

## この記事で作るもの

Organization レベルの Copilot 利用データを取得して、こんなダッシュボードを作ります。

- 日別アクティブユーザー数（DAU）の推移
- Agent モード / Ask モード / Edit モードの利用比率
- ユーザーごとの利用状況

技術スタックはこうなっています。

| 層 | 技術 | 役割 |
|---|---|---|
| データ取得 | Python（httpx） | API 呼び出し |
| データ加工 | Python（polars） | NDJSON パース・集計・JSON 出力 |
| 可観測性 | OpenTelemetry + Application Insights | データパイプラインのトレース・監視 |
| フロントエンド | React（Vite + Recharts） | グラフ描画 |
| 開発ツール | GitHub Copilot CLI | コード生成・エラー修正・レビュー |

## 新旧 API の違い

まず、何が変わったのかを整理します。

| | レガシー API（サンセット済み） | 新 API（GA） |
|---|---|---|
| エンドポイント | `/orgs/{org}/copilot/metrics` | `/orgs/{org}/copilot/metrics/reports/organization-28-day/latest` |
| レスポンス形式 | JSON 配列がそのまま返る | ダウンロードリンクが返る → リンク先が NDJSON |
| データ保持期間 | 直近 100 日 | 28 日（1日単位の取得も可能） |
| スコープ | Organization / Team | Enterprise / Organization / User |
| Agent モードの指標 | なし | あり（agent_edit, chat_panel_agent_mode など） |
| API バージョン | `2022-11-28` | `2026-03-10` |

いちばん大きな変化は、レスポンスの形式です。レガシー API は JSON 配列をそのまま返してくれたので、`response.json()` で終わりでした。新 API は「ダウンロードリンクの一覧」を返してきて、そのリンク先にある NDJSON ファイルを自分で取得・パースする必要があります。

NDJSON（Newline-Delimited JSON）は、1 行が 1 つの JSON オブジェクトになっている形式です。で、ここが今回いちばん驚いたところなんですが、polars には `pl.read_ndjson()` という関数があって、NDJSON をネイティブに DataFrame として読み込めます。手動で 1 行ずつ `json.loads()` する必要がありません。

## 前提条件

この記事の手順を試すには、以下が必要です。

- GitHub Organization で Copilot Business または Enterprise ライセンスが有効であること
- Enterprise の AI Controls で「Copilot usage metrics」ポリシーが Enabled になっていること
- Organization オーナー権限、またはカスタムロールで「View Organization Copilot Metrics」権限を持っていること
- Personal Access Token（classic）に `read:org` スコープが付与されていること

ポリシーの有効化は Enterprise 管理者の操作が必要です。自分の Organization で試せない場合は、後述するモックデータを使って動作確認できます。

## 環境構築

Python 側のプロジェクトを `uv` で作ります。Python は 2025 年 10 月にリリースされた 3.14 を使います（2026 年 4 月時点の安定版は 3.14.4）。

```bash:ターミナル
mkdir copilot-metrics && cd copilot-metrics
uv init --python 3.14
uv add httpx polars python-dotenv azure-monitor-opentelemetry opentelemetry-instrumentation-httpx
```

`azure-monitor-opentelemetry` は Microsoft が提供する OpenTelemetry のディストロで、`configure_azure_monitor()` を 1 行呼ぶだけで Application Insights へのトレース送信が有効になります。httpx の HTTP 呼び出しを自動トレースするために `opentelemetry-instrumentation-httpx` も入れています。

フロントエンドは別ディレクトリで Vite + React を立ち上げます。

```bash:ターミナル
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install recharts
```

最終的なディレクトリ構成はこんな感じです。

```
copilot-metrics/
├── src/
│   ├── fetch_metrics.py    # API からデータ取得
│   ├── transform.py        # データ加工・JSON 出力
│   └── generate_mock.py    # モックデータ生成
├── dashboard/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   └── types.ts
│   └── public/data/        # Python が出力した JSON
├── articles/               # この記事
├── .github/                # Copilot カスタム命令
├── pyproject.toml
└── .env
```

## Python でデータを取得する

### API 呼び出し

まず `.env` にトークンと Organization 名を設定します。

```bash:.env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_ORG=your-org-name
```

データ取得のスクリプトです。polars の `read_ndjson` を使って、ダウンロードした NDJSON を直接 DataFrame に変換しています。

```python:src/fetch_metrics.py
"""Copilot usage metrics API からデータを取得する。OTel でトレースを収集する。"""

import io
import os
from pathlib import Path

import httpx
import polars as pl
from dotenv import load_dotenv
from opentelemetry import trace

load_dotenv()

# OTel の初期化（Application Insights の接続文字列が設定されている場合のみ有効化）
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    configure_azure_monitor(connection_string=connection_string)
    HTTPXClientInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_ORG = os.environ["GITHUB_ORG"]
API_BASE = "https://api.github.com"
API_VERSION = "2026-03-10"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": API_VERSION,
}


def fetch_report_links(client: httpx.Client, report_type: str) -> dict:
    """レポートのダウンロードリンクを取得する。"""
    with tracer.start_as_current_span(
        "fetch_report_links", attributes={"report_type": report_type}
    ):
        url = f"{API_BASE}/orgs/{GITHUB_ORG}/copilot/metrics/reports/{report_type}/latest"
        response = client.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()


def download_ndjson(client: httpx.Client, download_links: list[str]) -> pl.DataFrame:
    """ダウンロードリンクから NDJSON を取得して polars DataFrame にする。"""
    frames = []
    with tracer.start_as_current_span(
        "download_ndjson", attributes={"link_count": len(download_links)}
    ):
        for i, link in enumerate(download_links):
            with tracer.start_as_current_span(
                f"download_file_{i}", attributes={"file_index": i}
            ):
                response = client.get(link, timeout=60)
                response.raise_for_status()
                df = pl.read_ndjson(io.BytesIO(response.content))
                frames.append(df)

    if not frames:
        return pl.DataFrame()

    return pl.concat(frames)


def save_json(df: pl.DataFrame, output_path: Path) -> None:
    """DataFrame を JSON ファイルとして保存する。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(df.write_json())
    print(f"保存しました: {output_path} ({df.height} 件)")


def main() -> None:
    output_dir = Path("dashboard/public/data")

    with tracer.start_as_current_span("fetch_all_metrics"):
        # httpx.Client を使うと HTTPXClientInstrumentor による自動計装が効く
        with httpx.Client() as client:
            # Organization レベルの 28 日レポートを取得
            print("Organization レポートを取得中...")
            org_report = fetch_report_links(client, "organization-28-day")
            org_df = download_ndjson(client, org_report["download_links"])
            save_json(org_df, output_dir / "daily.json")
            print(
                f"  期間: {org_report.get('report_start_day')} 〜 {org_report.get('report_end_day')}"
            )

            # ユーザーレベルの 28 日レポートを取得
            print("ユーザーレポートを取得中...")
            users_report = fetch_report_links(client, "users-28-day")
            users_df = download_ndjson(client, users_report["download_links"])
            save_json(users_df, output_dir / "users.json")

    print("完了！")


if __name__ == "__main__":
    main()
```

`configure_azure_monitor()` で Application Insights へのエクスポートを有効化し、`HTTPXClientInstrumentor().instrument()` で httpx の HTTP リクエストを自動トレースします。ここに加えて、`tracer.start_as_current_span()` でカスタムスパンを入れています。API からレポートリンクを取得する処理、NDJSON ファイルのダウンロード、全体の処理を個別のスパンとして記録するので、Application Insights のトランザクション検索で「どのステップで時間がかかったか」「エラーがどこで発生したか」が分かります。

`APPLICATIONINSIGHTS_CONNECTION_STRING` が `.env` に設定されていなければ OTel は有効化されないので、ローカルでモックデータを使うときはそのまま動きます。

### polars で NDJSON を読む

ここが pandas との一番の違いです。レガシー API 時代に pandas を使っていた人は、こんなコードを書いていたはずです。

```python
# pandas の場合: 手動で 1 行ずつパースする必要がある
import json
records = []
for line in response.text.strip().splitlines():
    records.append(json.loads(line))
df = pd.DataFrame(records)
```

polars なら、`read_ndjson` に `BytesIO` を渡すだけです。

```python
# polars の場合: ネイティブに NDJSON をパースできる
import io
import polars as pl
df = pl.read_ndjson(io.BytesIO(response.content))
```

内部的には Rust で並列パースしているので、大きなデータでも高速です。今回のユースケースでは数百行程度なのでパフォーマンス差は体感できませんが、コードがシンプルになるのは嬉しいです。

### ダウンロードリンクで気をつけること

新 API のレスポンスで戸惑ったのが、ダウンロードリンクが複数返ってくる場合があることです。

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

report-1 と report-2 でスキーマが違うのかと思いましたが、そうではなく、どちらも同じフィールド構造の NDJSON です。データ量が多いと分割されるだけなので、`pl.concat()` で結合すれば OK です。

ダウンロードリンクは署名付き URL で有効期限があるので、取得したらすぐにダウンロードしてください。

## データを加工する

API から取得した生データを、React 側で扱いやすい形に変換します。

```python:src/transform.py
"""取得した NDJSON データをダッシュボード用に加工する。"""

import json
from pathlib import Path

import polars as pl


def load_daily(path: Path) -> pl.DataFrame:
    return pl.read_json(path)


def build_daily_summary(df: pl.DataFrame) -> list[dict]:
    """日別のサマリーを作る。DAU と各モードの利用回数。"""
    if df.is_empty():
        return []

    mode_cols = [
        "chat_panel_agent_mode",
        "chat_panel_ask_mode",
        "chat_panel_edit_mode",
        "chat_panel_custom_mode",
    ]

    # 存在しないカラムは 0 で埋める
    for col in mode_cols + ["total_active_users", "user_initiated_interaction_count"]:
        if col not in df.columns:
            df = df.with_columns(pl.lit(0).alias(col))

    summary = (
        df.group_by("day")
        .agg(
            pl.col("total_active_users").sum().alias("active_users"),
            pl.col("user_initiated_interaction_count").sum().alias("interactions"),
            *[pl.col(c).sum().alias(c) for c in mode_cols],
        )
        .sort("day")
    )

    return summary.to_dicts()


def build_user_summary(df: pl.DataFrame) -> list[dict]:
    """ユーザーごとの利用サマリーを作る。"""
    if df.is_empty():
        return []

    # 存在しないカラムは 0 で埋める
    for col in [
        "user_initiated_interaction_count",
        "code_generation_activity_count",
        "chat_panel_agent_mode",
    ]:
        if col not in df.columns:
            df = df.with_columns(pl.lit(0).alias(col))

    summary = (
        df.group_by("user_login")
        .agg(
            pl.col("day").n_unique().alias("active_days"),
            pl.col("user_initiated_interaction_count").sum().alias("total_interactions"),
            pl.col("code_generation_activity_count")
            .sum()
            .alias("total_code_generations"),
            pl.col("chat_panel_agent_mode")
            .sum()
            .alias("agent_mode_interactions"),
        )
        .sort("total_interactions", descending=True)
        .rename({"user_login": "user"})
    )

    return summary.to_dicts()


def main() -> None:
    data_dir = Path("dashboard/public/data")

    daily_df = load_daily(data_dir / "daily.json")
    daily_summary = build_daily_summary(daily_df)
    (data_dir / "daily_summary.json").write_text(
        json.dumps(daily_summary, ensure_ascii=False, indent=2)
    )
    print(f"日別サマリー: {len(daily_summary)} 日分")

    users_df = load_daily(data_dir / "users.json")
    user_summary = build_user_summary(users_df)
    (data_dir / "user_summary.json").write_text(
        json.dumps(user_summary, ensure_ascii=False, indent=2)
    )
    print(f"ユーザーサマリー: {len(user_summary)} 人分")


if __name__ == "__main__":
    main()
```

:::message
フィールド名（`total_active_users`、`chat_panel_agent_mode` など）は、2026 年 4 月時点の公式ドキュメント「[Data available in Copilot usage metrics](https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics)」に記載されているものです。Organization レベルのレポートで実際に返ってくるフィールドは、環境によって異なる場合があります。存在しないカラムに対応するため、`with_columns(pl.lit(0))` でフォールバックしています。
:::

### モックデータで動作確認する

実際の API を叩ける環境がない場合、こんなモックデータで動作確認できます。

```python:src/generate_mock.py
"""ダッシュボード動作確認用のモックデータを生成する。"""

import json
import random
from datetime import date, timedelta
from pathlib import Path


def generate_mock_daily(days: int = 28) -> list[dict]:
    records = []
    start = date.today() - timedelta(days=days)

    for i in range(days):
        d = start + timedelta(days=i)
        is_weekday = d.weekday() < 5
        base_users = random.randint(15, 25) if is_weekday else random.randint(3, 8)

        records.append(
            {
                "day": d.isoformat(),
                "total_active_users": base_users,
                "user_initiated_interaction_count": base_users * random.randint(5, 15),
                "code_generation_activity_count": base_users * random.randint(3, 10),
                "chat_panel_agent_mode": random.randint(5, base_users),
                "chat_panel_ask_mode": random.randint(10, base_users * 2),
                "chat_panel_edit_mode": random.randint(2, base_users),
                "chat_panel_custom_mode": random.randint(0, 3),
            }
        )

    return records


def generate_mock_users(num_users: int = 20) -> list[dict]:
    records = []
    names = [f"dev-{i:02d}" for i in range(1, num_users + 1)]

    for name in names:
        days = random.randint(5, 28)
        start = date.today() - timedelta(days=28)

        for _ in range(days):
            d = start + timedelta(days=random.randint(0, 27))
            records.append(
                {
                    "day": d.isoformat(),
                    "user_login": name,
                    "user_initiated_interaction_count": random.randint(1, 30),
                    "code_generation_activity_count": random.randint(0, 20),
                    "chat_panel_agent_mode": random.randint(0, 10),
                    "chat_panel_ask_mode": random.randint(0, 15),
                    "chat_panel_edit_mode": random.randint(0, 5),
                }
            )

    return records


def main() -> None:
    output_dir = Path("dashboard/public/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    daily = generate_mock_daily()
    (output_dir / "daily.json").write_text(
        json.dumps(daily, ensure_ascii=False, indent=2)
    )
    print(f"モック日別データ: {len(daily)} 件")

    users = generate_mock_users()
    (output_dir / "users.json").write_text(
        json.dumps(users, ensure_ascii=False, indent=2)
    )
    print(f"モックユーザーデータ: {len(users)} 件")


if __name__ == "__main__":
    main()
```

## React でダッシュボードを作る

ここからはフロントエンドです。Python が出力した JSON を読み込んで、Recharts でグラフを描きます。

この部分も Copilot CLI で「DAU の推移を AreaChart で、モード別利用を StackedBarChart で表示する React コンポーネントを作って」と指示して生成しました。Recharts の API は Copilot CLI がよく知っているので、ほぼ一発で動くコードが出てきます。

### 型定義

```typescript:dashboard/src/types.ts
export interface DailySummary {
  day: string;
  active_users: number;
  chat_panel_agent_mode: number;
  chat_panel_ask_mode: number;
  chat_panel_edit_mode: number;
  chat_panel_custom_mode: number;
  interactions: number;
}

export interface UserSummary {
  user: string;
  active_days: number;
  total_interactions: number;
  total_code_generations: number;
  agent_mode_interactions: number;
}
```

### DAU チャート

```tsx:dashboard/src/components/DauChart.tsx
import {
  Area, AreaChart, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { DailySummary } from "../types";

interface Props {
  data: DailySummary[];
}

export function DauChart({ data }: Props) {
  return (
    <div>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
        日別アクティブユーザー数
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="day"
            tickFormatter={(v: string) => v.slice(5)}
            fontSize={12}
          />
          <YAxis fontSize={12} />
          <Tooltip
            labelFormatter={(v: string) => `${v}`}
            formatter={(value: number) => [`${value} 人`, "アクティブユーザー"]}
          />
          <Area
            type="monotone"
            dataKey="active_users"
            stroke="#6366f1"
            fill="#6366f1"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

### モード別利用比率

```tsx:dashboard/src/components/ModeBreakdown.tsx
import {
  Bar, BarChart, CartesianGrid, Legend,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { DailySummary } from "../types";

interface Props {
  data: DailySummary[];
}

const MODES = [
  { key: "chat_panel_agent_mode", label: "Agent", color: "#f59e0b" },
  { key: "chat_panel_ask_mode", label: "Ask", color: "#3b82f6" },
  { key: "chat_panel_edit_mode", label: "Edit", color: "#10b981" },
  { key: "chat_panel_custom_mode", label: "Custom", color: "#8b5cf6" },
] as const;

export function ModeBreakdown({ data }: Props) {
  return (
    <div>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
        チャットモード別の利用推移
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="day"
            tickFormatter={(v: string) => v.slice(5)}
            fontSize={12}
          />
          <YAxis fontSize={12} />
          <Tooltip labelFormatter={(v: string) => `${v}`} />
          <Legend />
          {MODES.map((m) => (
            <Bar
              key={m.key}
              dataKey={m.key}
              name={m.label}
              fill={m.color}
              stackId="mode"
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

### ユーザー一覧テーブル

```tsx:dashboard/src/components/UserTable.tsx
import type { UserSummary } from "../types";

interface Props {
  data: UserSummary[];
}

export function UserTable({ data }: Props) {
  return (
    <div>
      <h2 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
        ユーザー別の利用状況（上位 20 名）
      </h2>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
            <th style={{ padding: "8px" }}>ユーザー</th>
            <th style={{ padding: "8px" }}>アクティブ日数</th>
            <th style={{ padding: "8px" }}>インタラクション</th>
            <th style={{ padding: "8px" }}>コード生成</th>
            <th style={{ padding: "8px" }}>Agent モード</th>
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 20).map((user) => (
            <tr key={user.user} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "8px", fontFamily: "monospace" }}>{user.user}</td>
              <td style={{ padding: "8px" }}>{user.active_days} 日</td>
              <td style={{ padding: "8px" }}>{user.total_interactions}</td>
              <td style={{ padding: "8px" }}>{user.total_code_generations}</td>
              <td style={{ padding: "8px" }}>{user.agent_mode_interactions}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### App.tsx でまとめる

```tsx:dashboard/src/App.tsx
import { useEffect, useState } from "react";
import { DauChart } from "./components/DauChart";
import { ModeBreakdown } from "./components/ModeBreakdown";
import { UserTable } from "./components/UserTable";
import type { DailySummary, UserSummary } from "./types";

function App() {
  const [daily, setDaily] = useState<DailySummary[]>([]);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/data/daily_summary.json").then((r) => r.json()),
      fetch("/data/user_summary.json").then((r) => r.json()),
    ])
      .then(([d, u]) => {
        setDaily(d);
        setUsers(u);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p style={{ padding: "2rem" }}>読み込み中...</p>;
  }

  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "2rem 1rem" }}>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "2rem" }}>
        Copilot Usage Dashboard
      </h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
        <DauChart data={daily} />
        <ModeBreakdown data={daily} />
        <UserTable data={users} />
      </div>
    </div>
  );
}

export default App;
```

## 動かしてみる

今回はモックデータで動作確認します。冒頭で触れた通り、所属 Organization の都合で実 API は叩けないので、フィールド定義に合わせた現実的なデータを自分で生成しました。

```bash:ターミナル
# 1. モックデータを生成（実 API を叩かずに動作確認する場合）
uv run src/generate_mock.py
uv run src/transform.py

# もし Organization の管理権限があるなら、実 API からも取得できる
# uv run src/fetch_metrics.py
# uv run src/transform.py

# 2. ダッシュボードを起動
cd dashboard
npm run dev
```

`http://localhost:5173` を開くと、DAU の推移やモード別の利用比率が表示されます。

`generate_mock.py` は API のフィールド定義に準拠して、28 日分の daily データと 10 人分のユーザーデータを生成します。`total_active_users` は 5〜15、`chat_panel_agent_mode` は 0〜50 といった現実的な範囲の乱数を使っています。実際のレスポンスと同じ NDJSON 形式で出力するので、データ取得以降の処理は実 API とモックで同じコードパスを通ります。

## ハマったところ

### NDJSON を JSON 配列と勘違いしそうになった

新 API を最初に使うときに、一番気をつけないといけないのがここです。`/orgs/{org}/copilot/metrics/reports/...` のレスポンス自体は JSON オブジェクトを返しますが、その中の `download_links` が指す先のファイルは NDJSON 形式です。名前から `.json` で終わっていても、開くと 1 行 1 オブジェクトで、JSON 配列ではありません。

最初にやりがちなのは、ダウンロードしたファイルに対して `response.json()` を呼んでしまって `JSONDecodeError` が出るパターンです。polars の `pl.read_ndjson()` を使えば一発で解決しますが、これを知らないと `json.loads()` のループを手で書くことになります。

### httpx の自動計装は `httpx.Client()` 経由でないと効かない

`HTTPXClientInstrumentor().instrument()` で有効化したあと、モジュール関数の `httpx.get(url)` は計装されません（OpenTelemetry Python Contrib の既知の挙動）。`with httpx.Client() as client:` の形で Client インスタンスを作って `client.get(url)` を呼ぶ必要があります。記事のコードはこのパターンで書いています。

### azd の `azd-service-name` タグを忘れると deploy で失敗する

これは実際にやらかしました。`azd up` でプロビジョニングまでは通ったのに、`azd deploy` が「サービス `dashboard` に対応するリソースが見つからない」で落ちました。Bicep の Static Web App リソースに `tags: union(tags, { 'azd-service-name': 'dashboard' })` を付け忘れていたのが原因です。`azure.yaml` の `services` の名前と、Bicep リソースのタグが対応していないと azd が紐付けを解決できません。

### カスタム命令の効果

AGENTS.md に「間違えやすい API」テーブルを書いておいたのが地味に効きました。たとえば API バージョンヘッダーを `2022-11-28`（旧）ではなく `2026-03-10`（新）にする、というルールを書いておくと、Copilot CLI がコード生成時に正しいバージョンを使ってくれます。

逆に、カスタム命令がないと、Copilot CLI は学習データにあるレガシー API のパターンでコードを書くことがあります。新しい API を使うプロジェクトでは、AGENTS.md や instructions に「何が変わったか」を明示しておくのがおすすめです。

## 新 API で見えるようになったこと

フィールド定義を読むと、新 API の進化ポイントが見えてきます。

いちばん大きいのは、Agent モードの利用状況が取れるようになったことです。`chat_panel_agent_mode`、`chat_panel_ask_mode`、`chat_panel_edit_mode`、`chat_panel_custom_mode` の 4 つに分かれていて、Organization 内でどのモードがどれくらい使われているかが把握できます。Agent モードと Ask モードの比率を時系列で追えば、組織の AI 活用の進み具合が定量的に見えるはずです。

ユーザー単位のレポート（`users-28-day`、`users-1-day`）が新設されたのも大きいです。`user_login` と `user_initiated_interaction_count` を組み合わせれば、ライセンスは付与されているけど実際には使っていない人を特定できます。テックリードがライセンスの最適化を考えるときに、ここがいちばん知りたいところではないかと思います。

`agent_edit` フィールド（Agent/Edit モードでの行追加・削除）も追加されていて、「AI がどれだけコードを実際に書いたか」の定量化ができそうです。ここは自分ではまだ活用できていませんが、Copilot の ROI 議論ではキーになるフィールドだと思います。

## Azure Static Web Apps にデプロイする

ローカルで動くことを確認できたので、Azure にデプロイしてチームで共有できるようにします。元リポジトリ（microsoft/copilot-metrics-dashboard）は Azure App Service + Azure Functions を使っていますが、今回の構成は静的サイトなので Azure Static Web Apps のほうがシンプルです。

`azd`（Azure Developer CLI）を使えば、Bicep によるインフラ構築からアプリのデプロイまでワンコマンドで済みます。

### azure.yaml

プロジェクトルートに `azure.yaml` を作ります。これは `azd` がプロジェクトの構成を理解するための定義ファイルです。

```yaml:azure.yaml
name: copilot-metrics-dashboard
services:
  dashboard:
    project: ./dashboard
    host: staticwebapp
    dist: dist
    language: js
hooks:
  preprovision:
    shell: sh
    run: echo "データの事前生成が必要な場合は、ここで uv run src/fetch_metrics.py を実行できます"
  predeploy:
    shell: sh
    run: |
      cd dashboard
      npm ci
      npm run build
```

`host: staticwebapp` を指定すると、`azd` が Azure Static Web Apps へのデプロイだと判断してくれます。`dist` はビルド出力先で、Vite のデフォルトです。

### Bicep テンプレート

`infra/main.bicep` にインフラ定義を書きます。ここも Copilot CLI に「Azure Static Web Apps の Bicep テンプレートを書いて」と頼んで生成しました。Free プランで十分です。

```bicep:infra/main.bicep
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('リソースの命名に使う環境名')
param environmentName string

@minLength(1)
@description('リソースのデプロイ先リージョン')
param location string

var tags = {
  'azd-env-name': environmentName
}

var resourceGroupName = 'rg-${environmentName}'

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    name: environmentName
    location: location
    tags: tags
  }
}

module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'staticwebapp'
  scope: rg
  params: {
    name: 'swa-${environmentName}'
    location: 'eastasia'
    // azd が 'dashboard' サービスをこのリソースにデプロイするために必要なタグ
    tags: union(tags, { 'azd-service-name': 'dashboard' })
  }
}

output STATIC_WEB_APP_URL string = staticWebApp.outputs.uri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.connectionString
```

```bicep:infra/modules/monitoring.bicep
@description('リソース名のベース')
param name string

@description('デプロイ先リージョン')
param location string

@description('リソースに付与するタグ')
param tags object = {}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${name}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${name}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

output connectionString string = appInsights.properties.ConnectionString
```

```bicep:infra/modules/staticwebapp.bicep
@description('Static Web App のリソース名')
param name string

@description('デプロイ先リージョン')
param location string

@description('リソースに付与するタグ')
param tags object = {}

resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

output uri string = 'https://${staticWebApp.properties.defaultHostname}'
```

:::message
Azure Static Web Apps は対応リージョンが限られていて、SKU を問わず `westus2`、`centralus`、`eastus2`、`westeurope`、`eastasia` の 5 つだけです。日本から物理的に近いのは東アジア（`eastasia`）です。`japaneast` は 2026 年 4 月時点では対応していません。`azd up` 時に表示される選択肢から選んでください。
:::

### デプロイ

```bash:ターミナル
# 初回: 環境の初期化
azd init

# データを取得・加工（実 API を使う場合）
uv run src/fetch_metrics.py
uv run src/transform.py

# Azure にプロビジョニング + デプロイ
azd up
```

`azd up` を実行すると、Azure サブスクリプションとリージョンの選択を聞かれます。あとは自動で Resource Group の作成 → Static Web Apps のプロビジョニング → React アプリのビルド・デプロイが走ります。

完了すると、`https://xxx.azurestaticapps.net` のような URL と、Application Insights の接続文字列が出力されます。接続文字列を `.env` に追加しておきます。

```bash:.env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_ORG=your-org-name
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=https://xxx.in.applicationinsights.azure.com/
```

### Application Insights でデータパイプラインを監視する

OTel を入れたことで、`uv run src/fetch_metrics.py` を実行すると、データ取得プロセスのトレースが Application Insights に送信されます（モックデータ側の `generate_mock.py` は API 呼び出しを含まないので、実 API を叩ける環境での話です）。Azure Portal で Application Insights を開き、「トランザクション検索」を見ると、こんな情報が確認できるはずです。

- `fetch_all_metrics` スパン: データ取得プロセス全体の所要時間
- `fetch_report_links` スパン: GitHub API からレポートリンクを取得するまでの時間
- `download_ndjson` スパン: NDJSON ファイルをダウンロード・パースするまでの時間
- httpx の自動計装: 個々の HTTP リクエストのステータスコード、レスポンスタイム

GitHub API のレート制限に引っかかった場合や、署名付き URL が期限切れになった場合のエラーも、トレースとして記録されます。GitHub Actions で日次実行する構成にしたとき、「昨日のデータ取得が失敗していたのに気づかなかった」という事態を防げます。

個人的には、Copilot のメトリクスを可視化するツール自体が Azure Monitor で監視されている、という構成がちょっと面白いなと思っています。

### Copilot CLI の開発プロセスも OTel で観測する

ここからが今回いちばんやりたかったことです。

GitHub Copilot CLI は OTel トレースのエクスポート機能を内蔵しています。GenAI Semantic Conventions に準拠したスパンツリー（`invoke_agent` → `chat` + `execute_tool`）を出力でき、LLM 呼び出し・ツール実行・トークン消費を記録します。デフォルトでは無効ですが、環境変数を設定するだけで有効になります。

```bash:ターミナル
# OTel Collector のエンドポイントを指定して Copilot CLI を起動
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
copilot
```

OTel Collector を経由して Application Insights に送る構成にすると、Python データパイプラインのトレースと、Copilot CLI の開発プロセスのトレースが同じ Application Insights に集約されます。

Application Insights の「Agents details」ダッシュボードでは、GenAI Semantic Conventions に準拠したテレメトリを取り込んで、ツールごとの呼び出し頻度やトークン消費の推移を可視化できます。「このダッシュボードを作るのにどれだけ Copilot CLI を使ったか」「どのモデルでどれだけのトークンを消費したか」が見えるのは面白いです。

:::message
Copilot CLI の OTel 出力はプロンプトやレスポンスの内容を含みません（メタデータのみ）。内容も記録したい場合は `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` を設定しますが、機密情報が含まれる可能性があるので、信頼できる環境でのみ使ってください。
:::

ちなみに、VS Code の Copilot Chat でも同じ GenAI Semantic Conventions で OTel テレメトリをエクスポートする機能があります。こちらは別の記事で詳しく書いたので、興味がある方は「[GitHub Copilot Chat エージェントの振る舞いを OTel で分析する](https://zenn.dev/microsoft/articles/6b22d233a9f0a2)」を参照してください。

### Copilot CLI でインフラコードを書いた話

正直なところ、Bicep のテンプレートは自分でゼロから書くより Copilot CLI に任せたほうが速かったです。「Azure Static Web Apps の Free プランを Bicep で作って。azd 対応にして」と指示したら、`targetScope = 'subscription'` のパターンや `azd-env-name` タグの付与まで含めたコードが出てきました。

ただ、ハマったのが `azd-service-name` タグです。最初に生成されたコードにはこのタグが無くて、`azd up` は通るものの `azd deploy` が「デプロイ先のリソースが見つからない」というエラーで失敗しました。`azure.yaml` で定義したサービス名（今回は `dashboard`）を、対応する Bicep リソースのタグ `azd-service-name: 'dashboard'` で識別する仕組みになっています。main.bicep の Static Web Apps モジュール呼び出しで `union(tags, { 'azd-service-name': 'dashboard' })` とする形で対応しました。

Free プランのリージョン制約（`eastasia` は使えるが `japaneast` は非対応）も Copilot CLI が最初は知らなかったので、自分で公式ドキュメントを確認して修正しました。この手のハマりどころは `infrastructure.instructions.md` に書いておけば、次回以降は Copilot CLI が最初から正しいコードを生成してくれます。

## ここから発展させるなら

ここまでで「API からデータ取得 → 可視化 → Azure にデプロイ」までは完成しました。データの更新を自動化するなら、GitHub Actions のスケジュール実行で Python スクリプトを毎日走らせて JSON を更新、そのまま `azd deploy` でデプロイし直す構成が自然です。

1 日単位の API（`organization-1-day`）を使えば 28 日の制約を超えた長期トレンドも追えます。取得したデータを Azure Blob Storage に蓄積していく形にすれば、半年〜1年分の推移を見られるダッシュボードになります。

## おわりに

今回は新しい Copilot usage metrics API を使って、polars + React のダッシュボードを Azure Static Web Apps にデプロイし、OpenTelemetry で可観測性を確保するところまでやりました。

振り返ると、3 つのレイヤーで「Copilot の使われ方」を捉える構成になっています。

1つ目は、Copilot usage metrics API で Organization 全体の利用状況（DAU、モード別比率、ユーザー別データ）を可視化したこと。2つ目は、そのデータを取得する Python パイプライン自体を OTel + Application Insights で監視していること。3つ目は、このダッシュボードを作る開発プロセス（Copilot CLI の LLM 呼び出しやツール実行）も GenAI Semantic Conventions 準拠の OTel で Application Insights に集約していること。

カスタム命令（AGENTS.md、instructions、skills）を整備してから Copilot CLI で開発すると手戻りがかなり減る、という発見は今回いちばんの収穫でした。API 仕様の変更点や Bicep のお作法を instructions に書いておくだけで、Copilot CLI が生成するコードの品質が上がります。

残った宿題として、実 Organization データでの動作検証があります。今回はモックデータで完結させましたが、権限が揃う機会があればフィールド欠落や規模感のズレを確認して、別の記事でフォローアップしたいと思っています。

次は GitHub Actions での日次データ更新の自動化と、Lines of Code メトリクスの可視化をやってみたいなと思っています。

## 参考リンク

公式ドキュメント:

<!-- markdownlint-disable MD034 -->
https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics

https://docs.github.com/en/rest/copilot/copilot-usage-metrics

https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics

https://learn.microsoft.com/en-us/azure/static-web-apps/publish-bicep
<!-- markdownlint-enable MD034 -->

Changelog:

<!-- markdownlint-disable MD034 -->
https://github.blog/changelog/2026-02-27-copilot-metrics-is-now-generally-available/

https://github.blog/changelog/2026-01-29-closing-down-notice-of-legacy-copilot-metrics-apis/
<!-- markdownlint-enable MD034 -->

リポジトリ:

<!-- markdownlint-disable MD034 -->
https://github.com/microsoft/copilot-metrics-dashboard

https://github.com/github-copilot-resources/copilot-metrics-viewer
<!-- markdownlint-enable MD034 -->

:::details 免責事項
本記事は個人の見解であり、所属組織の公式な見解ではありません。
記載内容は 2026 年 4 月時点の情報に基づいています。API の仕様やフィールドは今後変更される可能性があります。
本記事のダッシュボードは API のフィールド定義に準拠したモックデータで動作確認しており、実 Organization データでの動作は未検証です。
本記事のコードは動作確認を目的としたものであり、本番環境での利用を保証するものではありません。
Azure Static Web Apps は SKU を問わず対応リージョンが限られており、Free プランではカスタムドメインの数など追加の制限もあります。詳細は公式ドキュメントを参照してください。
:::
