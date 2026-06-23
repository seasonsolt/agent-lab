from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .schemas import SkillManifest, TaskPackManifest, TaskSpec


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Manifest '{path}' does not exist")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"YAML file '{path}' must contain a mapping")
    return dict(data)


def load_skill_manifest(skill_dir: Path) -> SkillManifest:
    manifest = SkillManifest.model_validate(_load_yaml(skill_dir / "manifest.yaml"))
    entry = skill_dir / manifest.entry
    if manifest.entry != "SKILL.md":
        raise ValueError("Skill manifest entry must be exactly SKILL.md")
    if not entry.exists() or not entry.is_file():
        raise ValueError("Skill manifest entry SKILL.md must exist")
    return manifest


def _resolve_task_path(task_pack_dir: Path, task: TaskSpec, field_name: str) -> Path:
    raw_path = getattr(task, field_name)
    if Path(raw_path).is_absolute():
        raise ValueError(f"Task '{task.id}' {field_name} path must be relative")
    resolved_root = task_pack_dir.resolve()
    resolved_path = (task_pack_dir / raw_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Task '{task.id}' {field_name} path is outside task pack")
    if not resolved_path.exists():
        raise ValueError(f"Task '{task.id}' {field_name} path does not exist: {raw_path}")
    return resolved_path


def _resolve_optional_task_path(task_pack_dir: Path, task: TaskSpec, field_name: str) -> Path | None:
    raw_path = getattr(task, field_name)
    if raw_path is None:
        return None
    if Path(raw_path).is_absolute():
        raise ValueError(f"Task '{task.id}' {field_name} path must be relative")
    resolved_root = task_pack_dir.resolve()
    resolved_path = (task_pack_dir / raw_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Task '{task.id}' {field_name} path is outside task pack")
    if not resolved_path.exists():
        raise ValueError(f"Task '{task.id}' {field_name} path does not exist: {raw_path}")
    return resolved_path


def load_task_pack_manifest(task_pack_dir: Path) -> TaskPackManifest:
    manifest = TaskPackManifest.model_validate(_load_yaml(task_pack_dir / "taskpack.yaml"))
    for task in manifest.tasks:
        fixture = _resolve_task_path(task_pack_dir, task, "fixture")
        expected = _resolve_task_path(task_pack_dir, task, "expected")
        scorer = _resolve_task_path(task_pack_dir, task, "scorer")
        if not fixture.is_dir():
            raise ValueError(f"Task '{task.id}' fixture path must be a directory")
        if not expected.is_dir():
            raise ValueError(f"Task '{task.id}' expected path must be a directory")
        if not scorer.is_file():
            raise ValueError(f"Task '{task.id}' scorer path must be a file")
        workflow = _resolve_optional_task_path(task_pack_dir, task, "workflow")
        if workflow is not None and not workflow.is_file():
            raise ValueError(f"Task '{task.id}' workflow path must be a file")
    return manifest
