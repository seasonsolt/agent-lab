from __future__ import annotations

import uuid

import pytest

from app.eval_lab.db import init_schema
from app.eval_lab.repository import EvalRepository


def test_repository_persists_eval_run():
    init_schema()
    repo = EvalRepository()
    suffix = uuid.uuid4().hex
    skill_id = f"repo-test-skill-{suffix}"
    task_pack_id = f"repo-test-pack-{suffix}"

    skill = repo.upsert_skill(
        skill_id=skill_id,
        name="Repo Test Skill",
        version_hash="hash-skill",
        source_type="local_dir",
        source_path=f"/lab/skills/{skill_id}",
        manifest={"id": skill_id, "name": "Repo Test Skill"},
    )
    task_pack = repo.upsert_task_pack(
        task_pack_id=task_pack_id,
        name="Repo Test Pack",
        domain="coding",
        version_hash="hash-pack",
        source_path=f"/lab/task_packs/{task_pack_id}",
        manifest={"id": task_pack_id, "name": "Repo Test Pack", "domain": "coding"},
    )
    run = repo.create_eval_run(skill["id"], task_pack["id"])
    repo.mark_run_running(run["id"], sandbox_container_id="container-1")
    repo.add_score(run["id"], "task-1", "auto", 70, 100, {"tests_passed": True})
    repo.finish_run(run["id"], "passed", ["trace-1"])

    stored_skill = repo.get_skill(skill["id"])
    stored_task_pack = repo.get_task_pack(task_pack["id"])
    stored_run = repo.get_eval_run(run["id"])
    scores = repo.list_scores(run["id"])

    assert stored_skill["manifest"] == {"id": skill_id, "name": "Repo Test Skill"}
    assert stored_task_pack["manifest"] == {"id": task_pack_id, "name": "Repo Test Pack", "domain": "coding"}
    assert stored_run["status"] == "passed"
    assert stored_run["sandbox_container_id"] == "container-1"
    assert stored_run["langfuse_trace_ids"] == ["trace-1"]
    assert scores[0]["score"] == 70
    assert scores[0]["details"] == {"tests_passed": True}


def test_repository_rejects_missing_run_updates():
    init_schema()
    repo = EvalRepository()

    with pytest.raises(KeyError):
        repo.mark_run_running("missing-run", sandbox_container_id="container-1")

    with pytest.raises(KeyError):
        repo.finish_run("missing-run", "failed", [])
