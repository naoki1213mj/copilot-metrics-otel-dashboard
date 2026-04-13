@description('Storage account name.')
param storageAccountName string

@description('Blob container name for raw data.')
param rawContainerName string

@description('Blob container name for curated data.')
param curatedContainerName string

@description('Blob container name for dashboard-ready data.')
param dashboardContainerName string

@description('Key Vault name.')
param keyVaultName string

@description('Cosmos DB account name.')
param cosmosAccountName string

@description('Cosmos DB SQL database name.')
param cosmosDatabaseName string

@description('Dashboard web app principal ID.')
param dashboardPrincipalId string = ''

@description('Ingestion function app principal ID.')
param ingestionPrincipalId string = ''

var storageBlobDataReaderRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var storageBlobDataOwnerRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var storageTableDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
var keyVaultSecretsOfficerRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storageAccount
  name: 'default'
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: rawContainerName
}

resource curatedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: curatedContainerName
}

resource dashboardContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: dashboardContainerName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' existing = {
  parent: cosmosAccount
  name: cosmosDatabaseName
}

var cosmosDatabaseScope = replace(cosmosDatabase.id, '/sqlDatabases/', '/dbs/')
var cosmosDataReaderRoleDefinitionId = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001'
var cosmosDataContributorRoleDefinitionId = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'

resource dashboardDashboardContainerReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(dashboardPrincipalId)) {
  name: guid(dashboardContainer.id, dashboardPrincipalId, storageBlobDataReaderRoleDefinitionId)
  scope: dashboardContainer
  properties: {
    principalId: dashboardPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
  }
}

resource ingestionRawContainerContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(rawContainer.id, ingestionPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: rawContainer
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource ingestionCuratedContainerContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(curatedContainer.id, ingestionPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: curatedContainer
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource ingestionDashboardContainerContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(dashboardContainer.id, ingestionPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: dashboardContainer
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource ingestionHostStorageBlobOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(storageAccount.id, ingestionPrincipalId, storageBlobDataOwnerRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataOwnerRoleDefinitionId
  }
}

resource ingestionHostStorageTableContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(storageAccount.id, ingestionPrincipalId, storageTableDataContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageTableDataContributorRoleDefinitionId
  }
}

resource ingestionKeyVaultSecretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(ingestionPrincipalId)) {
  name: guid(keyVault.id, ingestionPrincipalId, keyVaultSecretsOfficerRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: ingestionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsOfficerRoleDefinitionId
  }
}

resource dashboardCosmosDataReader 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (!empty(dashboardPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosDatabaseScope, dashboardPrincipalId, cosmosDataReaderRoleDefinitionId)
  properties: {
    principalId: dashboardPrincipalId
    roleDefinitionId: cosmosDataReaderRoleDefinitionId
    scope: cosmosDatabaseScope
  }
}

resource ingestionCosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (!empty(ingestionPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosDatabaseScope, ingestionPrincipalId, cosmosDataContributorRoleDefinitionId)
  properties: {
    principalId: ingestionPrincipalId
    roleDefinitionId: cosmosDataContributorRoleDefinitionId
    scope: cosmosDatabaseScope
  }
}
