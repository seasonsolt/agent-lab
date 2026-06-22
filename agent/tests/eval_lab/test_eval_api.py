from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.eval_lab import routing as eval_routing
from app.main import app


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        skill_dir: Path,
        task_pack_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "skill_dir": skill_dir,
                "task_pack_dir": task_pack_dir,
                "network_enabled": network_enabled,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": [],
            "error": None,
        }


class FakeRepo:
    def __init__(self, missing: bool = False) -> None:
        self.missing = missing

    def get_eval_run(self, run_id: str) -> dict[str, Any]:
        if self.missing:
            raise KeyError(run_id)
        return {
            "id": run_id,
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "sandbox_container_id": None,
            "langfuse_trace_ids": ["trace-1"],
            "error": None,
        }

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        return {
            "id": skill_id,
            "name": "Skill",
            "version_hash": "skill-hash",
            "manifest": {"tags": []},
        }

    def get_task_pack(self, task_pack_id: str) -> dict[str, Any]:
        return {
            "id": task_pack_id,
            "name": "Pack",
            "domain": "coding",
            "version_hash": "pack-hash",
        }

    def list_scores(self, eval_run_id: str) -> list[dict[str, Any]]:
        return [
            {
                "task_id": "task-1",
                "score_type": "auto",
                "score": 100,
                "max_score": 100,
                "details": {},
            }
        ]


def test_create_eval_run_uses_safe_paths_and_returns_report_url(monkeypatch, tmp_path):
    runner = FakeRunner()
    monkeypatch.setattr(eval_routing, "get_runner", lambda: runner)
    monkeypatch.setattr(Settings, "eval_lab_host_project_dir", str(tmp_path))
    monkeypatch.setattr(Settings, "eval_lab_network_enabled", False)
    monkeypatch.setattr(Settings, "eval_lab_task_timeout_seconds", 123)
    skill = tmp_path / "skill"
    pack = tmp_path / "pack"
    skill.mkdir()
    pack.mkdir()

    with TestClient(app) as client:
        response = client.post(
            "/eval-runs",
            json={"skill_path": str(skill), "task_pack_path": str(pack)},
        )

    assert response.status_code == 200
    assert response.json() == {"id": "run-1", "status": "passed", "report_url": "/eval-runs/run-1/report"}
    assert runner.calls == [
        {
            "skill_dir": skill.resolve(),
            "task_pack_dir": pack.resolve(),
            "network_enabled": False,
            "timeout_seconds": 123,
        }
    ]


def test_get_eval_run(monkeypatch):
    monkeypatch.setattr(eval_routing, "get_repo", lambda: FakeRepo())

    with TestClient(app) as client:
        response = client.get("/eval-runs/run-1")

    assert response.status_code == 200
    assert response.json()["id"] == "run-1"
    assert response.json()["status"] == "passed"


def test_get_eval_run_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(eval_routing, "get_repo", lambda: FakeRepo(missing=True))

    with TestClient(app) as client:
        response = client.get("/eval-runs/missing")

    assert response.status_code == 404


def test_get_report(monkeypatch):
    monkeypatch.setattr(eval_routing, "get_repo", lambda: FakeRepo())

    with TestClient(app) as client:
        response = client.get("/eval-runs/run-1/report")

    assert response.status_code == 200
    assert response.json()["eval_run_id"] == "run-1"
    assert response.json()["final_score"] == 70
    assert response.json()["trace_ids"] == ["trace-1"]


def test_create_eval_run_rejects_paths_outside_project(monkeypatch, tmp_path):
    runner = FakeRunner()
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    monkeypatch.setattr(eval_routing, "get_runner", lambda: runner)
    monkeypatch.setattr(Settings, "eval_lab_host_project_dir", str(project))

    with TestClient(app) as client:
        responses = [
            client.post(
                "/eval-runs",
                json={"skill_path": str(outside / "skill"), "task_pack_path": str(project / "pack")},
            ),
            client.post(
                "/eval-runs",
                json={"skill_path": str(project / "skill"), "task_pack_path": str(outside / "pack")},
            ),
        ]

    assert [response.status_code for response in responses] == [400, 400]
    assert runner.calls == []
