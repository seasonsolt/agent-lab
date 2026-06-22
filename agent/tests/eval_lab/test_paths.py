from pathlib import Path

import pytest

from app.eval_lab.paths import PathMapping, ensure_child_path


def test_host_to_container_path_maps_project_child():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    assert mapping.host_to_container_project_path(Path("/host/project/skills/demo")) == Path("/lab/skills/demo")


def test_host_to_container_path_rejects_external_path():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    with pytest.raises(ValueError, match="outside project root"):
        mapping.host_to_container_project_path(Path("/tmp/skills/demo"))


def test_ensure_child_path_rejects_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError, match="outside"):
        ensure_child_path(root, root.parent / "escape")


def test_host_run_path_rejects_traversal():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    with pytest.raises(ValueError, match="outside runs root"):
        mapping.host_run_path("../escape")


def test_container_run_path_rejects_absolute_path():
    mapping = PathMapping(
        host_project_dir=Path("/host/project"),
        container_project_dir=Path("/lab"),
        host_runs_dir=Path("/host/runs"),
        container_runs_dir=Path("/runs"),
    )

    with pytest.raises(ValueError, match="outside runs root"):
        mapping.container_run_path("/tmp/escape")
