from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from typing import Iterator


@dataclass(frozen=True)
class ExternalSkillRepo:
    repo_url: str
    skill_path: str
    clone_dir: Path
    skill_dir: Path
    commit: str


@contextmanager
def clone_external_skill_repo(
    repo_url: str,
    skill_path: str,
    clone_root: Path,
) -> Iterator[ExternalSkillRepo]:
    clone_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="repo-", dir=clone_root) as tmp:
        clone_dir = Path(tmp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        commit = _git_commit(clone_dir)
        skill_dir = _resolve_child_path(clone_dir, skill_path)
        if not (skill_dir / "SKILL.md").is_file():
            raise ValueError(f"External skill path '{skill_path}' does not contain SKILL.md")
        _ensure_manifest(skill_dir)
        yield ExternalSkillRepo(
            repo_url=repo_url,
            skill_path=skill_path,
            clone_dir=clone_dir,
            skill_dir=skill_dir,
            commit=commit,
        )


def _git_commit(repo_dir: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _resolve_child_path(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("External skill path must be relative")
    resolved_root = root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate == resolved_root or resolved_root in candidate.parents:
        return candidate
    raise ValueError(f"External skill path '{relative_path}' is outside cloned repository")


def _ensure_manifest(skill_dir: Path) -> None:
    manifest_path = skill_dir / "manifest.yaml"
    if manifest_path.exists():
        return
    skill_id = skill_dir.name
    manifest_path.write_text(
        f"id: {skill_id}\nname: {skill_id}\nentry: SKILL.md\ntags:\n  - external\n",
        encoding="utf-8",
    )
