from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval_lab.runner import EvalRunner
from app.eval_lab.sandbox import SandboxRunResult


class FakeRepository:
    def __init__(self) -> None:
        self.skills: list[dict[str, Any]] = []
        self.task_packs: list[dict[str, Any]] = []
        self.runs: dict[str, dict[str, Any]] = {}
        self.scores: list[dict[str, Any]] = []
        self.running_marks: list[dict[str, str]] = []
        self.finished: list[dict[str, Any]] = []

    def upsert_skill(
        self,
        skill_id: str,
        name: str,
        version_hash: str,
        source_type: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        skill = {
            "id": skill_id,
            "name": name,
            "version_hash": version_hash,
            "source_type": source_type,
            "source_path": source_path,
            "manifest": manifest,
        }
        self.skills.append(skill)
        return skill

    def upsert_task_pack(
        self,
        task_pack_id: str,
        name: str,
        domain: str,
        version_hash: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        task_pack = {
            "id": task_pack_id,
            "name": name,
            "domain": domain,
            "version_hash": version_hash,
            "source_path": source_path,
            "manifest": manifest,
        }
        self.task_packs.append(task_pack)
        return task_pack

    def create_eval_run(self, skill_id: str, task_pack_id: str) -> dict[str, Any]:
        run = {
            "id": "eval-1",
            "skill_id": skill_id,
            "task_pack_id": task_pack_id,
            "status": "queued",
            "sandbox_container_id": None,
            "langfuse_trace_ids": [],
            "error": None,
        }
        self.runs[run["id"]] = run
        return run

    def mark_run_running(self, run_id: str, sandbox_container_id: str) -> None:
        self.running_marks.append({"run_id": run_id, "sandbox_container_id": sandbox_container_id})
        self.runs[run_id]["status"] = "running"
        self.runs[run_id]["sandbox_container_id"] = sandbox_container_id

    def finish_run(self, run_id: str, status: str, trace_ids: list[str], error: str | None = None) -> None:
        self.finished.append({"run_id": run_id, "status": status, "trace_ids": trace_ids, "error": error})
        self.runs[run_id]["status"] = status
        self.runs[run_id]["langfuse_trace_ids"] = trace_ids
        self.runs[run_id]["error"] = error

    def add_score(
        self,
        eval_run_id: str,
        task_id: str,
        score_type: str,
        score: float,
        max_score: float,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        score_record = {
            "eval_run_id": eval_run_id,
            "task_id": task_id,
            "score_type": score_type,
            "score": score,
            "max_score": max_score,
            "details": details,
        }
        self.scores.append(score_record)
        return score_record

    def get_eval_run(self, run_id: str) -> dict[str, Any]:
        return self.runs[run_id]


class FakeSandbox:
    def __init__(self, result_status: str = "passed") -> None:
        self.result_status = result_status
        self.calls: list[dict[str, Any]] = []

    def run_task(
        self,
        run_id: str,
        task_id: str,
        task_prompt: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool | None = None,
        timeout_seconds: int | None = None,
    ) -> SandboxRunResult:
        self.calls.append(
            {
                "run_id": run_id,
                "task_id": task_id,
                "task_prompt": task_prompt,
                "skill_host_dir": skill_host_dir,
                "fixture_host_dir": fixture_host_dir,
                "workspace_host_dir": workspace_host_dir,
                "network_enabled": network_enabled,
                "timeout_seconds": timeout_seconds,
            }
        )
        workspace_host_dir.mkdir(parents=True, exist_ok=True)
        (workspace_host_dir / "changed.txt").write_text("changed\n", encoding="utf-8")
        return SandboxRunResult(
            task_id=task_id,
            status=self.result_status,
            agent_output="agent output",
            changed_files=["changed.txt"],
            trace_ids=["trace-1"],
        )


class FakeWorkflowRunner:
    def __init__(
        self,
        workflow_status: str = "passed",
        sandbox_result: SandboxRunResult | None = None,
        node_status: str = "passed",
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.workflow_status = workflow_status
        self.sandbox_result = sandbox_result
        self.node_status = node_status

    def run(
        self,
        manifest,
        run_id: str,
        task_id: str,
        task_prompt: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
        sandbox_workspace_host_dir: Path | None = None,
    ):
        self.calls.append(
            {
                "manifest_id": manifest.id,
                "run_id": run_id,
                "task_id": task_id,
                "task_prompt": task_prompt,
                "skill_host_dir": skill_host_dir,
                "fixture_host_dir": fixture_host_dir,
                "workspace_host_dir": workspace_host_dir,
                "sandbox_workspace_host_dir": sandbox_workspace_host_dir,
                "network_enabled": network_enabled,
                "timeout_seconds": timeout_seconds,
            }
        )

        from app.eval_lab.schemas import WorkflowNodeRecord
        from app.eval_lab.workflow_runner import WorkflowRunResult

        return WorkflowRunResult(
            status=self.workflow_status,
            nodes=[
                WorkflowNodeRecord(
                    node_id="scan",
                    node_type="tool",
                    status=self.node_status,
                    duration_ms=1,
                    artifact_paths=[".agent-lab/artifacts/scan.txt"],
                )
            ],
            trace_ids=["trace-workflow"],
            sandbox_result=self.sandbox_result,
        )


def write_skill(skill_dir: Path) -> None:
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n", encoding="utf-8")
    (skill_dir / "manifest.yaml").write_text(
        "id: demo-skill\nname: Demo Skill\nentry: SKILL.md\ntags:\n  - coding\n",
        encoding="utf-8",
    )


def write_task_pack(task_pack_dir: Path) -> None:
    task_dir = task_pack_dir / "tasks" / "fix-1"
    fixture = task_dir / "fixture"
    expected = task_dir / "expected"
    fixture.mkdir(parents=True)
    expected.mkdir()
    (fixture / "input.txt").write_text("before\n", encoding="utf-8")
    (expected / "input.txt").write_text("after\n", encoding="utf-8")
    (task_dir / "scorer.py").write_text(
        "import json\n"
        "print(json.dumps({'score': 9, 'max_score': 10, 'details': {'ok': True}}))\n",
        encoding="utf-8",
    )
    (task_pack_dir / "taskpack.yaml").write_text(
        "id: basic-pack\n"
        "name: Basic Pack\n"
        "domain: coding\n"
        "tasks:\n"
        "  - id: fix-1\n"
        "    type: coding\n"
        "    prompt: Fix the file.\n"
        "    fixture: tasks/fix-1/fixture\n"
        "    expected: tasks/fix-1/expected\n"
        "    scorer: tasks/fix-1/scorer.py\n"
        "    max_score: 10\n",
        encoding="utf-8",
    )


def write_workflow_task_pack(task_pack_dir: Path) -> None:
    task_dir = task_pack_dir / "tasks" / "fix-1"
    workflow_dir = task_pack_dir / "workflows"
    fixture = task_dir / "fixture"
    expected = task_dir / "expected"
    fixture.mkdir(parents=True)
    expected.mkdir()
    workflow_dir.mkdir()
    (fixture / "input.txt").write_text("before\n", encoding="utf-8")
    (task_dir / "scorer.py").write_text(
        "import json\n"
        "print(json.dumps({'score': 1, 'max_score': 1, 'details': {'ok': True}}))\n",
        encoding="utf-8",
    )
    (workflow_dir / "static-quality.yaml").write_text(
        "id: static-quality\n"
        "name: Static Quality\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "    command: python -c \"print('scan')\"\n",
        encoding="utf-8",
    )
    (task_pack_dir / "taskpack.yaml").write_text(
        "id: workflow-pack\n"
        "name: Workflow Pack\n"
        "domain: java\n"
        "tasks:\n"
        "  - id: fix-1\n"
        "    type: coding\n"
        "    track: static-quality\n"
        "    capability: resource-management\n"
        "    workflow: workflows/static-quality.yaml\n"
        "    prompt: Fix the file.\n"
        "    fixture: tasks/fix-1/fixture\n"
        "    expected: tasks/fix-1/expected\n"
        "    scorer: tasks/fix-1/scorer.py\n"
        "    max_score: 1\n",
        encoding="utf-8",
    )


def write_task_pack_with_task_id(task_pack_dir: Path, task_id: str) -> None:
    task_dir = task_pack_dir / "tasks" / "fix-1"
    fixture = task_dir / "fixture"
    expected = task_dir / "expected"
    fixture.mkdir(parents=True)
    expected.mkdir()
    (fixture / "input.txt").write_text("before\n", encoding="utf-8")
    (expected / "input.txt").write_text("after\n", encoding="utf-8")
    (task_dir / "scorer.py").write_text(
        "import json\n"
        "print(json.dumps({'score': 1, 'max_score': 1, 'details': {}}))\n",
        encoding="utf-8",
    )
    (task_pack_dir / "taskpack.yaml").write_text(
        "id: basic-pack\n"
        "name: Basic Pack\n"
        "domain: coding\n"
        "tasks:\n"
        f"  - id: {json.dumps(task_id)}\n"
        "    type: coding\n"
        "    prompt: Fix the file.\n"
        "    fixture: tasks/fix-1/fixture\n"
        "    expected: tasks/fix-1/expected\n"
        "    scorer: tasks/fix-1/scorer.py\n"
        "    max_score: 1\n",
        encoding="utf-8",
    )


def test_eval_runner_happy_path_uses_repo_sandbox_scorer_and_run_dir(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "runs"
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox = FakeSandbox()

    run = EvalRunner(repo=repo, sandbox=sandbox, runs_root=runs_root).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=True,
        timeout_seconds=12,
    )

    assert run["status"] == "passed"
    assert repo.skills[0]["id"] == "demo-skill"
    assert repo.skills[0]["manifest"]["tags"] == ["coding"]
    assert repo.task_packs[0]["id"] == "basic-pack"
    assert repo.task_packs[0]["manifest"]["tasks"][0]["id"] == "fix-1"
    assert repo.running_marks == [{"run_id": "eval-1", "sandbox_container_id": str(runs_root / "eval-1")}]
    assert sandbox.calls[0]["network_enabled"] is True
    assert sandbox.calls[0]["timeout_seconds"] == 12
    assert (sandbox.calls[0]["workspace_host_dir"] / "input.txt").read_text(encoding="utf-8") == "before\n"
    output_path = runs_root / "eval-1" / "fix-1" / "agent_output.json"
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "passed"
    assert repo.scores == [
        {
            "eval_run_id": "eval-1",
            "task_id": "fix-1",
            "score_type": "auto",
            "score": 9.0,
            "max_score": 10.0,
            "details": {
                "ok": True,
                "scorer_score": 9.0,
                "scorer_max_score": 10.0,
                "sandbox_status": "passed",
                "sandbox_changed_files": ["changed.txt"],
                "sandbox_error": None,
                "workflow_nodes": [],
            },
        }
    ]
    assert repo.finished == [{"run_id": "eval-1", "status": "passed", "trace_ids": ["trace-1"], "error": None}]


def test_eval_runner_maps_container_run_workspace_to_host_sandbox_path(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    host_runs_root = tmp_path / "host-runs"
    container_runs_root = tmp_path / "container-runs"
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox = FakeSandbox()

    run = EvalRunner(
        repo=repo,
        sandbox=sandbox,
        runs_root=container_runs_root,
        host_runs_root=host_runs_root,
    ).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=True,
        timeout_seconds=12,
    )

    assert run["status"] == "passed"
    assert (container_runs_root / "eval-1" / "fix-1" / "input.txt").read_text(encoding="utf-8") == "before\n"
    assert (container_runs_root / "eval-1" / "fix-1" / "agent_output.json").exists()
    assert sandbox.calls[0]["workspace_host_dir"] == host_runs_root / "eval-1" / "fix-1"
    assert sandbox.calls[0]["fixture_host_dir"] == task_pack_dir / "tasks" / "fix-1" / "fixture"
    assert repo.running_marks == [
        {"run_id": "eval-1", "sandbox_container_id": str(container_runs_root / "eval-1")}
    ]


def test_eval_runner_replaces_existing_run_dir(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "runs"
    stale_dir = runs_root / "eval-1"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.txt").write_text("stale\n", encoding="utf-8")
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)

    run = EvalRunner(repo=FakeRepository(), sandbox=FakeSandbox(), runs_root=runs_root).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "passed"
    assert not (stale_dir / "stale.txt").exists()


def test_eval_runner_rejects_task_id_path_escape(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "runs"
    write_skill(skill_dir)
    write_task_pack_with_task_id(task_pack_dir, "../escape")
    repo = FakeRepository()

    run = EvalRunner(repo=repo, sandbox=FakeSandbox(), runs_root=runs_root).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "error"
    assert "outside" in repo.finished[0]["error"]
    assert not (tmp_path / "escape").exists()


def test_eval_runner_normalizes_scorer_score_to_task_max_score(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)
    repo = FakeRepository()

    EvalRunner(repo=repo, sandbox=FakeSandbox(), runs_root=tmp_path / "runs").run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert repo.scores[0]["score"] == 9.0
    assert repo.scores[0]["max_score"] == 10.0
    assert repo.scores[0]["details"]["scorer_score"] == 9.0


def test_eval_runner_failed_sandbox_status_finishes_not_passed_and_keeps_traces(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox = FakeSandbox(result_status="failed")

    run = EvalRunner(repo=repo, sandbox=sandbox, runs_root=tmp_path / "runs").run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "failed"
    assert repo.finished == [{"run_id": "eval-1", "status": "failed", "trace_ids": ["trace-1"], "error": None}]
    assert repo.scores[0]["score_type"] == "auto"


def test_eval_runner_error_sandbox_status_finishes_error_and_keeps_traces(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    write_skill(skill_dir)
    write_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox = FakeSandbox(result_status="error")

    run = EvalRunner(repo=repo, sandbox=sandbox, runs_root=tmp_path / "runs").run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "failed"
    assert repo.finished == [{"run_id": "eval-1", "status": "failed", "trace_ids": ["trace-1"], "error": None}]
    assert repo.scores[0]["score_type"] == "auto"
    assert repo.scores[0]["details"]["sandbox_status"] == "error"


def test_eval_runner_finish_status_is_conservative_for_empty_tasks(tmp_path):
    runner = EvalRunner(repo=FakeRepository(), sandbox=FakeSandbox(), runs_root=tmp_path / "runs")

    assert runner._finish_status([]) == "error"
    assert runner._task_status_from_score(6, 10, "passed") == "passed"
    assert runner._task_status_from_score(9, 10, "error") == "failed"


def test_eval_runner_uses_workflow_runner_when_task_has_workflow(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "container-runs"
    host_runs_root = tmp_path / "host-runs"
    write_skill(skill_dir)
    write_workflow_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox = FakeSandbox()
    workflow_runner = FakeWorkflowRunner()

    run = EvalRunner(
        repo=repo,
        sandbox=sandbox,
        workflow_runner=workflow_runner,
        runs_root=runs_root,
        host_runs_root=host_runs_root,
    ).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "passed"
    assert sandbox.calls == []
    assert workflow_runner.calls[0]["manifest_id"] == "static-quality"
    assert workflow_runner.calls[0]["workspace_host_dir"] == runs_root / "eval-1" / "fix-1"
    assert workflow_runner.calls[0]["sandbox_workspace_host_dir"] == host_runs_root / "eval-1" / "fix-1"
    assert repo.finished == [{"run_id": "eval-1", "status": "passed", "trace_ids": ["trace-workflow"], "error": None}]
    assert repo.scores[0]["details"]["workflow_nodes"][0]["node_id"] == "scan"


def test_eval_runner_preserves_failed_workflow_status_with_passed_sandbox_result(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "runs"
    write_skill(skill_dir)
    write_workflow_task_pack(task_pack_dir)
    repo = FakeRepository()
    sandbox_result = SandboxRunResult(
        task_id="fix-1-scan",
        status="passed",
        agent_output="agent output",
        changed_files=["changed.txt"],
        trace_ids=["trace-sandbox"],
    )
    workflow_runner = FakeWorkflowRunner(
        workflow_status="failed",
        sandbox_result=sandbox_result,
        node_status="failed",
    )

    run = EvalRunner(
        repo=repo,
        sandbox=FakeSandbox(),
        workflow_runner=workflow_runner,
        runs_root=runs_root,
    ).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "failed"
    assert repo.finished == [{"run_id": "eval-1", "status": "failed", "trace_ids": ["trace-workflow"], "error": None}]
    assert repo.scores[0]["details"]["sandbox_status"] == "passed"
    assert repo.scores[0]["details"]["workflow_status"] == "failed"
    assert repo.scores[0]["details"]["workflow_nodes"][0]["status"] == "failed"
