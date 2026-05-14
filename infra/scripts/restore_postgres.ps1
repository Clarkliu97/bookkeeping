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
        $restoreDocumentsScript = @'
import shutil
import zipfile
from pathlib import Path

archive_path = Path("/restore-backup/documents.zip")
documents_path = Path("/app/storage/documents")

if documents_path.exists():
    shutil.rmtree(documents_path)

documents_path.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(documents_path)
'@

        $restoreDocumentsScript | docker compose run --rm --no-deps -T -u 0 -v "${BackupDir}:/restore-backup:ro" api python -
    }

    Write-Output "Restore completed from: $BackupDir"
}
finally {
    Pop-Location
}