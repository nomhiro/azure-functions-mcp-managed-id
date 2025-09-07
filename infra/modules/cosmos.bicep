@description('Cosmos DB account base name (will be normalized)')
param baseName string
@description('Location')
param location string
@description('Enable Free Tier (only one per subscription)')
param enableFreeTier bool = false
@description('Database name to create')
param databaseName string = 'course'
@description('Container (array) names to create')
param containerNames array = [
  'courses'
  'serveys'
  'users'
]
@description('Partition key path for all containers')
param partitionKey string = '/id'
@description('Tags')
param tags object = {}

// Naming
var accountName = toLower(baseName)

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: enableFreeTier
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: [
      { name: 'EnableServerless' }
    ]
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  name: databaseName
  parent: cosmosAccount
  properties: {
    resource: { id: databaseName }
  }
}

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containerNames: {
  name: c
  parent: cosmosDatabase
  properties: {
    resource: {
      id: c
      partitionKey: {
        paths: [ partitionKey ]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: -1
    }
  }
}]

var cosmosKeys = cosmosAccount.listKeys()

output accountNameOut string = cosmosAccount.name
output endpoint string = cosmosAccount.properties.documentEndpoint
@secure()
output primaryKey string = cosmosKeys.primaryMasterKey
output database string = databaseName
output containers array = containerNames
