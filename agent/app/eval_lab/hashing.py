from __future__ import annotations

import hashlib
from pathlib import Path


_IGNORED_NAMES = {".DS_Store", "__pycache__", ".pytest_cache"}


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_NAMES for part in path.parts)


def hash_directory(path: Path) -> str:
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Path '{path}' is not an existing directory")

    root = path.resolve()
    digest = hashlib.sha256()
    files = [
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and not _is_ignored(candidate.relative_to(root))
    ]

    for file_path in sorted(files, key=lambda candidate: candidate.relative_to(root).as_posix()):
        relative_name = file_path.relative_to(root).as_posix().encode("utf-8")
        file_bytes = file_path.read_bytes()
        digest.update(relative_name)
        digest.update(b"\0")
        digest.update(str(len(file_bytes)).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_bytes)
        digest.update(b"\0")

    return digest.hexdigest()
