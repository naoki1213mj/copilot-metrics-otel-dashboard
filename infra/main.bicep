targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd 環境名')
param environmentName string

@minLength(1)
@description('リソースのデプロイ先リージョン')
param location string

var tags = {
  'azd-env-name': environmentName
}

var resourceGroupName = 'rg-${environmentName}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'staticWebApp'
  scope: rg
  params: {
    name: 'swa-${environmentName}'
    location: 'eastasia'
    tags: tags
  }
}

output AZURE_STATIC_WEB_APP_NAME string = staticWebApp.outputs.name
output AZURE_STATIC_WEB_APP_HOSTNAME string = staticWebApp.outputs.hostname
