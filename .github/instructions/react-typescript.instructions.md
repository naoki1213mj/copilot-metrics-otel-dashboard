---
name: 'React TypeScript ルール'
description: 'React + Vite + Recharts のコーディング規約'
applyTo: 'dashboard/**/*.tsx, dashboard/**/*.ts'
---

## React ルール

- 関数コンポーネントのみ。class コンポーネントは使わない
- Props は interface で定義する。`type` ではなく `interface`
- `any` 型を使わない
- コメントは日本語で書く

## Recharts

- ResponsiveContainer で囲む
- XAxis の tickFormatter で日付を MM-DD 形式にする
- Tooltip に日本語のラベルを設定する
- 色は視認性の高いパレットを使う

## ファイル構成

- コンポーネントは `dashboard/src/components/` に配置
- 型定義は `dashboard/src/types.ts` にまとめる
- データ取得は `public/data/` の JSON ファイルを fetch する
