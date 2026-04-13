---
title: "Copilot usage metrics API と Azure でダッシュボードを組んでみた"
emoji: "📊"
type: "tech"
topics: ["GitHubCopilot", "Python", "React", "Azure"]
published: false
---

こんにちは。松本です。

GitHub Copilot の利用状況を Organization 単位で眺めるダッシュボードを作ってみました。新しい Copilot usage metrics API でデータを取得し、Python と polars で加工して、React で描画する構成です。Azure Functions で取り込みを回し、App Service でダッシュボードを配信するところまで組んでいます。

ただし、今の環境では会社のポリシーで実 Organization のデータを取れません。この記事で見せているのはすべてモックデータです。API のフィールド定義に沿ったモックを用意して、「実データが入ったらそのまま差し替わる」構成にしてあるので、あくまで「やるならこう組む」の検証として読んでもらえると助かります。

:::message
2026 年 4 月 14 日時点の公式ドキュメントとリポジトリの実装に基づいています。Copilot usage metrics API は 2026 年 2 月 27 日に GA、旧 `/orgs/{org}/copilot/metrics` は 4 月 2 日にサンセット済みです。
:::

## API の返し方が変わった

usage metrics API で最初に引っかかるのは、レスポンスの形です。旧 API は JSON 配列をそのまま返してくれていた。新しいほうは 2 段構えになっています。エンドポイントを叩くと `download_links` の配列が返ってきて、そこに入っている署名付き URL から NDJSON をダウンロードする流れです。

| 項目 | 旧 API | usage metrics API |
|---|---|---|
| エンドポイント | `/orgs/{org}/copilot/metrics` | `/orgs/{org}/copilot/metrics/reports/...` |
| 返り値 | JSON 配列 | `download_links` を含む JSON |
| 実データ | レスポンスに直接入っている | 署名付き URL 先の NDJSON |
| API バージョン | `2022-11-28` | `2026-03-10` |

正直、最初は戸惑いました。`response.json()` でデータが取れないので。ただ、NDJSON は polars がネイティブに読めるので、実装は意外とすっきり収まる。

```python:src/fetch_metrics.py（抜粋）
def download_ndjson(client: httpx.Client, links: list[str]) -> pl.DataFrame:
    """署名付き URL から NDJSON をダウンロードして結合する。"""
    frames: list[pl.DataFrame] = []
    for link in links:
        resp = client.get(link)
        resp.raise_for_status()
        df = pl.read_ndjson(io.BytesIO(resp.content))
        frames.append(df)
    return concat_data_frames(frames)
```

`json.loads()` で 1 行ずつパースするループは不要です。`pl.read_ndjson()` に `BytesIO` を渡すだけ。polars のこの機能に気づいたときは少し嬉しかったです。

## 日次レポートの束ね方

ここは最初に勘違いしたところです。

`organization-28-day/latest` は、直近 28 日のまとまったレポートを返してくれる。便利です。ただ、このリポジトリの 100 日表示はこの endpoint から作っていません。

やっているのは、`organization-1-day?day=YYYY-MM-DD` を日付ごとに叩いて、最大 100 日ぶんの日次データを束ねることです。ダッシュボードの 28 / 60 / 100 日切り替えは、集めた日次データのスライスを変えているだけ。

- `organization-28-day/latest` → 直近 28 日のまとまりレポート
- `organization-1-day?day=...` → 特定日のレポート。100 日分回す
- UI の期間切り替え → 日次データの表示範囲を変える

この区別が腹落ちしたとき、API の設計がちょっと見えた気がしました。28 日 latest は「全体像をさっと見たい」用で、日次のほうは「好きな粒度で束ねてくれ」という割り切りだろうと。

## 構成

Microsoft 公式の [microsoft/copilot-metrics-dashboard](https://github.com/microsoft/copilot-metrics-dashboard) を意識しつつ、取り込みと配信を分けた Azure 構成にしています。

```txt:アーキテクチャ
GitHub Copilot usage metrics API
  ↓ download_links → signed URL → NDJSON
Azure Functions (ingestion)
  ├─ raw NDJSON → Blob Storage (raw-metrics)
  ├─ 変換 JSON  → Blob Storage (curated-metrics / dashboard-data)
  ├─ メタデータ → Cosmos DB (ingestionRuns / dashboardViews)
  └─ テレメトリ → Application Insights

Azure App Service (dashboard)
  ├─ React SPA を配信
  └─ /api/data/* を Functions にプロキシ

Key Vault → GitHub token 保持
Log Analytics → 全リソースの diagnostic settings
```

ファイルと役割の対応はこうなっています。

| レイヤー | ファイル | やっていること |
|---|---|---|
| データ取得 | `src/fetch_metrics.py` | GitHub API → NDJSON ダウンロード |
| 変換 | `src/transform.py` | NDJSON → ダッシュボード用 JSON 4 種 |
| モック生成 | `src/generate_mock.py` | 10 ユーザー × 100 日のモックデータ |
| Functions 実行 | `src/ingestion_runtime.py`, `function_app.py` | 定期実行・手動実行・データ配信 |
| ダッシュボード | `dashboard/src/*`, `dashboard/server.js` | React UI + Node.js 配信サーバー |
| インフラ | `infra/*.bicep`, `azure.yaml` | Azure リソース定義と azd |

軽い静的構成よりだいぶ重い。ただ、「本当に回すならこうなるよな」という感覚で組んでいます。

## データ取り込みのポイント

### httpx.Client を分ける

GitHub API を叩く client と、署名付き URL からダウンロードする client は分けています。理由はシンプルで、署名付き URL 側に GitHub の Bearer トークンを送りたくないから。

```python:src/fetch_metrics.py（抜粋）
def build_api_client(token: str) -> httpx.Client:
    """GitHub API 用。認証ヘッダーと API バージョンを設定する。"""
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        },
        timeout=30,
    )

def build_download_client() -> httpx.Client:
    """NDJSON ダウンロード用。認証ヘッダーは付けない。"""
    return httpx.Client(timeout=60)
```

地味ですが、こういう分離はあとから効いてきます。OTel の自動計装（`HTTPXClientInstrumentor`）も API 用 client だけに付けて、署名付き URL のアクセスがトレースに混ざらないようにしました。

### OTel は条件付きで有効化する

`APPLICATIONINSIGHTS_CONNECTION_STRING` が設定されているときだけ `configure_azure_monitor()` を呼んでいます。ローカルでモックデータを触るだけなら、テレメトリは不要です。

ちなみに、`httpx.get()` のようなモジュール関数ではなく `httpx.Client()` のインスタンスメソッドを使っているのは、この自動計装を効かせるためでもあります。

### 欠けるフィールドは埋める前提にする

usage metrics API はフィールドが増え続けています。2026 年 4 月だけでも、cloud agent のアクティブユーザー集計や code review の active / passive 区別など、複数のフィールドが追加されました。日によっては値が欠けることもありえるので、`src/transform.py` の `ensure_columns()` で足りないカラムを 0 や `false` で補完してから集計しています。

```python:src/transform.py（抜粋）
def ensure_columns(df: pl.DataFrame, defaults: dict[str, object]) -> pl.DataFrame:
    """DataFrame に必要なカラムが無い場合、既定値で埋めて追加する。"""
    missing_columns = [
        pl.lit(default).alias(col)
        for col, default in defaults.items()
        if col not in df.columns
    ]
    if missing_columns:
        df = df.with_columns(missing_columns)
    return df
```

記事にするほどの話ではないかもしれませんが、実装していて地味に助かった部分です。

## モックデータの設計

実データが手に入らない以上、モックの質がダッシュボードの検証精度をそのまま決めます。ここはけっこう力を入れました。

`src/generate_mock.py` では 10 人のユーザーにそれぞれペルソナを持たせています。`staff-engineer`（Agent 利用が濃い）、`review-focused`（review の touch 日数が多い）、`casual-user`（週末はほぼ触らない）、といった具合です。各ペルソナで平日 / 休日の activity 確率やモード別の share を変えているので、ダッシュボードに表示したときに「人によって使い方が違う」のが見えます。

言語プロファイルもユーザーごとに分けていて、alice は Python + Go + HCL、bob は TypeScript + CSS のように偏りを付けました。「全員が同じ言語を同じ割合で使っている」モックだと、言語チャートが無意味になるので。

あと、100 日の中に `onboarding-drive`、`agent-rollout`、`delivery-sprint` のようなフェーズを入れて、期間によって言語の activity にブーストをかけています。これで「Agent を導入した週に bicep と hcl が跳ねた」みたいな傾向がモック上でも出ます。

## ダッシュボードの見せ方

UI は Overview、Agent、Diagnostics の 3 タブです。全部縦に並べるとスクロールが長くなりすぎるし、スクリーンショットも撮りにくかったので、タブで切りました。

Overview は DAU とプロンプト数の推移、言語別 activity。Agent タブは IDE 内の Agent / Plan モードの利用推移と、cloud agent のアクティブユーザー数。Diagnostics はコード生成・承認の推移、review の touch 日数、ユーザー別の利用状況を見ます。

表示期間は 28 / 60 / 100 日で切り替えられて、`user_daily_summary.json` から React 側で再集計しているので、期間を変えるとユーザー別の集計も追従します。

### 言語ラベルはそのまま使う

`totals_by_language_feature` で返ってくる言語ラベルは、勝手に一般化しないことにしました。`hcl` を「Terraform」に丸めたくなりますし、`bash` と `shellscript` と `pwsh` をまとめたくもなる。ただ、API が返す値をそのまま使うほうが、あとから「なぜ違う値が出ているのか」で悩まずに済みます。

### chat_panel_edit_mode は Plan と表示する

API のフィールド名は `chat_panel_edit_mode` ですが、UI 上は Plan として表示しています。GitHub Copilot の Inline Chat で Plan モードに相当する指標で、生のフィールド名をそのまま見せるより伝わりやすい。この手の「API 名と画面ラベルが 1:1 じゃない」判断は、実装してみて初めて要るとわかった部分です。

## azd でのデプロイ

デプロイは azd を使っています。`azure.yaml` で dashboard を App Service、ingestion を Azure Functions として定義しました。

```yaml:azure.yaml
services:
  dashboard:
    project: ./dashboard
    language: js
    host: appservice
    dist: deploy
    hooks:
      prepackage:
        shell: pwsh
        run: |
          if (-not (Test-Path node_modules)) {
            npm ci
          }
          npm run build
  ingestion:
    project: .
    language: py
    host: function
    hooks:
      prepackage:
        shell: pwsh
        run: uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

hooks の `shell: pwsh` は、Windows で開発しているなら入れておいたほうがいいです。デフォルトの `sh` だと WSL を前提に動こうとして、入っていない環境では落ちます。

Bicep は subscription スコープで書いていて、リソースグループの作成から始めて、Log Analytics、Storage、Cosmos DB、Key Vault、App Service Plan、Web App、Function App、RBAC まで一通りモジュール化しました。Storage と Cosmos DB はキー認証を無効にしていて、Function App と Web App の Managed Identity に必要な RBAC ロールを付けています。Functions 側には Blob Data Contributor + Cosmos DB Data Contributor、Web App 側には dashboard-data コンテナーの Blob Data Reader だけ。

GitHub token は Key Vault に入れて、`azd env set --file .env` で流し込む形です。

デプロイの流れはこう。

```bash:ターミナル
azd env new copilot-otel-sub1-easia --subscription <id> --location eastasia
azd env set --file .env
azd provision --no-state
azd deploy --all
```

正直に書くと、今の subscription では App Service plan の quota 制限に当たって、region や SKU を何度か変えました。最終的に East Asia の P1v3 で provision は通り、App Service 側のダッシュボードは動いています。ただ、Function App のデプロイがまだ完全には通っておらず、ホストが起動しない状態が残っています。ここは別途対応中です。

## 監視

Application Insights と Log Analytics はかなり厚めに入れました。Function App と Web App だけでなく、Storage や Cosmos DB にも diagnostic settings を付けています。

`function_app.py` には ingestion 用の endpoint も用意しました。

- `POST api/ingestion/run` — 手動で取り込みを実行
- `GET api/ingestion/status` — 最新の取り込み状態を返す
- `GET api/data/{file_name}` — ダッシュボード用 JSON を配信

最新 run の状態は Cosmos DB にも残すので、単に「失敗した」で終わらず、あとから追いかけやすい。個人的にはここがいちばん実用的でした。ダッシュボードの見た目より先に、取り込みがちゃんと回るかのほうが気になります。

## Copilot CLI の使いどころ

今回、コードのかなりの部分を GitHub Copilot CLI と一緒に書きました。

いちばん効いたのは、コード生成そのものよりも、プロジェクト固有の前提を固定できること。このリポジトリでは `AGENTS.md` に「新 API は `download_links` を経由する」「NDJSON は `pl.read_ndjson()` で読む」「httpx の計装は `HTTPXClientInstrumentor`」のようなルールを書いてあります。Copilot CLI は会話のたびにこれを読んでくれるので、古い API のエンドポイントを提案してくることがかなり減りました。

さらに `.github/skills/` に API のフィールド定義まで入れています。usage metrics API はフィールドが頻繁に追加されるので、「`copilot_coding_agent_active_users_1d` は nullable で 2026-04 に追加」みたいな情報が手元にあるのとないのとでは、コード生成の精度がだいぶ違う。

Zenn 記事の文体ルールや製品名の正誤表も skill にしました。「GitHub Copilot であって Github Copilot ではない」「Microsoft Foundry であって Azure AI Foundry ではない」あたりの制約を、コードと記事の両方で共有できるのは skill の仕組みならではだと思います。

もちろん最初から完璧ではないです。Bicep のモジュール分割や RBAC の設計では何度か方針を直しました。ただ、直すたびに `AGENTS.md` が更新されるので、同じミスの繰り返しは減る。個人的には、Copilot CLI のいちばんの価値は「文脈を忘れないペアプロ相手」というところにあると感じています。

## おわりに

`copilot-metrics-otel-dashboard` は、新しい usage metrics API を理解するために作り始めたリポジトリです。結果的に、Azure Functions で取り込み、Blob Storage と Cosmos DB に永続化し、App Service でダッシュボードを配信するところまで膨らみました。

モックベースの検証なので、実 Organization データでの動作確認はまだです。Function App の起動を安定させて、一度 ingestion を通すのが直近の課題です。その先では、Cosmos DB に蓄積した run 履歴を使って「いつ Agent 利用が伸びたか」を追えるようにしたいと思っています。

API の 2 段階フロー、NDJSON のパース、polars での加工、Azure 上の RBAC 設計あたりは、この検証を通じてかなり整理できました。実データが取れる環境が用意できたら、そのまま差し替えて続きを試すつもりです。

## 参考リンク

公式ドキュメント:

<!-- markdownlint-disable MD034 -->
https://docs.github.com/en/rest/copilot/copilot-usage-metrics

https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics

https://github.blog/changelog/2026-02-27-copilot-metrics-is-now-generally-available/

https://github.blog/changelog/2026-01-29-closing-down-notice-of-legacy-copilot-metrics-apis/

https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/

https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages

https://learn.microsoft.com/en-us/azure/app-service/
<!-- markdownlint-enable MD034 -->

リポジトリ:

<!-- markdownlint-disable MD034 -->
https://github.com/microsoft/copilot-metrics-dashboard
<!-- markdownlint-enable MD034 -->

:::details 免責事項
本記事は個人の見解です。
記載内容は 2026 年 4 月 14 日時点の情報と、このリポジトリの実装に基づいています。
Copilot usage metrics API のフィールドや Azure のサポート状況は変わることがあります。
実運用に入れる前に、権限、コスト、保持期間、秘密情報の扱いは各環境で確認してください。
:::
