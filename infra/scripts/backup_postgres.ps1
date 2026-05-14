param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$OutputRoot = $env:BACKUP_OUTPUT_DIR
)

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $ProjectRoot "backups"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $OutputRoot $timestamp
$documentsPath = Join-Path $ProjectRoot "storage\documents"
$databaseOutput = Join-Path $backupDir "database.sql"
$documentsArchive = Join-Path $backupDir "documents.zip"
$metadataPath = Join-Path $backupDir "metadata.json"
$postgresUser = if ([string]::IsNullOrWhiteSpace($env:POSTGRES_USER)) { "bookkeeping" } else { $env:POSTGRES_USER }
$postgresDb = if ([string]::IsNullOrWhiteSpace($env:POSTGRES_DB)) { "bookkeeping_tax" } else { $env:POSTGRES_DB }
$containerDumpPath = "/tmp/bookkeeping-database.sql"

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

try {
    docker compose exec -T db pg_dump -U $postgresUser -d $postgresDb -f $containerDumpPath
    docker compose cp "db:${containerDumpPath}" $databaseOutput | Out-Null
}
finally {
    docker compose exec -T db rm -f $containerDumpPath | Out-Null
}

if (Test-Path $documentsPath) {
    Compress-Archive -Path (Join-Path $documentsPath "*") -DestinationPath $documentsArchive -Force
}

$metadata = [ordered]@{
    createdAt = (Get-Date).ToUniversalTime().ToString("o")
    projectRoot = $ProjectRoot
    databaseDump = "database.sql"
    documentsArchive = if (Test-Path $documentsArchive) { "documents.zip" } else { $null }
}
$metadata | ConvertTo-Json | Set-Content -Path $metadataPath

Write-Output "Backup completed: $backupDir"