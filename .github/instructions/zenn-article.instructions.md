---
name: 'Zenn 記事ルール'
description: 'Zenn 記事の文体、記法、ファクトチェック規約'
applyTo: 'articles/**/*.md'
---

## 技術名称の正誤表

| ✅ 正しい | ❌ 間違い |
|----------|---------|
| GitHub Copilot | Github Copilot, github copilot |
| GitHub Copilot CLI | Copilot CLI（初出時は正式名称で） |
| Copilot usage metrics API | Copilot Metrics API（レガシー名） |
| NDJSON（Newline-Delimited JSON） | ndjson, NDJson |
| Organization | organization（文中では大文字始まり） |
| Personal Access Token（PAT） | personal access token（初出時は正式名称） |
| Azure Static Web Apps | Azure Static Web App（複数形） |
| Microsoft Foundry | Azure AI Foundry（旧名称。2025年11月リネーム） |

## Zenn 記法

- フロントマター必須: title（70 字以内）, emoji, type, topics, published
- 見出しは H2 から（H1 は Zenn が自動生成）
- `:::message` / `:::details タイトル` は `:::` で閉じる
- コードブロックにはファイル名ラベルをつける
- bare URL 単独行 → リンクカード表示。`<!-- markdownlint-disable MD034 -->` で囲む
- 冒頭に参照時点 `:::message`、末尾に `:::details 免責事項`

## AI 文体禁止

- **太字** を地の文に残さない
- 同じ語尾 3 回以上禁止
- 「以下の 3 つの観点から」→ 見出しで十分
- 「非常に重要です」→「けっこう大事です」
- 「～することが可能です」→「～できます」
- 「今後の展開が注目されます」→ 削除する
- 「まとめ」セクション → 「おわりに」で次にやりたいことを書く

## コンテスト情報

投稿先: Zenn「GitHub Copilot 活用選手権」（2026年4月1日〜30日）
狙い: Microsoft 製品 × GitHub Copilot 賞
ポイント: Azure + Copilot CLI を使った開発プロセスの再現性・具体性
