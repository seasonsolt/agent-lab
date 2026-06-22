from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def ensure_child_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents:
        return resolved_candidate
    raise ValueError(f"Path '{candidate}' is outside '{root}'")


@dataclass(frozen=True)
class PathMapping:
    host_project_dir: Path
    container_project_dir: Path
    host_runs_dir: Path
    container_runs_dir: Path

    def host_to_container_project_path(self, path: Path) -> Path:
        try:
            resolved = ensure_child_path(self.host_project_dir, path)
        except ValueError as exc:
            raise ValueError(f"Path '{path}' is outside project root '{self.host_project_dir}'") from exc
        relative = resolved.relative_to(self.host_project_dir.resolve())
        return self.container_project_dir / relative

    def host_run_path(self, run_id: str) -> Path:
        try:
            return ensure_child_path(self.host_runs_dir, self.host_runs_dir / run_id)
        except ValueError as exc:
            raise ValueError(f"Run path '{run_id}' is outside runs root '{self.host_runs_dir}'") from exc

    def container_run_path(self, run_id: str) -> Path:
        try:
            return ensure_child_path(self.container_runs_dir, self.container_runs_dir / run_id)
        except ValueError as exc:
            raise ValueError(f"Run path '{run_id}' is outside runs root '{self.container_runs_dir}'") from exc
