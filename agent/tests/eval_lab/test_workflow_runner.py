from __future__ import annotations

from pathlib import Path
from typing import Any

from app.eval_lab.sandbox import SandboxRunResult
from app.eval_lab.schemas import WorkflowManifest, WorkflowNodeSpec
from app.eval_lab.workflow_runner import WorkflowRunner


class FakeSandbox:
    def __init__(self) -> None:
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
        (workspace_host_dir / "fixed.txt").write_text("fixed\n", encoding="utf-8")
        return SandboxRunResult(
            task_id=task_id,
            status="passed",
            agent_output="fixed",
            changed_files=["fixed.txt"],
            trace_ids=["trace-agent"],
        )


def workflow_manifest() -> WorkflowManifest:
    return WorkflowManifest(
        id="static-quality",
        name="Static Quality",
        max_parallel_nodes=2,
        nodes=[
            WorkflowNodeSpec(
                id="scan",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="continue_with_artifact",
                command="python -c \"print('scan finding')\"",
                outputs=["scan.txt"],
            ),
            WorkflowNodeSpec(
                id="aggregate",
                type="aggregate",
                needs=["scan"],
                timeout_seconds=5,
                on_failure="fail_workflow",
                inputs=["scan"],
                outputs=["aggregate.md"],
            ),
            WorkflowNodeSpec(
                id="agent_fix",
                type="coding_agent",
                needs=["aggregate"],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Fix the Java issue.",
                inputs=["aggregate"],
            ),
        ],
    )


def test_workflow_runner_executes_nodes_and_records_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    sandbox = FakeSandbox()

    result = WorkflowRunner(sandbox=sandbox).run(
        manifest=workflow_manifest(),
        run_id="eval-1",
        task_id="case-1",
        task_prompt="Fix it.",
        skill_host_dir=skill,
        fixture_host_dir=fixture,
        workspace_host_dir=workspace,
        network_enabled=False,
        timeout_seconds=60,
    )

    assert result.status == "passed"
    assert [node.node_id for node in result.nodes] == ["scan", "aggregate", "agent_fix"]
    assert result.trace_ids == ["trace-agent"]
    assert sandbox.calls[0]["task_prompt"].count("scan finding") == 1
    assert (workspace / ".agent-lab" / "artifacts" / "aggregate.md").exists()


def test_workflow_runner_continues_with_artifact_for_allowed_tool_failure(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    manifest = WorkflowManifest(
        id="scan-failure",
        name="Scan Failure",
        nodes=[
            WorkflowNodeSpec(
                id="scan",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="continue_with_artifact",
                command="python -c \"import sys; print('scanner failed'); sys.exit(7)\"",
                outputs=["scan.txt"],
            )
        ],
    )

    result = WorkflowRunner(sandbox=FakeSandbox()).run(
        manifest=manifest,
        run_id="eval-1",
        task_id="case-1",
        task_prompt="Fix it.",
        skill_host_dir=skill,
        fixture_host_dir=fixture,
        workspace_host_dir=workspace,
        network_enabled=False,
        timeout_seconds=60,
    )

    assert result.status == "passed"
    assert result.nodes[0].status == "passed"
    assert result.nodes[0].error is not None
    assert "scanner failed" in (workspace / ".agent-lab" / "artifacts" / "scan.txt").read_text(encoding="utf-8")


def test_workflow_runner_fails_workflow_for_required_tool_failure(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    manifest = WorkflowManifest(
        id="required-failure",
        name="Required Failure",
        nodes=[
            WorkflowNodeSpec(
                id="scan",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"import sys; sys.exit(7)\"",
            )
        ],
    )

    result = WorkflowRunner(sandbox=FakeSandbox()).run(
        manifest=manifest,
        run_id="eval-1",
        task_id="case-1",
        task_prompt="Fix it.",
        skill_host_dir=skill,
        fixture_host_dir=fixture,
        workspace_host_dir=workspace,
        network_enabled=False,
        timeout_seconds=60,
    )

    assert result.status == "failed"
    assert result.nodes[0].status == "failed"
