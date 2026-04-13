---
name: 'Infrastructure ルール'
description: 'Bicep / azd / Azure Static Web Apps のデプロイ規約'
applyTo: 'infra/**/*.bicep, azure.yaml, **/Dockerfile'
---

## azd

- `azure.yaml` でサービスを定義する。`host: staticwebapp` で Azure Static Web Apps にデプロイ
- `dist` は Vite のデフォルトビルド出力ディレクトリ
- hooks で pre/post 処理を定義できる（preprovision, predeploy など）

## Bicep

- `targetScope = 'subscription'` でリソースグループも Bicep で管理する
- タグに `azd-env-name` を含める（azd が環境を識別するために必要）
- **デプロイ対象のリソースには `azd-service-name: '<service>'` タグを必ず付ける**。これが無いと `azd deploy` がどのリソースにデプロイするか解決できず失敗する。`<service>` は `azure.yaml` の `services` 配下で定義した名前と一致させる
- モジュール分割: `infra/main.bicep` → `infra/modules/*.bicep`
- タグのマージは `union(tags, { 'azd-service-name': 'dashboard' })` の形で書く
- パラメータファイルは `infra/main.parameters.json` に置く

## Azure Static Web Apps

- Free プランはリージョンの選択肢が限られる。`eastasia` は利用可能、`japaneast` は 2026 年 4 月時点で非対応
- API バージョンは `2022-09-01` を使う
- GitHub Actions との自動連携を使わない場合は `properties` を空にする（azd が直接デプロイ）
- カスタムドメインは Free プランだと制限あり

## デプロイコマンド

```bash
azd init          # 初回のみ
azd up            # プロビジョニング + デプロイ
azd deploy        # 既存リソースへの再デプロイ
azd down          # リソース削除
```
