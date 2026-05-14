#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: sh infra/scripts/restore_postgres.sh BACKUP_DIR" >&2
  exit 1
fi

script_dir="$(cd "$(dirname -- "$0")" && pwd)"
project_root="${PROJECT_ROOT:-$(cd "${script_dir}/../.." && pwd)}"

host_path_for_docker() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    printf '%s' "$1"
  fi
}

if ! backup_dir="$(cd "$1" 2>/dev/null && pwd)"; then
  echo "Backup directory not found: $1" >&2
  exit 1
fi

backup_dir_mount="$(host_path_for_docker "${backup_dir}")"

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
  dropdb --if-exists --force -U "${postgres_user}" "${postgres_db}"

docker compose -f "${project_root}/docker-compose.yml" exec -T db \
  createdb -U "${postgres_user}" "${postgres_db}"

docker compose -f "${project_root}/docker-compose.yml" exec -T db \
  psql -v ON_ERROR_STOP=1 -U "${postgres_user}" -d "${postgres_db}" < "${database_input}"

if [ -f "${documents_archive}" ]; then
  cat <<'PY' | docker compose -f "${project_root}/docker-compose.yml" run --rm --no-deps -T -u 0 \
    -v "${backup_dir_mount}:/restore-backup:ro" api python -
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
PY
fi

echo "Restore completed from: ${backup_dir}"