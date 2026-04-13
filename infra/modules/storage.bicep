@description('Storage account name.')
param name string

@description('Azure region for the storage account.')
param location string

@description('Blob container name for raw data.')
param rawContainerName string

@description('Blob container name for curated data.')
param curatedContainerName string

@description('Blob container name for dashboard-ready data.')
param dashboardContainerName string

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
])
@description('Storage account redundancy SKU.')
param skuName string = 'Standard_LRS'

@description('Tags applied to the storage account.')
param tags object = {}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: skuName
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
    encryption: {
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: true
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    changeFeed: {
      enabled: true
    }
    containerDeleteRetentionPolicy: {
      days: 7
      enabled: true
    }
    deleteRetentionPolicy: {
      days: 7
      enabled: true
    }
    isVersioningEnabled: true
  }
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: rawContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource curatedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: curatedContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource dashboardContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: dashboardContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource storageDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: storage
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

output name string = storage.name
output resourceId string = storage.id
output primaryBlobEndpoint string = storage.properties.primaryEndpoints.blob
output primaryQueueEndpoint string = storage.properties.primaryEndpoints.queue
output primaryTableEndpoint string = storage.properties.primaryEndpoints.table
output rawContainerName string = rawContainer.name
output curatedContainerName string = curatedContainer.name
output dashboardContainerName string = dashboardContainer.name
