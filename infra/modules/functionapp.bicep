@description('Function app name.')
param name string

@description('Azure region for the function app.')
param location string

@description('App Service plan resource ID.')
param serverFarmResourceId string

@description('Storage account name used by Azure Functions host storage.')
param storageAccountName string

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('Application Insights instrumentation key.')
param appInsightsInstrumentationKey string

@description('Key Vault name used by app settings references.')
param keyVaultName string

@description('Key Vault URI surfaced to the function app settings.')
param keyVaultUri string

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Additional app settings for the ingestion function app.')
param appSettings object = {}

@description('Tags applied to the ingestion function app.')
param tags object = {}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  kind: 'functionapp,linux'
  tags: union(tags, {
    'azd-service-name': 'ingestion'
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
      linuxFxVersion: 'PYTHON|3.13'
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
    AzureWebJobsSecretStorageKeyVaultUri: keyVaultUri
    AzureWebJobsSecretStorageType: 'keyvault'
    AzureWebJobsStorage__blobServiceUri: 'https://${storageAccountName}.blob.core.windows.net'
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__queueServiceUri: 'https://${storageAccountName}.queue.core.windows.net'
    AzureWebJobsStorage__tableServiceUri: 'https://${storageAccountName}.table.core.windows.net'
    ENABLE_ORYX_BUILD: 'true'
    FUNCTIONS_EXTENSION_VERSION: '~4'
    FUNCTIONS_WORKER_RUNTIME: 'python'
     KEY_VAULT_NAME: keyVaultName
     KEY_VAULT_URI: keyVaultUri
     SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
   }, appSettings)
 }

resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
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
