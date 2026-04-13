@description('Web app name.')
param name string

@description('Azure region for the web app.')
param location string

@description('App Service plan resource ID.')
param serverFarmResourceId string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Application Insights instrumentation key.')
param appInsightsInstrumentationKey string

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Additional app settings for the dashboard web app.')
param appSettings object = {}

@description('Tags applied to the dashboard web app.')
param tags object = {}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  kind: 'app,linux'
  tags: union(tags, {
    'azd-service-name': 'dashboard'
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    clientAffinityEnabled: false
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    serverFarmId: serverFarmResourceId
    siteConfig: {
      alwaysOn: true
      ftpsState: 'Disabled'
      http20Enabled: true
      linuxFxVersion: 'NODE|22-lts'
      minTlsVersion: '1.2'
    }
  }
}

resource appSettingsResource 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: app
  name: 'appsettings'
  properties: union({
    APPINSIGHTS_INSTRUMENTATIONKEY: appInsightsInstrumentationKey
    APPLICATIONINSIGHTS_CONNECTION_STRING: appInsightsConnectionString
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    WEBSITE_NODE_DEFAULT_VERSION: '~22'
  }, appSettings)
}

resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: app
  properties: {
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
    workspaceId: logAnalyticsWorkspaceResourceId
  }
}

output name string = app.name
output resourceId string = app.id
output defaultHostname string = app.properties.defaultHostName
output systemAssignedPrincipalId string? = app.identity.principalId
