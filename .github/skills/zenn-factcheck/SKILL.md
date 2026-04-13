---
name: zenn-factcheck
description: >-
  技術記事のファクトチェック手順。製品名、API、バージョン、URL を一次情報源と照合する。
  「ファクトチェック」「確認」「正確性」のリクエストで使う。
---

# ファクトチェック手順

## 照合対象と一次情報源

| 対象 | 確認内容 | 一次情報源 |
|------|---------|-----------|
| 製品名 | 正式名称、リブランド | 公式ドキュメント |
| バージョン | GA / Preview / サンセット | Changelog、PyPI、GitHub Releases |
| コード | エンドポイント、認証方式、パラメータ | SDK リポジトリ、REST API ドキュメント |
| 数値 | 保持期間、制限値 | 公式ドキュメント |
| URL | リンク切れ、リダイレクト | 実アクセスで確認 |

## このプロジェクト固有の確認先

- Copilot usage metrics API: https://docs.github.com/en/rest/copilot/copilot-usage-metrics
- データフィールド: https://docs.github.com/en/copilot/reference/copilot-usage-metrics/copilot-usage-metrics
- Changelog: https://github.blog/changelog/2026-02-27-copilot-metrics-is-now-generally-available/
- レガシー API サンセット: https://github.blog/changelog/2026-01-29-closing-down-notice-of-legacy-copilot-metrics-apis/

## ルール

- Preview 機能は「YYYY 年 M 月時点で Preview」と日付を添える
- 確認できない情報は「未確認」と明記する
- 推測と事実を混ぜない
