@description('App Service plan name.')
param name string

@description('Azure region for the App Service plan.')
param location string

@description('App Service plan SKU name.')
param skuName string = 'P1v3'

@minValue(1)
@maxValue(10)
@description('Worker count for the App Service plan.')
param skuCapacity int = 1

@description('Whether the App Service plan should be zone redundant.')
param zoneRedundant bool = false

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Tags applied to the App Service plan.')
param tags object = {}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: name
  location: location
  kind: 'linux'
  tags: tags
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  properties: {
    reserved: true
    zoneRedundant: zoneRedundant
  }
}

resource planDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: plan
  properties: {
    logAnalyticsDestinationType: 'Dedicated'
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
    workspaceId: logAnalyticsWorkspaceResourceId
  }
}

output name string = plan.name
output resourceId string = plan.id
