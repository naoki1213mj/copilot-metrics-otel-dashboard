# copilot-metrics-dashboard

## What This Is

GitHub Copilot usage metrics API（Organization レベル）のデータを可視化するダッシュボード。
Python でデータ取得・加工し、React でグラフ描画する。Zenn 記事のコンテスト投稿を兼ねる。

## Tech Stack

- Python 3.14+, uv, httpx, polars, azure-monitor-opentelemetry, opentelemetry-instrumentation-httpx, ruff
- React 19, Vite 6, TypeScript 5, Recharts
- Azure Static Web Apps（デプロイ先）
- azd（Azure Developer CLI）

## Coding Guidelines

### Python
- パッケージ管理: uv（pip や venv ではなく uv を使う）
- リンター・フォーマッター: ruff
- 型ヒント必須。`str | None` 形式（`Optional[str]` ではなく）
- 変数名・関数名は英語。コメントと docstring は日本語
- エラーは具体的な例外型で catch する（bare except 禁止）
- `pip install` を使わない。`requirements.txt` を手動編集しない

### TypeScript / React
- 関数コンポーネントのみ。class コンポーネントは使わない
- Props は interface で定義する
- `any` 型を使わない

### 共通
- コミットメッセージは Conventional Commits 形式
- シークレットは `.env` で管理。`.env` は `.gitignore` に入れる
- `.env.example` をプレースホルダー値付きで用意する
- 不明な API は公式ドキュメントで確認してから使う

## Project Structure

```
copilot-metrics-dashboard/
├── src/                    # Python（データ取得・加工）
│   ├── fetch_metrics.py
│   ├── transform.py
│   └── generate_mock.py
├── dashboard/              # React（フロントエンド）
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   └── types.ts
│   └── public/data/        # Python が出力した JSON
├── articles/               # Zenn 記事
├── infra/                  # Bicep / azd
├── pyproject.toml
└── .env.example
```

## Key Decisions

1. Organization レベル API を使う — Enterprise レベルより読者のアクセス権限の壁が低い
2. Python + React の 2 層構成 — Python で API 呼び出しと NDJSON パース、React で描画。microsoft/copilot-metrics-dashboard の構成に近い
3. 静的 JSON 連携 — Python が JSON ファイルを出力し、React はそれを読む。リアルタイム連携はしない
4. モックデータ対応 — 実 API 環境がなくてもダッシュボードの動作確認ができるようにする

## Resources

- API スキル: `.github/skills/copilot-metrics-api/SKILL.md`
- 文体スキル: `.github/skills/zenn-writing-style/SKILL.md`
- ファクトチェック: `.github/skills/zenn-factcheck/SKILL.md`

## Quick Commands

```bash
uv sync && cd dashboard && npm install   # 初回セットアップ
uv run src/generate_mock.py              # モックデータ生成
uv run src/transform.py                  # データ加工
cd dashboard && npm run dev              # ダッシュボード起動
```
