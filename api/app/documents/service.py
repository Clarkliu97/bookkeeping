from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import get_settings


def document_storage_root() -> Path:
    root = Path(get_settings().document_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_document_bytes(*, company_id: UUID, original_filename: str, content: bytes) -> tuple[str, str, str, int]:
    checksum = sha256(content).hexdigest()
    extension = Path(original_filename).suffix
    stored_filename = f"{uuid4()}{extension}"
    relative_path = Path(str(company_id)) / stored_filename
    absolute_path = document_storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    return stored_filename, relative_path.as_posix(), checksum, len(content)


def resolve_document_path(storage_path: str) -> Path:
    root = document_storage_root()
    normalized_storage_path = storage_path.strip()
    candidates = [
        root / normalized_storage_path,
        root / normalized_storage_path.replace("\\", "/"),
        root / normalized_storage_path.replace("/", "\\"),
    ]

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    return candidates[0]
