from __future__ import annotations

import time
from pathlib import Path
from threading import Lock
from typing import Any

import pytest

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


class TimedSandbox(FakeSandbox):
    def __init__(self) -> None:
        super().__init__()
        self.started: list[tuple[str, float]] = []
        self.active = 0
        self.max_observed_active = 0
        self._lock = Lock()

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
        with self._lock:
            self.active += 1
            self.max_observed_active = max(self.max_observed_active, self.active)
            self.started.append((task_id, time.monotonic()))
        try:
            time.sleep(0.2)
            return super().run_task(
                run_id=run_id,
                task_id=task_id,
                task_prompt=task_prompt,
                skill_host_dir=skill_host_dir,
                fixture_host_dir=fixture_host_dir,
                workspace_host_dir=workspace_host_dir,
                network_enabled=network_enabled,
                timeout_seconds=timeout_seconds,
            )
        finally:
            with self._lock:
                self.active -= 1


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


@pytest.mark.parametrize(
    "unsafe_output",
    [
        "/tmp/scan.txt",
        "../scan.txt",
        "nested/scan.txt",
        "nested\\scan.txt",
    ],
)
def test_workflow_runner_rejects_unsafe_output_artifact_names(tmp_path, unsafe_output):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    manifest = WorkflowManifest(
        id="unsafe-output",
        name="Unsafe Output",
        nodes=[
            WorkflowNodeSpec(
                id="scan",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"print('scan')\"",
                outputs=[unsafe_output],
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
    assert "Unsafe workflow artifact output name" in result.nodes[0].error
    assert not (workspace / ".agent-lab" / "scan.txt").exists()
    assert not (workspace / ".agent-lab" / "artifacts" / "nested").exists()


def test_workflow_runner_rejects_unsafe_fallback_artifact_name_from_node_id(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    manifest = WorkflowManifest(
        id="unsafe-fallback-output",
        name="Unsafe Fallback Output",
        nodes=[
            WorkflowNodeSpec(
                id="../../../escaped",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"print('scan')\"",
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
    assert "Unsafe workflow artifact output name" in result.nodes[0].error
    assert not (workspace / "escaped.txt").exists()
    assert not (workspace.parent / "escaped.txt").exists()


def test_workflow_runner_agent_prompt_uses_declared_dependency_output_name(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    sandbox = FakeSandbox()
    manifest = WorkflowManifest(
        id="declared-output",
        name="Declared Output",
        nodes=[
            WorkflowNodeSpec(
                id="scan",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"print('{\\\"finding\\\": true}')\"",
                outputs=["scan.json"],
            ),
            WorkflowNodeSpec(
                id="agent_fix",
                type="coding_agent",
                needs=["scan"],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Use the JSON scan output.",
            ),
        ],
    )

    result = WorkflowRunner(sandbox=sandbox).run(
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
    assert "Workflow artifact from scan (scan.json):" in sandbox.calls[0]["task_prompt"]
    assert sandbox.calls[0]["task_prompt"].count('"finding": true') == 1


def test_workflow_runner_limits_ready_batch_parallelism_with_deterministic_records(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    sandbox = TimedSandbox()
    manifest = WorkflowManifest(
        id="parallel-agents",
        name="Parallel Agents",
        max_parallel_nodes=2,
        nodes=[
            WorkflowNodeSpec(
                id="agent_a",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Fix A.",
            ),
            WorkflowNodeSpec(
                id="agent_b",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Fix B.",
            ),
            WorkflowNodeSpec(
                id="agent_c",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Fix C.",
            ),
        ],
    )

    result = WorkflowRunner(sandbox=sandbox).run(
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
    assert [node.node_id for node in result.nodes] == ["agent_a", "agent_b", "agent_c"]
    assert len(sandbox.started) == 3
    assert abs(sandbox.started[0][1] - sandbox.started[1][1]) < 0.15
    assert sandbox.max_observed_active > 1
    assert sandbox.max_observed_active <= 2


def test_workflow_runner_limits_nodes_with_same_parallelism_key(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    sandbox = TimedSandbox()
    manifest = WorkflowManifest(
        id="parallel-key",
        name="Parallel Key",
        max_parallel_nodes=3,
        nodes=[
            WorkflowNodeSpec(
                id="agent_a",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                max_parallelism_key="llm",
                prompt="Fix A.",
            ),
            WorkflowNodeSpec(
                id="agent_b",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                max_parallelism_key="llm",
                prompt="Fix B.",
            ),
            WorkflowNodeSpec(
                id="agent_c",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                max_parallelism_key="other",
                prompt="Fix C.",
            ),
        ],
    )

    result = WorkflowRunner(sandbox=sandbox).run(
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
    assert [node.node_id for node in result.nodes] == ["agent_a", "agent_c", "agent_b"]
    assert len(sandbox.started) == 3
    assert abs(sandbox.started[0][1] - sandbox.started[1][1]) < 0.15
    assert sandbox.started[2][1] - sandbox.started[0][1] >= 0.15
    assert sandbox.max_observed_active <= 2


def test_workflow_runner_reads_only_declared_input_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    sandbox = FakeSandbox()
    manifest = WorkflowManifest(
        id="declared-inputs",
        name="Declared Inputs",
        nodes=[
            WorkflowNodeSpec(
                id="scan_a",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"print('include me')\"",
                outputs=["scan_a.txt"],
            ),
            WorkflowNodeSpec(
                id="scan_b",
                type="tool",
                needs=[],
                timeout_seconds=5,
                on_failure="fail_workflow",
                command="python -c \"print('do not include me')\"",
                outputs=["scan_b.txt"],
            ),
            WorkflowNodeSpec(
                id="agent_fix",
                type="coding_agent",
                needs=["scan_a", "scan_b"],
                inputs=["scan_a"],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Use declared evidence only.",
            ),
        ],
    )

    result = WorkflowRunner(sandbox=sandbox).run(
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
    prompt = sandbox.calls[0]["task_prompt"]
    assert "include me" in prompt
    assert "do not include me" not in prompt


def test_workflow_runner_fails_consumer_when_declared_input_artifact_is_missing(tmp_path):
    workspace = tmp_path / "workspace"
    fixture = tmp_path / "fixture"
    skill = tmp_path / "skill"
    workspace.mkdir()
    fixture.mkdir()
    skill.mkdir()
    manifest = WorkflowManifest(
        id="missing-artifact",
        name="Missing Artifact",
        nodes=[
            WorkflowNodeSpec(
                id="agent_prepare",
                type="coding_agent",
                needs=[],
                timeout_seconds=30,
                on_failure="fail_workflow",
                prompt="Prepare without writing an artifact.",
            ),
            WorkflowNodeSpec(
                id="aggregate",
                type="aggregate",
                needs=["agent_prepare"],
                inputs=["agent_prepare"],
                timeout_seconds=5,
                on_failure="fail_workflow",
                outputs=["aggregate.md"],
            ),
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
    assert [node.node_id for node in result.nodes] == ["agent_prepare", "aggregate"]
    assert result.nodes[1].status == "failed"
    assert "Missing workflow artifact" in result.nodes[1].error
