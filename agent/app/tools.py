from __future__ import annotations

import os
from pathlib import Path

from .config import Settings


WORKSPACE = Path(Settings.workspace).resolve()


def _ensure_workspace_path(path: str) -> Path:
    """Resolve a workspace-relative or absolute path and enforce it stays inside the workspace."""

    if path.startswith("/"):
        target = Path(path).resolve()
    else:
        target = (WORKSPACE / path).resolve()

    root = WORKSPACE.as_posix()
    candidate = target.as_posix()

    if candidate != root and not candidate.startswith(root + os.sep):
        raise ValueError(f"Path '{path}' is outside workspace")

    return target


def list_workspace(path: str = ".") -> str:
    """Return a sorted, newline-separated listing of workspace directory contents."""

    folder = _ensure_workspace_path(path)
    if not folder.exists():
        return f"Path '{path}' does not exist."
    if not folder.is_dir():
        return f"Path '{path}' is not a directory."
    entries = sorted(item.name for item in folder.iterdir())
    return "\n".join(entries) if entries else "Directory is empty."


def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a file from the workspace and return UTF-8 text, optionally truncated."""

    file_path = _ensure_workspace_path(path)
    if not file_path.exists():
        return f"File '{path}' does not exist."
    if not file_path.is_file():
        return f"Path '{path}' is not a file."
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + f"... [truncated {len(text) - max_chars} chars]"
    return text


def write_file(path: str, content: str) -> str:
    """Write text content to a workspace file path, creating directories if needed."""

    file_path = _ensure_workspace_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {str(file_path)}."
