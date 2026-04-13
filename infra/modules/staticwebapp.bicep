@description('Static Web App のリソース名')
param name string

@description('デプロイ先リージョン')
param location string

@description('リソースタグ')
param tags object

resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': 'dashboard'
  })
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

output name string = staticWebApp.name
output hostname string = staticWebApp.properties.defaultHostname
output id string = staticWebApp.id
