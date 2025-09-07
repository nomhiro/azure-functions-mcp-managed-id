@description('Base name (function app & related resources)')
param baseName string
@description('Location (use region supported by Flex Consumption)')
param location string
@description('Python runtime version (supported: 3.10, 3.11, 3.12)')
@allowed([
  '3.10'
  '3.11'
  '3.12'
])
param pythonVersion string = '3.11'
@description('Zone redundant plan (Flex Consumption supports in some regions)')
param zoneRedundant bool = false
@description('Maximum instance count (omit if 0)')
param maximumInstanceCount int = 0
@description('Instance memory MB (allowed: 1024,1536,2048; 0 to omit)')
param instanceMemoryMB int = 0
@description('Always ready entries: [{ name: "http"|"function:<name>", instanceCount: <int> }]')
param alwaysReady array = []
@description('Use managed identity based AzureWebJobsStorage (recommended)')
param useManagedIdentityStorage bool = false
@description('Create deployment blob container and configure functionAppConfig.deployment')
param createDeploymentContainer bool = true
@description('Extra app settings array of objects { name, value }')
param extraAppSettings array = []
@description('Custom tags')
param tags object = {}

// Names
var planName = 'plan-${baseName}'
var storageName = toLower('st${uniqueString(resourceGroup().id, baseName)}')
// Token for generating deployment container name similar to sample reference
var resourceToken = toLower(uniqueString(resourceGroup().id, baseName, location))
var deploymentContainerName = 'app-package-${take(baseName,32)}-${take(resourceToken,7)}'

// Storage
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

var storageKeys = storage.listKeys()
var storageAccountKey = storageKeys.keys[0].value
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccountKey}'

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${baseName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'ApplicationInsights'
  }
  tags: tags
}

// Flex Consumption Plan (Linux) - reserved true per docs
resource functionPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  zoneRedundant: zoneRedundant
  }
  tags: tags
}

// Build functionAppConfig object explicitly (no union complexity) for clarity
var functionAppConfigObj = union({
  runtime: {
    name: 'python'
    version: pythonVersion
  }
}, (maximumInstanceCount > 0 || instanceMemoryMB > 0 || length(alwaysReady) > 0) ? {
  scaleAndConcurrency: union(
    (maximumInstanceCount > 0 ? { maximumInstanceCount: maximumInstanceCount } : {}),
    (instanceMemoryMB > 0 ? { instanceMemoryMB: instanceMemoryMB } : {}),
    (length(alwaysReady) > 0 ? { alwaysReady: alwaysReady } : {})
  )
} : {}, createDeploymentContainer ? {
  deployment: {
    storage: {
      type: 'blobContainer'
      value: 'https://${storage.name}.blob.${environment().suffixes.storage}/${deploymentContainerName}'
      authentication: {
        type: 'SystemAssignedIdentity'
      }
    }
  }
} : {})

// Optional deployment container (private)
resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (createDeploymentContainer) {
  name: '${storage.name}/default/${deploymentContainerName}'
  properties: {
    publicAccess: 'None'
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: baseName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    httpsOnly: true
    serverFarmId: functionPlan.id
    functionAppConfig: functionAppConfigObj
    siteConfig: {
      appSettings: concat([
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        // Storage identity-based or connection string
        (useManagedIdentityStorage ? { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' } : null)
        (useManagedIdentityStorage ? { name: 'AzureWebJobsStorage__accountName', value: storage.name } : null)
        (useManagedIdentityStorage ? { name: 'AzureWebJobsStorage__blobServiceUri', value: 'https://${storage.name}.blob.${environment().suffixes.storage}' } : null)
        (useManagedIdentityStorage ? { name: 'AzureWebJobsStorage__queueServiceUri', value: 'https://${storage.name}.queue.${environment().suffixes.storage}' } : null)
        (!useManagedIdentityStorage ? { name: 'AzureWebJobsStorage', value: storageConnectionString } : null)
      ], extraAppSettings)
    }
  }
  tags: tags
  dependsOn: createDeploymentContainer ? [ deploymentContainer ] : []
}

// RBAC (only Blob & Queue which Functions actually needs). Table omitted to stay least-privilege.
resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useManagedIdentityStorage) {
  name: guid(storage.id, 'blob-role', functionApp.id)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
resource storageQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useManagedIdentityStorage) {
  name: guid(storage.id, 'queue-role', functionApp.id)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = functionApp.name
output principalId string = functionApp.identity.principalId
output storageConnection string = storageConnectionString
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output deploymentContainer string = createDeploymentContainer ? deploymentContainerName : ''
