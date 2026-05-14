SUSPICIOUS_WINDOWS_MOJIBAKE_MARKERS = (
    "鈥",
    "揂",
    "揇",
    "慒",
    "慍",
    "憈",
    "慶",
    "慳",
    "慓",
)

_CP936_BYTE_REPLACEMENTS = (
    (bytes((0xE2, 0x80, 0x3F)), bytes((0xE2, 0x80, 0x94))),
)


def looks_like_windows_mojibake(text: str | None) -> bool:
    if not text:
        return False
    return any(marker in text for marker in SUSPICIOUS_WINDOWS_MOJIBAKE_MARKERS)


def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in SUSPICIOUS_WINDOWS_MOJIBAKE_MARKERS)


def repair_windows_mojibake(text: str | None) -> str | None:
    if text is None or not looks_like_windows_mojibake(text):
        return text

    try:
        encoded = text.encode("cp936")
    except UnicodeEncodeError:
        return text

    repaired_bytes = encoded
    for source_bytes, target_bytes in _CP936_BYTE_REPLACEMENTS:
        repaired_bytes = repaired_bytes.replace(source_bytes, target_bytes)

    try:
        repaired = repaired_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return text

    if _mojibake_score(repaired) >= _mojibake_score(text):
        return text

    return repaired