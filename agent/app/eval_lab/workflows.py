from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .schemas import WorkflowManifest


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Workflow manifest '{path}' does not exist")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"Workflow manifest '{path}' must contain a mapping")
    return dict(data)


def load_workflow_manifest(path: Path) -> WorkflowManifest:
    manifest = WorkflowManifest.model_validate(_load_yaml(path))
    _validate_node_ids(manifest)
    _validate_dependencies(manifest)
    _validate_acyclic(manifest)
    return manifest


def _validate_node_ids(manifest: WorkflowManifest) -> None:
    seen: set[str] = set()
    for node in manifest.nodes:
        if node.id in seen:
            raise ValueError(f"Duplicate workflow node id: {node.id}")
        seen.add(node.id)


def _validate_dependencies(manifest: WorkflowManifest) -> None:
    node_ids = {node.id for node in manifest.nodes}
    for node in manifest.nodes:
        for dependency in node.needs:
            if dependency not in node_ids:
                raise ValueError(f"Workflow node '{node.id}' has unknown dependency '{dependency}'")


def _validate_acyclic(manifest: WorkflowManifest) -> None:
    dependencies = {node.id: set(node.needs) for node in manifest.nodes}
    resolved: set[str] = set()
    remaining = dict(dependencies)

    while remaining:
        ready = sorted(node_id for node_id, needs in remaining.items() if needs <= resolved)
        if not ready:
            cycle_nodes = ", ".join(sorted(remaining))
            raise ValueError(f"Workflow contains a dependency cycle involving: {cycle_nodes}")
        for node_id in ready:
            resolved.add(node_id)
            remaining.pop(node_id)
