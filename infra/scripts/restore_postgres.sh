#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: sh infra/scripts/restore_postgres.sh BACKUP_DIR" >&2
  exit 1
fi

script_dir="$(cd "$(dirname -- "$0")" && pwd)"
project_root="${PROJECT_ROOT:-$(cd "${script_dir}/../.." && pwd)}"

if ! backup_dir="$(cd "$1" 2>/dev/null && pwd)"; then
  echo "Backup directory not found: $1" >&2
  exit 1
fi

database_input="${backup_dir}/database.sql"
documents_archive="${backup_dir}/documents.zip"
documents_path="${project_root}/storage/documents"
postgres_user="${POSTGRES_USER:-bookkeeping}"
postgres_db="${POSTGRES_DB:-bookkeeping_tax}"

if [ ! -f "${database_input}" ]; then
  echo "database.sql not found in ${backup_dir}" >&2
  exit 1
fi

docker compose -f "${project_root}/docker-compose.yml" exec -T db \
  psql -U "${postgres_user}" -d "${postgres_db}" < "${database_input}"

if [ -f "${documents_archive}" ]; then
  rm -rf "${documents_path}"
  mkdir -p "${documents_path}"

  if command -v python3 >/dev/null 2>&1; then
    DOCUMENTS_ARCHIVE="${documents_archive}" DOCUMENTS_PATH="${documents_path}" python3 - <<'PY'
import os
from pathlib import Path
import zipfile

archive_path = Path(os.environ["DOCUMENTS_ARCHIVE"])
documents_path = Path(os.environ["DOCUMENTS_PATH"])

with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(documents_path)
PY
  elif command -v unzip >/dev/null 2>&1; then
    unzip -oq "${documents_archive}" -d "${documents_path}"
  else
    echo "Unable to restore documents.zip. Install python3 or unzip." >&2
    exit 1
  fi
fi

echo "Restore completed from: ${backup_dir}"