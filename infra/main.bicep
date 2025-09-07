@description('Azure region for all resources')
@allowed([
  'japaneast'
  'japanwest'
  'eastasia'
  'southeastasia'
  'eastus'
  'westeurope'
])
param location string = 'japaneast'

@description('Environment name (azd environment). Used in resource naming)')
param envName string

@description('Enable Cosmos DB Free Tier (only one per subscription).')
param enableFreeTier bool = false

@description('Python version for the Function App runtime')
@allowed([
  '3.10'
  '3.11'
  '3.12'
])
param pythonVersion string = '3.11'

@description('Custom tags to apply to all resources')
param tags object = {}

@description('Use managed identity for AzureWebJobsStorage (adds RBAC on storage).')
param useManagedIdentityStorage bool = true

@description('Function App maximum instance count (0 = unset)')
param functionMaximumInstanceCount int = 0

@description('Function App instance memory MB (allowed 1024,1536,2048. 0 = unset)')
param functionInstanceMemoryMB int = 0

@description('Function App always ready entries (e.g. [{ name: "http", instanceCount: 2 }])')
param functionAlwaysReady array = []

@description('Optional function app name prefix (leave empty to auto-generate)')
param functionNamePrefix string = ''

// Module: Cosmos
module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    baseName: 'cos-${uniqueString(resourceGroup().id, envName)}'
    location: location
    enableFreeTier: enableFreeTier
    databaseName: 'course'
    containerNames: [
      'courses'
      'serveys'
      'users'
    ]
    tags: union(tags, { 'azd-env-name': envName })
  }
}

// Extra app settings to inject cosmos info
var extraFuncSettings = [
  {
    name: 'COSMOSDB_ACCOUNT_ENDPOINT'
    value: cosmos.outputs.endpoint
  }
  {
    name: 'COSMOSDB_DATABASE'
    value: cosmos.outputs.database
  }
]

// Module: Function App
module functionApp 'modules/functionapp.bicep' = {
  name: 'functionApp'
  params: {
  // global unique function app name: prefix or generated
  baseName: empty(functionNamePrefix) ? 'func-${envName}-${uniqueString(resourceGroup().id, envName)}' : functionNamePrefix
    location: location
    pythonVersion: pythonVersion
  maximumInstanceCount: functionMaximumInstanceCount
  instanceMemoryMB: functionInstanceMemoryMB
  alwaysReady: functionAlwaysReady
  useManagedIdentityStorage: useManagedIdentityStorage
    extraAppSettings: extraFuncSettings
    tags: union(tags, { 'azd-env-name': envName })
  }
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output functionAppPrincipalId string = functionApp.outputs.principalId
output cosmosEndpoint string = cosmos.outputs.endpoint
@secure()
output cosmosPrimaryKey string = cosmos.outputs.primaryKey
output cosmosDatabaseName string = cosmos.outputs.database
output cosmosContainerNames array = cosmos.outputs.containers
