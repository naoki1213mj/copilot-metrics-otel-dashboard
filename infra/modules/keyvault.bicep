@description('Key Vault name.')
param name string

@description('Azure region for the Key Vault.')
param location string

@description('Optional GitHub token value to seed into Key Vault.')
@secure()
param githubToken string = ''

@description('Log Analytics workspace resource ID used for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Tags applied to the Key Vault.')
param tags object = {}

var githubTokenSecretName = 'github-token'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    accessPolicies: []
    enablePurgeProtection: true
    enableRbacAuthorization: true
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    publicNetworkAccess: 'Enabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
    softDeleteRetentionInDays: 90
    tenantId: tenant().tenantId
  }
}

resource githubTokenSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(githubToken)) {
  parent: keyVault
  name: githubTokenSecretName
  properties: {
    attributes: {
      enabled: true
    }
    contentType: 'text/plain'
    value: githubToken
  }
}

resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: keyVault
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

output name string = keyVault.name
output resourceId string = keyVault.id
output uri string = keyVault.properties.vaultUri
output githubTokenSecretName string = githubTokenSecretName
#disable-next-line outputs-should-not-contain-secrets
output hasGithubToken bool = !empty(githubToken)