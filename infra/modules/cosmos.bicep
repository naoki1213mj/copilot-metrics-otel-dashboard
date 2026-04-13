@description('Azure Cosmos DB account name.')
param accountName string

@description('Azure region for Cosmos DB.')
param location string

@description('Cosmos DB SQL database name.')
param databaseName string

@description('Cosmos DB container name for usage metrics.')
param metricsContainerName string

@description('Cosmos DB container name for ingestion run metadata.')
param ingestionRunsContainerName string

@description('Cosmos DB container name for dashboard projections.')
param dashboardViewsContainerName string

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Tags applied to Cosmos DB resources.')
param tags object = {}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous30Days'
      }
    }
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    databaseAccountOfferType: 'Standard'
    disableKeyBasedMetadataWriteAccess: false
    disableLocalAuth: true
    enableAutomaticFailover: false
    enableFreeTier: false
    enableMultipleWriteLocations: false
    locations: [
      {
        failoverPriority: 0
        isZoneRedundant: false
        locationName: location
      }
    ]
    publicNetworkAccess: 'Enabled'
  }
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: cosmosDb
  name: databaseName
  properties: {
    options: {}
    resource: {
      id: databaseName
    }
  }
}

resource metricsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: metricsContainerName
  properties: {
    options: {}
    resource: {
      defaultTtl: -1
      id: metricsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/organization'
        ]
      }
    }
  }
}

resource ingestionRunsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: ingestionRunsContainerName
  properties: {
    options: {}
    resource: {
      defaultTtl: -1
      id: ingestionRunsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/runType'
        ]
      }
    }
  }
}

resource dashboardViewsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: sqlDatabase
  name: dashboardViewsContainerName
  properties: {
    options: {}
    resource: {
      defaultTtl: -1
      id: dashboardViewsContainerName
      partitionKey: {
        kind: 'Hash'
        paths: [
          '/viewType'
        ]
      }
    }
  }
}

resource cosmosDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${accountName}-diagnostics'
  scope: cosmosDb
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

output name string = cosmosDb.name
output resourceId string = cosmosDb.id
output endpoint string = cosmosDb.properties.documentEndpoint
output databaseName string = sqlDatabase.name
output metricsContainerName string = metricsContainer.name
output ingestionRunsContainerName string = ingestionRunsContainer.name
output dashboardViewsContainerName string = dashboardViewsContainer.name
