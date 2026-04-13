# Copilot Metrics Dashboard

GitHub Copilot の新しい usage metrics API（Organization レベル）からデータを取得し、
React ダッシュボードで可視化するプロジェクト。Zenn 記事のコンテスト投稿を兼ねる。

## アーキテクチャ

```
GitHub API (usage metrics)
  ↓ NDJSON (download_links → 署名付き URL)
Python (httpx + polars)
  ├→ JSON ファイル出力 → React (Vite + Recharts) → Azure Static Web Apps
  └→ OTel トレース ─┐
                     ├→ Application Insights（Agents details ダッシュボード）
Copilot CLI ─────────┘
  └→ GenAI Semantic Conventions 準拠の OTel トレース
```

## 間違えやすい API / 設定

| ✅ 正しい | ❌ 間違い | 理由 |
|----------|---------|------|
| `X-GitHub-Api-Version: 2026-03-10` | `2022-11-28` | 新 API は 2026-03-10 必須。旧バージョンだとレガシー API にルーティングされる |
| レスポンスの `download_links` を GET → NDJSON を行ごとにパース | `response.json()` で全体をパース | 新 API は直接データを返さない。ダウンロードリンク → NDJSON の 2 段階 |
| `/orgs/{org}/copilot/metrics/reports/organization-28-day/latest` | `/orgs/{org}/copilot/metrics` | 旧エンドポイントは 2026-04-02 にサンセット済み |
| PAT スコープ: `read:org` | `manage_billing:copilot` | Organization レベルは `read:org` で十分 |
| `uv add httpx` | `pip install httpx` | このプロジェクトは uv を使う |
| NDJSON: 1 行 = 1 JSON オブジェクト | NDJSON: JSON 配列 | `json.loads(line)` で 1 行ずつパースする |
| `pl.read_ndjson(io.BytesIO(content))` | `json.loads(line)` のループ | polars は NDJSON をネイティブにパースできる |

## コマンド集

```bash
# Python 側
uv sync                          # 依存インストール
uv run src/fetch_metrics.py      # API からデータ取得
uv run src/generate_mock.py      # モックデータ生成
uv run src/transform.py          # データ加工
uv run ruff check .              # リント
uv run pytest                    # テスト

# React 側
cd dashboard && npm install      # 依存インストール
cd dashboard && npm run dev      # 開発サーバー起動
cd dashboard && npm run build    # ビルド

# デプロイ
azd init                         # 初回のみ
azd up                           # プロビジョニング + デプロイ
azd deploy                       # 既存リソースへの再デプロイ
azd down                         # リソース削除
```

## 変更の規律

- 依頼された変更だけ行う。隣接コードを勝手に「改善」しない
- 既存のスタイルに合わせる
- 無関係なデッドコードに気づいたら削除せず指摘だけする
- コミット・push は、現在の会話で明示依頼がある場合だけ行う

## Zenn 記事の品質基準

- 冒頭に参照時点を明記する
- 公式ドキュメントの内容と私見を明確に分ける
- コードは動作確認済みのもの。未検証なら「未検証」と書く
- 製品名は正式名称を使う（Microsoft Foundry、GitHub Copilot CLI など）
- AI 文体を使わない（詳細は `.github/skills/zenn-writing-style/SKILL.md`）

## ファクトチェック手順

1. 製品名・API パス: 公式ドキュメント（docs.github.com）で確認
2. PAT スコープ・権限: REST API ドキュメントで確認
3. NDJSON フィールド名: 「Data available in Copilot usage metrics」ページで確認
4. 価格・制限値: 公式 Pricing ページで確認
5. URL: 実アクセスで確認
