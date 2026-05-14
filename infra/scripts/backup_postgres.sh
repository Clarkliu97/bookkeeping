#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="${PROJECT_ROOT:-$(cd "${script_dir}/../.." && pwd)}"
output_root="${BACKUP_OUTPUT_DIR:-${OUTPUT_ROOT:-${project_root}/backups}}"

timestamp="$(date -u +%Y%m%d_%H%M%S)"
backup_dir="${output_root}/${timestamp}"
documents_path="${project_root}/storage/documents"
database_output="${backup_dir}/database.sql"
documents_archive="${backup_dir}/documents.zip"
metadata_path="${backup_dir}/metadata.json"
postgres_user="${POSTGRES_USER:-bookkeeping}"
postgres_db="${POSTGRES_DB:-bookkeeping_tax}"

mkdir -p "${backup_dir}"

docker compose -f "${project_root}/docker-compose.yml" exec -T db \
  pg_dump -U "${postgres_user}" "${postgres_db}" > "${database_output}"

if [ -d "${documents_path}" ] && find "${documents_path}" -mindepth 1 -print -quit >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    DOCUMENTS_PATH="${documents_path}" DOCUMENTS_ARCHIVE="${documents_archive}" python3 - <<'PY'
import os
from pathlib import Path
import zipfile

documents_path = Path(os.environ["DOCUMENTS_PATH"])
archive_path = Path(os.environ["DOCUMENTS_ARCHIVE"])

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for source in documents_path.rglob("*"):
        if source.is_file():
            archive.write(source, source.relative_to(documents_path))
PY
  elif command -v zip >/dev/null 2>&1; then
    (
      cd "${documents_path}"
      zip -rq "${documents_archive}" .
    )
  else
    echo "Unable to create documents.zip. Install python3 or zip." >&2
    exit 1
  fi
fi

documents_archive_value="null"
if [ -f "${documents_archive}" ]; then
  documents_archive_value='"documents.zip"'
fi

cat > "${metadata_path}" <<EOF
{
  "createdAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "projectRoot": "${project_root}",
  "databaseDump": "database.sql",
  "documentsArchive": ${documents_archive_value}
}
EOF

echo "Backup completed: ${backup_dir}"