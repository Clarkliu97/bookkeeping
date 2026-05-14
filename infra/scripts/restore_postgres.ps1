param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [string]$ProjectRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$databaseInput = Join-Path $BackupDir "database.sql"
$documentsArchive = Join-Path $BackupDir "documents.zip"
$documentsPath = Join-Path $ProjectRoot "storage\documents"
$postgresUser = if ([string]::IsNullOrWhiteSpace($env:POSTGRES_USER)) { "bookkeeping" } else { $env:POSTGRES_USER }
$postgresDb = if ([string]::IsNullOrWhiteSpace($env:POSTGRES_DB)) { "bookkeeping_tax" } else { $env:POSTGRES_DB }

if (-not (Test-Path $databaseInput)) {
    throw "database.sql not found in $BackupDir"
}

Push-Location $ProjectRoot

try {
    docker compose exec -T db dropdb --if-exists --force -U $postgresUser $postgresDb
    docker compose exec -T db createdb -U $postgresUser $postgresDb

    Get-Content $databaseInput | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $postgresUser -d $postgresDb

    if (Test-Path $documentsArchive) {
        Remove-Item $documentsPath -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $documentsPath -Force | Out-Null
        Expand-Archive -Path $documentsArchive -DestinationPath $documentsPath -Force
    }

    Write-Output "Restore completed from: $BackupDir"
}
finally {
    Pop-Location
}