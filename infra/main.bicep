targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name used for naming and tagging.')
param environmentName string

@minLength(1)
@description('Azure region used for all regional resources.')
param location string

@description('Optional prefix used for globally unique resource names.')
param workloadName string = 'copilotmetrics'

@minValue(30)
@maxValue(730)
@description('Retention in days for the Log Analytics workspace.')
param logAnalyticsRetentionInDays int = 30

@description('App Service plan SKU for the shared dashboard/function hosting plan.')
param appServicePlanSkuName string = 'P1v3'

@minValue(1)
@maxValue(10)
@description('Worker count for the shared App Service plan.')
param appServicePlanWorkerCount int = 1

@description('Whether the shared App Service plan should be zone redundant.')
param appServicePlanZoneRedundant bool = false

@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
])
@description('Storage account redundancy SKU.')
param storageSkuName string = 'Standard_LRS'

@secure()
@description('Optional GitHub token to seed into Key Vault for the ingestion function app.')
param githubToken string = ''

@description('Blob container name for raw downloaded usage metric payloads.')
param rawMetricsContainerName string = 'raw-metrics'

@description('Blob container name for curated/normalized usage metric payloads.')
param curatedMetricsContainerName string = 'curated-metrics'

@description('Blob container name for dashboard-ready artifacts.')
param dashboardDataContainerName string = 'dashboard-data'

@description('Cosmos DB SQL database name.')
param cosmosDatabaseName string = 'copilotMetrics'

@description('Cosmos DB container name for usage metrics.')
param cosmosMetricsContainerName string = 'usageMetrics'

@description('Cosmos DB container name for ingestion run state and metadata.')
param cosmosIngestionRunsContainerName string = 'ingestionRuns'

@description('Cosmos DB container name for dashboard projections/views.')
param cosmosDashboardViewsContainerName string = 'dashboardViews'

var normalizedEnvironmentName = toLower(replace(replace(environmentName, '-', ''), '_', ''))
var normalizedWorkloadName = toLower(replace(replace(workloadName, '-', ''), '_', ''))
var uniqueSuffix = toLower(uniqueString(subscription().subscriptionId, environmentName, location))
var namingStem = take('${normalizedWorkloadName}${normalizedEnvironmentName}', 12)

var resourceGroupName = 'rg-${environmentName}'
var logAnalyticsWorkspaceName = 'log-${environmentName}'
var applicationInsightsName = 'appi-${environmentName}'
var appServicePlanName = 'asp-${environmentName}'
var dashboardAppName = 'app-${take(normalizedEnvironmentName, 18)}-${take(uniqueSuffix, 8)}'
var ingestionFunctionName = 'func-${take(normalizedEnvironmentName, 17)}-${take(uniqueSuffix, 8)}'
var storageAccountName = 'st${take(namingStem, 8)}${take(uniqueSuffix, 14)}'
var cosmosAccountName = 'cosmos-${take(namingStem, 12)}-${take(uniqueSuffix, 8)}'
var keyVaultName = 'kv-${take(namingStem, 11)}-${take(uniqueSuffix, 8)}'

var tags = {
  'azd-env-name': environmentName
  'azd-template': 'copilot-metrics-dashboard'
  'workload-name': workloadName
}

module rg 'modules/resource-group.bicep' = {
  name: '${environmentName}-resourceGroup'
  params: {
    location: location
    name: resourceGroupName
    tags: tags
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: '${environmentName}-monitoring'
  scope: resourceGroup(resourceGroupName)
  dependsOn: [
    rg
  ]
  params: {
    applicationInsightsName: applicationInsightsName
    location: location
    logAnalyticsRetentionInDays: logAnalyticsRetentionInDays
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: '${environmentName}-storage'
  scope: resourceGroup(resourceGroupName)
  dependsOn: [
    rg
  ]
  params: {
    curatedContainerName: curatedMetricsContainerName
    dashboardContainerName: dashboardDataContainerName
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: storageAccountName
    rawContainerName: rawMetricsContainerName
    skuName: storageSkuName
    tags: tags
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: '${environmentName}-cosmos'
  scope: resourceGroup(resourceGroupName)
  dependsOn: [
    rg
  ]
  params: {
    accountName: cosmosAccountName
    dashboardViewsContainerName: cosmosDashboardViewsContainerName
    databaseName: cosmosDatabaseName
    ingestionRunsContainerName: cosmosIngestionRunsContainerName
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    metricsContainerName: cosmosMetricsContainerName
    tags: tags
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: '${environmentName}-keyVault'
  scope: resourceGroup(resourceGroupName)
  dependsOn: [
    rg
  ]
  params: {
    githubToken: githubToken
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: keyVaultName
    tags: tags
  }
}

module appServicePlan 'modules/appserviceplan.bicep' = {
  name: '${environmentName}-appServicePlan'
  scope: resourceGroup(resourceGroupName)
  dependsOn: [
    rg
  ]
  params: {
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: appServicePlanName
    skuCapacity: appServicePlanWorkerCount
    skuName: appServicePlanSkuName
    tags: tags
    zoneRedundant: appServicePlanZoneRedundant
  }
}

module dashboardApp 'modules/webapp.bicep' = {
  name: '${environmentName}-dashboardApp'
  scope: resourceGroup(resourceGroupName)
  params: {
    appInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    appInsightsInstrumentationKey: monitoring.outputs.applicationInsightsInstrumentationKey
    appSettings: {
      DASHBOARD_DATA_PROXY_BASE_URL: 'https://${ingestionFunction.outputs.defaultHostname}/api/data'
    }
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: dashboardAppName
    serverFarmResourceId: appServicePlan.outputs.resourceId
    tags: tags
  }
}

module ingestionFunction 'modules/functionapp.bicep' = {
  name: '${environmentName}-ingestionFunction'
  scope: resourceGroup(resourceGroupName)
  params: {
    appInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    appInsightsInstrumentationKey: monitoring.outputs.applicationInsightsInstrumentationKey
    appSettings: {
      COPILOT_METRICS_SOURCE: 'mock'
      AZURE_COSMOS_DASHBOARD_VIEWS_CONTAINER_NAME: cosmos.outputs.dashboardViewsContainerName
      AZURE_COSMOS_DATABASE_NAME: cosmos.outputs.databaseName
      AZURE_COSMOS_ENDPOINT: cosmos.outputs.endpoint
      AZURE_COSMOS_INGESTION_RUNS_CONTAINER_NAME: cosmos.outputs.ingestionRunsContainerName
      AZURE_COSMOS_METRICS_CONTAINER_NAME: cosmos.outputs.metricsContainerName
      KEY_VAULT_URI: keyVault.outputs.uri
      METRICS_STORAGE_ACCOUNT_NAME: storage.outputs.name
      METRICS_STORAGE_BLOB_ENDPOINT: storage.outputs.primaryBlobEndpoint
      METRICS_CURATED_CONTAINER: storage.outputs.curatedContainerName
      METRICS_DASHBOARD_CONTAINER: storage.outputs.dashboardContainerName
      METRICS_RAW_CONTAINER: storage.outputs.rawContainerName
    }
    keyVaultName: keyVault.outputs.name
    keyVaultUri: keyVault.outputs.uri
    location: location
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: ingestionFunctionName
    serverFarmResourceId: appServicePlan.outputs.resourceId
    storageAccountName: storage.outputs.name
    tags: tags
  }
}

module rbac 'modules/rbac.bicep' = {
  name: '${environmentName}-rbac'
  scope: resourceGroup(resourceGroupName)
  params: {
    cosmosAccountName: cosmos.outputs.name
    cosmosDatabaseName: cosmos.outputs.databaseName
    curatedContainerName: storage.outputs.curatedContainerName
    dashboardContainerName: storage.outputs.dashboardContainerName
    dashboardPrincipalId: dashboardApp.outputs.?systemAssignedPrincipalId ?? ''
    ingestionPrincipalId: ingestionFunction.outputs.?systemAssignedPrincipalId ?? ''
    keyVaultName: keyVault.outputs.name
    rawContainerName: storage.outputs.rawContainerName
    storageAccountName: storage.outputs.name
  }
}

output AZURE_RESOURCE_GROUP_NAME string = rg.outputs.name
output DASHBOARD_APP_NAME string = dashboardApp.outputs.name
output DASHBOARD_APP_URL string = 'https://${dashboardApp.outputs.defaultHostname}'
output INGESTION_FUNCTION_APP_NAME string = ingestionFunction.outputs.name
output INGESTION_FUNCTION_APP_URL string = 'https://${ingestionFunction.outputs.defaultHostname}'
output LOG_ANALYTICS_WORKSPACE_NAME string = monitoring.outputs.logAnalyticsWorkspaceName
output STORAGE_ACCOUNT_NAME string = storage.outputs.name
output STORAGE_BLOB_ENDPOINT string = storage.outputs.primaryBlobEndpoint
output KEY_VAULT_NAME string = keyVault.outputs.name
output KEY_VAULT_URI string = keyVault.outputs.uri
output COSMOS_DB_ACCOUNT_NAME string = cosmos.outputs.name
output COSMOS_DB_ENDPOINT string = cosmos.outputs.endpoint
output COSMOS_DB_DATABASE_NAME string = cosmos.outputs.databaseName
#disable-next-line outputs-should-not-contain-secrets
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
