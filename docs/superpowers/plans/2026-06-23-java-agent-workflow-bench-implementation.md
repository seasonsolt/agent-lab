# Java Agent Workflow Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working slice of the Java agent workflow benchmark: workflow manifests, a small DAG runner, workflow-aware reports, and one executable Java case per benchmark track.

**Architecture:** Keep the current skill/task-pack/sandbox flow intact. Add workflow support as an optional task-pack feature: tasks without `workflow` keep using the existing linear sandbox path, while tasks with `workflow` run a DAG of tool, aggregate, and coding-agent nodes before the existing scorer calculates the auto score.

**Tech Stack:** FastAPI, Pydantic, Docker sandbox, pytest, PyYAML, Python subprocess, Java 17 `javac`/`java`, existing Agent Lab CLI/API.

---

## Scope

This plan implements the benchmark foundation and three Java golden cases:

- `static-quality/null-resource-exception`
- `architecture/ddia-idempotent-consumer`
- `security-appsec/sql-injection`

This plan does not add full SonarQube, RAG indexing, external PR review product ingestion, or the full six-case benchmark pack. Those need the workflow foundation from this plan.

## File Structure

Create:

- `agent/app/eval_lab/workflows.py`: workflow manifest models, path validation, DAG validation.
- `agent/app/eval_lab/workflow_runner.py`: internal DAG runner and node executors.
- `agent/tests/eval_lab/test_workflows.py`: workflow manifest and DAG validation tests.
- `agent/tests/eval_lab/test_workflow_runner.py`: scheduling, parallelism, artifact, and failure-policy tests.
- `task_packs/java-skills-bench/taskpack.yaml`: first Java benchmark pack.
- `task_packs/java-skills-bench/workflows/static-quality.yaml`: static-quality workflow.
- `task_packs/java-skills-bench/workflows/architecture-review.yaml`: architecture workflow.
- `task_packs/java-skills-bench/workflows/security-appsec.yaml`: security workflow.
- `task_packs/java-skills-bench/scorers/java_assertions.py`: shared Java scorer.
- `task_packs/java-skills-bench/tasks/static-quality/null-resource-exception/...`: static-quality fixture, expected tests, and docs.
- `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/...`: architecture fixture, expected tests, and docs.
- `task_packs/java-skills-bench/tasks/security-appsec/sql-injection/...`: security fixture, expected tests, and docs.

Modify:

- `agent/Dockerfile`: install Java 17 for scorers and workflow tool nodes.
- `agent/app/eval_lab/schemas.py`: add task metadata, workflow-node report schemas.
- `agent/app/eval_lab/manifests.py`: validate optional task workflow paths.
- `agent/app/eval_lab/runner.py`: dispatch workflow tasks to `WorkflowRunner`.
- `agent/app/eval_lab/report.py`: expose workflow node artifacts in eval reports.
- `agent/tests/eval_lab/test_manifests.py`: cover task metadata and workflow path validation.
- `agent/tests/eval_lab/test_runner.py`: cover workflow dispatch while preserving legacy path.
- `agent/tests/eval_lab/test_report.py`: cover workflow node aggregation.
- `agent/tests/eval_lab/test_sample_assets.py`: validate the Java sample pack.
- `README.md`: document the first Java workflow benchmark command.

---

### Task 1: Add Workflow Manifest Schema And Task Metadata

**Files:**
- Modify: `agent/app/eval_lab/schemas.py`
- Modify: `agent/app/eval_lab/manifests.py`
- Modify: `agent/tests/eval_lab/test_manifests.py`

- [ ] **Step 1: Add failing tests for task metadata and workflow path validation**

Append these tests to `agent/tests/eval_lab/test_manifests.py`:

```python
def test_load_task_pack_manifest_accepts_java_workflow_metadata(tmp_path):
    pack_dir = tmp_path / "pack"
    task_dir = pack_dir / "tasks" / "case-1"
    workflow_dir = pack_dir / "workflows"
    task_dir.mkdir(parents=True)
    workflow_dir.mkdir()
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
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
    (pack_dir / "taskpack.yaml").write_text(
        "id: java-skills-bench\n"
        "name: Java Skills Bench\n"
        "domain: java\n"
        "tasks:\n"
        "  - id: null-resource-exception\n"
        "    type: coding\n"
        "    track: static-quality\n"
        "    capability: resource-management\n"
        "    workflow: workflows/static-quality.yaml\n"
        "    knowledge_sources:\n"
        "      - Sonar-style static quality\n"
        "    prompt: Fix resource handling.\n"
        "    fixture: tasks/case-1/fixture\n"
        "    expected: tasks/case-1/expected\n"
        "    scorer: tasks/case-1/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    manifest = load_task_pack_manifest(pack_dir)

    task = manifest.tasks[0]
    assert task.track == "static-quality"
    assert task.capability == "resource-management"
    assert task.workflow == "workflows/static-quality.yaml"
    assert task.knowledge_sources == ["Sonar-style static quality"]


def test_load_task_pack_manifest_rejects_workflow_path_escape(tmp_path):
    pack_dir = tmp_path / "pack"
    outside = tmp_path / "outside"
    task_dir = pack_dir / "tasks" / "case-1"
    outside.mkdir()
    task_dir.mkdir(parents=True)
    (task_dir / "fixture").mkdir()
    (task_dir / "expected").mkdir()
    (task_dir / "scorer.py").write_text("print('{}')\n", encoding="utf-8")
    (outside / "workflow.yaml").write_text("id: outside\nname: Outside\nnodes: []\n", encoding="utf-8")
    (pack_dir / "taskpack.yaml").write_text(
        "id: java-skills-bench\n"
        "name: Java Skills Bench\n"
        "domain: java\n"
        "tasks:\n"
        "  - id: case-1\n"
        "    type: coding\n"
        "    workflow: ../outside/workflow.yaml\n"
        "    prompt: Fix it.\n"
        "    fixture: tasks/case-1/fixture\n"
        "    expected: tasks/case-1/expected\n"
        "    scorer: tasks/case-1/scorer.py\n"
        "    max_score: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="workflow path is outside task pack"):
        load_task_pack_manifest(pack_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_manifests.py -q
```

Expected: fail because `TaskSpec` does not expose `track`, `capability`, `workflow`, or `knowledge_sources`.

- [ ] **Step 3: Extend `TaskSpec`**

In `agent/app/eval_lab/schemas.py`, replace the `TaskSpec` class with:

```python
class TaskSpec(BaseModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    fixture: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    scorer: str = Field(min_length=1)
    max_score: float = Field(gt=0)
    track: str | None = None
    capability: str | None = None
    workflow: str | None = None
    knowledge_sources: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Validate optional workflow paths**

In `agent/app/eval_lab/manifests.py`, add this helper after `_resolve_task_path`:

```python
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
```

Then in `load_task_pack_manifest`, after scorer validation, add:

```python
        workflow = _resolve_optional_task_path(task_pack_dir, task, "workflow")
        if workflow is not None and not workflow.is_file():
            raise ValueError(f"Task '{task.id}' workflow path must be a file")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_manifests.py -q
```

Expected: all manifest tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/app/eval_lab/schemas.py agent/app/eval_lab/manifests.py agent/tests/eval_lab/test_manifests.py
git commit -m "feat: add workflow task metadata"
```

---

### Task 2: Add Workflow Manifest Loader And DAG Validation

**Files:**
- Create: `agent/app/eval_lab/workflows.py`
- Create: `agent/tests/eval_lab/test_workflows.py`
- Modify: `agent/app/eval_lab/schemas.py`

- [ ] **Step 1: Add failing workflow loader tests**

Create `agent/tests/eval_lab/test_workflows.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.eval_lab.workflows import load_workflow_manifest


def test_load_workflow_manifest_reads_valid_dag(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: java-static-quality\n"
        "name: Java Static Quality\n"
        "max_parallel_nodes: 2\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('scan')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: continue_with_artifact\n"
        "    outputs:\n"
        "      - scan.json\n"
        "  - id: agent_fix\n"
        "    type: coding_agent\n"
        "    needs: [scan]\n"
        "    timeout_seconds: 30\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    manifest = load_workflow_manifest(workflow_path)

    assert manifest.id == "java-static-quality"
    assert manifest.max_parallel_nodes == 2
    assert [node.id for node in manifest.nodes] == ["scan", "agent_fix"]
    assert manifest.nodes[0].outputs == ["scan.json"]


def test_load_workflow_manifest_rejects_duplicate_node_ids(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: duplicate\n"
        "name: Duplicate\n"
        "nodes:\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('a')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "  - id: scan\n"
        "    type: tool\n"
        "    command: python -c \"print('b')\"\n"
        "    needs: []\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate workflow node id"):
        load_workflow_manifest(workflow_path)


def test_load_workflow_manifest_rejects_missing_dependency(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: missing-dependency\n"
        "name: Missing Dependency\n"
        "nodes:\n"
        "  - id: agent_fix\n"
        "    type: coding_agent\n"
        "    needs: [scan]\n"
        "    timeout_seconds: 30\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown dependency"):
        load_workflow_manifest(workflow_path)


def test_load_workflow_manifest_rejects_cycles(tmp_path):
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        "id: cycle\n"
        "name: Cycle\n"
        "nodes:\n"
        "  - id: a\n"
        "    type: aggregate\n"
        "    needs: [b]\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n"
        "  - id: b\n"
        "    type: aggregate\n"
        "    needs: [a]\n"
        "    timeout_seconds: 5\n"
        "    on_failure: fail_workflow\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cycle"):
        load_workflow_manifest(workflow_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_workflows.py -q
```

Expected: fail because `app.eval_lab.workflows` does not exist.

- [ ] **Step 3: Add workflow schema models**

In `agent/app/eval_lab/schemas.py`, add these aliases after `Verdict`:

```python
WorkflowNodeType = Literal["tool", "expert_lens", "aggregate", "coding_agent", "scorer", "judge"]
WorkflowFailurePolicy = Literal["fail_workflow", "continue_with_artifact", "skip_dependents"]
WorkflowNodeStatus = Literal["queued", "running", "passed", "failed", "skipped"]
```

Then add these models after `TaskPackManifest`:

```python
class WorkflowNodeSpec(BaseModel):
    id: str = Field(min_length=1)
    type: WorkflowNodeType
    needs: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(gt=0)
    on_failure: WorkflowFailurePolicy = "fail_workflow"
    command: str | None = None
    prompt: str | None = None
    max_parallelism_key: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)


class WorkflowManifest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    max_parallel_nodes: int = Field(default=4, gt=0)
    nodes: list[WorkflowNodeSpec] = Field(min_length=1)


class WorkflowNodeRecord(BaseModel):
    node_id: str
    node_type: WorkflowNodeType
    status: WorkflowNodeStatus
    duration_ms: int = Field(ge=0)
    artifact_paths: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    error: str | None = None
```

- [ ] **Step 4: Implement workflow loading and validation**

Create `agent/app/eval_lab/workflows.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_workflows.py tests/eval_lab/test_manifests.py -q
```

Expected: all workflow and manifest tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/app/eval_lab/schemas.py agent/app/eval_lab/workflows.py agent/tests/eval_lab/test_workflows.py
git commit -m "feat: validate workflow manifests"
```

---

### Task 3: Implement DAG Runner For Tool, Aggregate, And Coding-Agent Nodes

**Files:**
- Create: `agent/app/eval_lab/workflow_runner.py`
- Create: `agent/tests/eval_lab/test_workflow_runner.py`

- [ ] **Step 1: Add failing workflow runner tests**

Create `agent/tests/eval_lab/test_workflow_runner.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_workflow_runner.py -q
```

Expected: fail because `workflow_runner.py` does not exist.

- [ ] **Step 3: Implement workflow runner**

Create `agent/app/eval_lab/workflow_runner.py`:

```python
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .sandbox import DockerSandbox, SandboxRunResult
from .schemas import WorkflowManifest, WorkflowNodeRecord, WorkflowNodeSpec


class WorkflowRunResult(BaseModel):
    status: str
    nodes: list[WorkflowNodeRecord] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    sandbox_result: SandboxRunResult | None = None


class WorkflowRunner:
    def __init__(self, sandbox: DockerSandbox | None = None) -> None:
        self.sandbox = sandbox or DockerSandbox()

    def run(
        self,
        manifest: WorkflowManifest,
        run_id: str,
        task_id: str,
        task_prompt: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
    ) -> WorkflowRunResult:
        artifacts_dir = workspace_host_dir / ".agent-lab" / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        completed: set[str] = set()
        skipped: set[str] = set()
        records: list[WorkflowNodeRecord] = []
        trace_ids: list[str] = []
        sandbox_result: SandboxRunResult | None = None
        failed = False

        node_by_id = {node.id: node for node in manifest.nodes}
        remaining = list(manifest.nodes)

        while remaining:
            ready = [
                node
                for node in remaining
                if all(dependency in completed or dependency in skipped for dependency in node.needs)
            ]
            if not ready:
                records.append(
                    WorkflowNodeRecord(
                        node_id="workflow",
                        node_type="aggregate",
                        status="failed",
                        duration_ms=0,
                        error="No ready workflow nodes remained; DAG validation should have rejected this workflow.",
                    )
                )
                return WorkflowRunResult(status="failed", nodes=records, trace_ids=trace_ids, sandbox_result=sandbox_result)

            for node in ready[: manifest.max_parallel_nodes]:
                remaining.remove(node)
                if any(dependency in skipped for dependency in node.needs):
                    skipped.add(node.id)
                    records.append(
                        WorkflowNodeRecord(
                            node_id=node.id,
                            node_type=node.type,
                            status="skipped",
                            duration_ms=0,
                            error="Upstream dependency was skipped.",
                        )
                    )
                    continue

                started = time.monotonic()
                record, node_sandbox_result = self._run_node(
                    node=node,
                    node_by_id=node_by_id,
                    task_prompt=task_prompt,
                    run_id=run_id,
                    task_id=task_id,
                    skill_host_dir=skill_host_dir,
                    fixture_host_dir=fixture_host_dir,
                    workspace_host_dir=workspace_host_dir,
                    artifacts_dir=artifacts_dir,
                    network_enabled=network_enabled,
                    timeout_seconds=min(timeout_seconds, node.timeout_seconds),
                )
                duration_ms = int((time.monotonic() - started) * 1000)
                record.duration_ms = duration_ms
                records.append(record)

                if node_sandbox_result is not None:
                    sandbox_result = node_sandbox_result
                    trace_ids.extend(node_sandbox_result.trace_ids)

                if record.status == "passed":
                    completed.add(node.id)
                elif node.on_failure == "skip_dependents":
                    skipped.add(node.id)
                else:
                    failed = True
                    completed.add(node.id)
                    if node.on_failure == "fail_workflow":
                        return WorkflowRunResult(
                            status="failed",
                            nodes=records,
                            trace_ids=_dedupe(trace_ids),
                            sandbox_result=sandbox_result,
                        )

        return WorkflowRunResult(
            status="failed" if failed else "passed",
            nodes=records,
            trace_ids=_dedupe(trace_ids),
            sandbox_result=sandbox_result,
        )

    def _run_node(
        self,
        node: WorkflowNodeSpec,
        node_by_id: dict[str, WorkflowNodeSpec],
        task_prompt: str,
        run_id: str,
        task_id: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        artifacts_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
    ) -> tuple[WorkflowNodeRecord, SandboxRunResult | None]:
        if node.type == "tool":
            return self._run_tool_node(node, workspace_host_dir, artifacts_dir, timeout_seconds), None
        if node.type == "aggregate":
            return self._run_aggregate_node(node, node_by_id, artifacts_dir), None
        if node.type == "coding_agent":
            sandbox_result = self.sandbox.run_task(
                run_id=run_id,
                task_id=f"{task_id}-{node.id}",
                task_prompt=self._build_agent_prompt(node, task_prompt, artifacts_dir),
                skill_host_dir=skill_host_dir,
                fixture_host_dir=fixture_host_dir,
                workspace_host_dir=workspace_host_dir,
                network_enabled=network_enabled,
                timeout_seconds=timeout_seconds,
            )
            return (
                WorkflowNodeRecord(
                    node_id=node.id,
                    node_type=node.type,
                    status="passed" if sandbox_result.status == "passed" else "failed",
                    duration_ms=0,
                    artifact_paths=[],
                    trace_ids=sandbox_result.trace_ids,
                    error=None if sandbox_result.status == "passed" else sandbox_result.agent_output,
                ),
                sandbox_result,
            )
        return (
            WorkflowNodeRecord(
                node_id=node.id,
                node_type=node.type,
                status="failed",
                duration_ms=0,
                error=f"Unsupported workflow node type for MVP runner: {node.type}",
            ),
            None,
        )

    def _run_tool_node(
        self,
        node: WorkflowNodeSpec,
        workspace_host_dir: Path,
        artifacts_dir: Path,
        timeout_seconds: int,
    ) -> WorkflowNodeRecord:
        if not node.command:
            return WorkflowNodeRecord(
                node_id=node.id,
                node_type=node.type,
                status="failed",
                duration_ms=0,
                error="Tool node requires command.",
            )
        try:
            completed = subprocess.run(
                node.command,
                cwd=workspace_host_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            artifact_path = self._write_text_artifact(
                artifacts_dir,
                node,
                f"Command timed out after {timeout_seconds} seconds.\nSTDOUT:\n{exc.stdout or ''}\nSTDERR:\n{exc.stderr or ''}\n",
            )
            return WorkflowNodeRecord(
                node_id=node.id,
                node_type=node.type,
                status="failed",
                duration_ms=0,
                artifact_paths=[artifact_path],
                error=f"Tool node timed out after {timeout_seconds} seconds.",
            )

        output = f"RETURN_CODE={completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}\n"
        artifact_path = self._write_text_artifact(artifacts_dir, node, output)
        status = "passed" if completed.returncode == 0 or node.on_failure == "continue_with_artifact" else "failed"
        return WorkflowNodeRecord(
            node_id=node.id,
            node_type=node.type,
            status=status,
            duration_ms=0,
            artifact_paths=[artifact_path],
            error=None if completed.returncode == 0 else output.strip(),
        )

    def _run_aggregate_node(
        self,
        node: WorkflowNodeSpec,
        node_by_id: dict[str, WorkflowNodeSpec],
        artifacts_dir: Path,
    ) -> WorkflowNodeRecord:
        sections = []
        for dependency in node.needs:
            upstream = node_by_id[dependency]
            artifact = artifacts_dir / _artifact_name(upstream)
            if artifact.exists():
                sections.append(f"## {dependency}\n\n{artifact.read_text(encoding='utf-8')}")
        artifact_path = self._write_text_artifact(artifacts_dir, node, "\n\n".join(sections))
        return WorkflowNodeRecord(
            node_id=node.id,
            node_type=node.type,
            status="passed",
            duration_ms=0,
            artifact_paths=[artifact_path],
        )

    def _build_agent_prompt(self, node: WorkflowNodeSpec, task_prompt: str, artifacts_dir: Path) -> str:
        prompt_parts = [task_prompt]
        if node.prompt:
            prompt_parts.append(node.prompt)
        for dependency in node.needs:
            artifact = artifacts_dir / f"{dependency}.md"
            if artifact.exists():
                prompt_parts.append(f"Workflow artifact from {dependency}:\n{artifact.read_text(encoding='utf-8')}")
            txt_artifact = artifacts_dir / f"{dependency}.txt"
            if txt_artifact.exists():
                prompt_parts.append(f"Workflow artifact from {dependency}:\n{txt_artifact.read_text(encoding='utf-8')}")
        return "\n\n".join(prompt_parts)

    def _write_text_artifact(self, artifacts_dir: Path, node: WorkflowNodeSpec, text: str) -> str:
        artifact_name = _artifact_name(node)
        path = artifacts_dir / artifact_name
        path.write_text(text, encoding="utf-8")
        return path.relative_to(artifacts_dir.parent.parent).as_posix()


def _artifact_name(node: WorkflowNodeSpec) -> str:
    if node.outputs:
        return node.outputs[0]
    suffix = "md" if node.type == "aggregate" else "txt"
    return f"{node.id}.{suffix}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_workflow_runner.py -q
```

Expected: all workflow runner tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/app/eval_lab/workflow_runner.py agent/tests/eval_lab/test_workflow_runner.py
git commit -m "feat: run evaluation workflows"
```

---

### Task 4: Integrate Workflows Into EvalRunner And Reports

**Files:**
- Modify: `agent/app/eval_lab/runner.py`
- Modify: `agent/app/eval_lab/report.py`
- Modify: `agent/app/eval_lab/schemas.py`
- Modify: `agent/tests/eval_lab/test_runner.py`
- Modify: `agent/tests/eval_lab/test_report.py`

- [ ] **Step 1: Add failing report test for workflow nodes**

Append this test to `agent/tests/eval_lab/test_report.py`:

```python
def test_build_report_includes_workflow_nodes_from_score_details():
    report = build_report_from_records(
        eval_run={
            "id": "run-1",
            "status": "passed",
            "skill_id": "skill-1",
            "task_pack_id": "pack-1",
            "langfuse_trace_ids": ["trace-1"],
            "error": None,
        },
        skill={"id": "skill-1", "name": "Skill", "version_hash": "skill-hash", "manifest": {}},
        task_pack={"id": "pack-1", "name": "Pack", "domain": "java", "version_hash": "pack-hash"},
        scores=[
            {
                "task_id": "task-1",
                "score_type": "auto",
                "score": 100,
                "max_score": 100,
                "details": {
                    "workflow_nodes": [
                        {
                            "node_id": "scan",
                            "node_type": "tool",
                            "status": "passed",
                            "duration_ms": 12,
                            "artifact_paths": [".agent-lab/artifacts/scan.txt"],
                            "trace_ids": [],
                            "error": None,
                        }
                    ]
                },
            }
        ],
    )

    assert len(report.workflow_nodes) == 1
    assert report.workflow_nodes[0].node_id == "scan"
    assert report.workflow_nodes[0].artifact_paths == [".agent-lab/artifacts/scan.txt"]
```

- [ ] **Step 2: Add failing runner test for workflow dispatch**

Append this helper and test to `agent/tests/eval_lab/test_runner.py`:

```python
class FakeWorkflowRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

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
                "network_enabled": network_enabled,
                "timeout_seconds": timeout_seconds,
            }
        )

        from app.eval_lab.schemas import WorkflowNodeRecord
        from app.eval_lab.workflow_runner import WorkflowRunResult

        return WorkflowRunResult(
            status="passed",
            nodes=[
                WorkflowNodeRecord(
                    node_id="scan",
                    node_type="tool",
                    status="passed",
                    duration_ms=1,
                    artifact_paths=[".agent-lab/artifacts/scan.txt"],
                )
            ],
            trace_ids=["trace-workflow"],
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


def test_eval_runner_uses_workflow_runner_when_task_has_workflow(tmp_path):
    skill_dir = tmp_path / "skill"
    task_pack_dir = tmp_path / "pack"
    runs_root = tmp_path / "runs"
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
    ).run(
        skill_dir=skill_dir,
        task_pack_dir=task_pack_dir,
        network_enabled=False,
        timeout_seconds=8,
    )

    assert run["status"] == "passed"
    assert sandbox.calls == []
    assert workflow_runner.calls[0]["manifest_id"] == "static-quality"
    assert repo.finished == [{"run_id": "eval-1", "status": "passed", "trace_ids": ["trace-workflow"], "error": None}]
    assert repo.scores[0]["details"]["workflow_nodes"][0]["node_id"] == "scan"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_report.py::test_build_report_includes_workflow_nodes_from_score_details tests/eval_lab/test_runner.py::test_eval_runner_uses_workflow_runner_when_task_has_workflow -q
```

Expected: fail because reports do not include `workflow_nodes`, and `EvalRunner` does not accept `workflow_runner`.

- [ ] **Step 4: Add workflow nodes to report schema**

In `agent/app/eval_lab/schemas.py`, update `EvalReport` by adding this field:

```python
    workflow_nodes: list[WorkflowNodeRecord] = Field(default_factory=list)
```

- [ ] **Step 5: Aggregate workflow nodes in reports**

In `agent/app/eval_lab/report.py`, import `WorkflowNodeRecord`:

```python
from .schemas import EvalReport, ScoreRecord, Verdict, WorkflowNodeRecord
```

In `build_report_from_records`, after `score_records = ...`, add:

```python
    workflow_nodes = [
        WorkflowNodeRecord.model_validate(node)
        for score in scores
        for node in score.get("details", {}).get("workflow_nodes", [])
    ]
```

Then pass `workflow_nodes=workflow_nodes` into the `EvalReport(...)` constructor.

- [ ] **Step 6: Wire `WorkflowRunner` into `EvalRunner`**

In `agent/app/eval_lab/runner.py`, add imports:

```python
from .workflow_runner import WorkflowRunner, WorkflowRunResult
from .workflows import load_workflow_manifest
```

Update `EvalRunner.__init__` to accept `workflow_runner`:

```python
    def __init__(
        self,
        repo: EvalRepository | None = None,
        sandbox: DockerSandbox | None = None,
        workflow_runner: WorkflowRunner | None = None,
        runs_root: Path | None = None,
    ) -> None:
        self.repo = repo or EvalRepository()
        self.sandbox = sandbox or DockerSandbox()
        self.workflow_runner = workflow_runner or WorkflowRunner(sandbox=self.sandbox)
        self.runs_root = Path(runs_root or Settings.eval_lab_host_runs_dir)
```

Inside the task loop, replace the direct `result = self.sandbox.run_task(...)` block with:

```python
                workflow_result: WorkflowRunResult | None = None
                if task.workflow:
                    workflow_manifest = load_workflow_manifest(task_pack_dir / task.workflow)
                    workflow_result = self.workflow_runner.run(
                        manifest=workflow_manifest,
                        run_id=run_id,
                        task_id=task.id,
                        task_prompt=task.prompt,
                        skill_host_dir=skill_dir,
                        fixture_host_dir=fixture_dir,
                        workspace_host_dir=workspace_dir,
                        network_enabled=network_enabled,
                        timeout_seconds=timeout_seconds,
                    )
                    result = workflow_result.sandbox_result or SandboxRunResult(
                        task_id=task.id,
                        status=workflow_result.status,
                        agent_output="Workflow completed without a coding-agent node.",
                        changed_files=sorted(
                            path.relative_to(workspace_dir).as_posix()
                            for path in workspace_dir.rglob("*")
                            if path.is_file()
                        ),
                        trace_ids=[],
                    )
                else:
                    result = self.sandbox.run_task(
                        run_id=run_id,
                        task_id=task.id,
                        task_prompt=task.prompt,
                        skill_host_dir=skill_dir,
                        fixture_host_dir=fixture_dir,
                        workspace_host_dir=workspace_dir,
                        network_enabled=network_enabled,
                        timeout_seconds=timeout_seconds,
                    )
                if workflow_result is not None:
                    trace_ids.extend(workflow_result.trace_ids)
                else:
                    trace_ids.extend(result.trace_ids)
```

Update the score details dictionary by adding:

```python
                        "workflow_nodes": [
                            node.model_dump()
                            for node in workflow_result.nodes
                        ] if workflow_result is not None else [],
```

If `SandboxRunResult` is not imported in `runner.py`, add:

```python
from .sandbox import DockerSandbox, SandboxRunResult
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_report.py tests/eval_lab/test_runner.py -q
```

Expected: all report and runner tests pass.

- [ ] **Step 8: Commit**

```bash
git add agent/app/eval_lab/schemas.py agent/app/eval_lab/report.py agent/app/eval_lab/runner.py agent/tests/eval_lab/test_report.py agent/tests/eval_lab/test_runner.py
git commit -m "feat: include workflow nodes in eval runs"
```

---

### Task 5: Add Java Runtime To The Coding-Agent Image

**Files:**
- Modify: `agent/Dockerfile`

- [ ] **Step 1: Update Dockerfile with Java 17**

Replace the top of `agent/Dockerfile` with:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Verify Java is available in the rebuilt container**

Run:

```bash
docker compose run --build --rm coding-agent sh -lc 'java -version && javac -version'
```

Expected: command exits 0 and prints OpenJDK 17 version lines for `java` and `javac`.

- [ ] **Step 3: Commit**

```bash
git add agent/Dockerfile
git commit -m "chore: add Java runtime to agent image"
```

---

### Task 6: Add Shared Java Scorer And First Java Benchmark Pack

**Files:**
- Create: `task_packs/java-skills-bench/taskpack.yaml`
- Create: `task_packs/java-skills-bench/scorers/java_assertions.py`
- Create: `task_packs/java-skills-bench/workflows/static-quality.yaml`
- Create: `task_packs/java-skills-bench/workflows/architecture-review.yaml`
- Create: `task_packs/java-skills-bench/workflows/security-appsec.yaml`
- Create Java task fixture and expected files listed in this task.
- Modify: `agent/tests/eval_lab/test_sample_assets.py`

- [ ] **Step 1: Add failing sample asset test**

Append this test to `agent/tests/eval_lab/test_sample_assets.py`:

```python
def test_java_skills_bench_task_pack_is_valid():
    root = Path("/lab")
    task_pack = load_task_pack_manifest(root / "task_packs" / "java-skills-bench")

    assert task_pack.id == "java-skills-bench"
    assert [task.track for task in task_pack.tasks] == [
        "static-quality",
        "architecture",
        "security-appsec",
    ]
    assert [task.capability for task in task_pack.tasks] == [
        "resource-management",
        "messaging-streaming",
        "injection",
    ]
    assert all(task.workflow for task in task_pack.tasks)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sample_assets.py::test_java_skills_bench_task_pack_is_valid -q
```

Expected: fail because `task_packs/java-skills-bench` does not exist.

- [ ] **Step 3: Create workflow manifests**

Create `task_packs/java-skills-bench/workflows/static-quality.yaml`:

```yaml
id: static-quality
name: Static Quality Workflow
max_parallel_nodes: 2
nodes:
  - id: static_scan
    type: tool
    command: "python -c \"print('Check null handling, resource closing, broad suppressions, and test deletion.')\""
    needs: []
    timeout_seconds: 10
    on_failure: continue_with_artifact
    outputs:
      - static_scan.txt
  - id: aggregate_findings
    type: aggregate
    needs:
      - static_scan
    timeout_seconds: 10
    on_failure: fail_workflow
    outputs:
      - aggregate_findings.md
  - id: agent_fix
    type: coding_agent
    needs:
      - aggregate_findings
    timeout_seconds: 300
    on_failure: fail_workflow
    prompt: "Use the static-quality findings as evidence. Fix the Java implementation without deleting tests or hiding failures."
```

Create `task_packs/java-skills-bench/workflows/architecture-review.yaml`:

```yaml
id: architecture-review
name: Architecture Review Workflow
max_parallel_nodes: 3
nodes:
  - id: ddia_lens
    type: tool
    command: "python -c \"print('DDIA lens: preserve idempotency, ordering evidence, source-of-truth boundaries, and replay safety.')\""
    needs: []
    timeout_seconds: 10
    on_failure: continue_with_artifact
    outputs:
      - ddia_lens.txt
  - id: concurrency_lens
    type: tool
    command: "python -c \"print('Concurrency lens: duplicate delivery and retry races must not corrupt durable state.')\""
    needs: []
    timeout_seconds: 10
    on_failure: continue_with_artifact
    outputs:
      - concurrency_lens.txt
  - id: aggregate_findings
    type: aggregate
    needs:
      - ddia_lens
      - concurrency_lens
    timeout_seconds: 10
    on_failure: fail_workflow
    outputs:
      - aggregate_findings.md
  - id: agent_fix
    type: coding_agent
    needs:
      - aggregate_findings
    timeout_seconds: 300
    on_failure: fail_workflow
    prompt: "Use the architecture findings as evidence. Implement the smallest correct Java change."
```

Create `task_packs/java-skills-bench/workflows/security-appsec.yaml`:

```yaml
id: security-appsec
name: Security AppSec Workflow
max_parallel_nodes: 2
nodes:
  - id: sast_scan
    type: tool
    command: "python -c \"print('SAST evidence: user-controlled data must not be concatenated into SQL strings.')\""
    needs: []
    timeout_seconds: 10
    on_failure: continue_with_artifact
    outputs:
      - sast_scan.txt
  - id: aggregate_findings
    type: aggregate
    needs:
      - sast_scan
    timeout_seconds: 10
    on_failure: fail_workflow
    outputs:
      - aggregate_findings.md
  - id: agent_fix
    type: coding_agent
    needs:
      - aggregate_findings
    timeout_seconds: 300
    on_failure: fail_workflow
    prompt: "Use the security finding as evidence. Preserve behavior while removing injection risk."
```

- [ ] **Step 4: Create shared Java scorer**

Create `task_packs/java-skills-bench/scorers/java_assertions.py`:

```python
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import traceback
from pathlib import Path


def java_files(root: Path) -> list[str]:
    return sorted(str(path) for path in root.rglob("*.java"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--agent-output", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace)
    expected = Path(args.expected)
    build_dir = workspace / ".agent-lab-java-build"

    try:
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)
        sources = java_files(workspace / "src" / "main" / "java") + java_files(expected)
        if not sources:
            raise RuntimeError("No Java sources found for scoring")
        compile_cmd = ["javac", "-encoding", "UTF-8", "-d", str(build_dir), *sources]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True, check=False, timeout=30)
        if compile_result.returncode != 0:
            print(
                json.dumps(
                    {
                        "score": 0,
                        "max_score": 100,
                        "details": {
                            "compiled": False,
                            "compile_stdout": compile_result.stdout,
                            "compile_stderr": compile_result.stderr,
                        },
                    }
                )
            )
            return 0

        run_result = subprocess.run(
            ["java", "-cp", str(build_dir), "TestRunner"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        passed = run_result.returncode == 0
        print(
            json.dumps(
                {
                    "score": 100 if passed else 0,
                    "max_score": 100,
                    "details": {
                        "compiled": True,
                        "tests_passed": passed,
                        "stdout": run_result.stdout,
                        "stderr": run_result.stderr,
                    },
                }
            )
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "score": 0,
                    "max_score": 100,
                    "details": {
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                }
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create task pack manifest**

Create `task_packs/java-skills-bench/taskpack.yaml`:

```yaml
id: java-skills-bench
name: Java Skills Bench
domain: java
tasks:
  - id: null-resource-exception
    type: coding
    track: static-quality
    capability: resource-management
    workflow: workflows/static-quality.yaml
    knowledge_sources:
      - Sonar-style static quality
      - Java resource management
    prompt: >-
      Fix ResourceLoader.loadFirstLine(Path) so it handles missing files,
      closes resources, and returns Optional.empty() instead of throwing for
      absent input. Keep the public method signature unchanged. Do not delete
      tests or add dependencies.
    fixture: tasks/static-quality/null-resource-exception/fixture
    expected: tasks/static-quality/null-resource-exception/expected
    scorer: scorers/java_assertions.py
    max_score: 100
  - id: ddia-idempotent-consumer
    type: coding
    track: architecture
    capability: messaging-streaming
    workflow: workflows/architecture-review.yaml
    knowledge_sources:
      - DDIA
      - idempotent consumer pattern
      - replay-safe event processing
    prompt: >-
      Fix OrderEventConsumer.apply(OrderEvent) for an at-least-once event
      stream. Duplicate event IDs must be ignored, stale lower versions must not
      overwrite newer state, payment before creation must not create an order,
      and cancellation must remain terminal. Keep the implementation in memory
      and do not add dependencies.
    fixture: tasks/architecture/ddia-idempotent-consumer/fixture
    expected: tasks/architecture/ddia-idempotent-consumer/expected
    scorer: scorers/java_assertions.py
    max_score: 100
  - id: sql-injection
    type: coding
    track: security-appsec
    capability: injection
    workflow: workflows/security-appsec.yaml
    knowledge_sources:
      - AppSec
      - SQL injection prevention
    prompt: >-
      Fix UserSearch.buildFindByEmail(String) so user input is represented as a
      bound parameter instead of concatenated into SQL. Preserve the Query API,
      keep behavior deterministic, and do not add dependencies.
    fixture: tasks/security-appsec/sql-injection/fixture
    expected: tasks/security-appsec/sql-injection/expected
    scorer: scorers/java_assertions.py
    max_score: 100
```

- [ ] **Step 6: Create static-quality Java fixture and hidden test**

Create `task_packs/java-skills-bench/tasks/static-quality/null-resource-exception/fixture/src/main/java/com/agentlab/staticquality/ResourceLoader.java`:

```java
package com.agentlab.staticquality;

import java.io.BufferedReader;
import java.io.FileReader;
import java.nio.file.Path;
import java.util.Optional;

public class ResourceLoader {
    public Optional<String> loadFirstLine(Path path) throws Exception {
        BufferedReader reader = new BufferedReader(new FileReader(path.toFile()));
        String line = reader.readLine();
        return Optional.of(line.trim());
    }
}
```

Create `task_packs/java-skills-bench/tasks/static-quality/null-resource-exception/fixture/README.md`:

```markdown
# Null Resource Exception

Fix `ResourceLoader.loadFirstLine(Path)`.

Requirements:

- Return `Optional.empty()` for missing files.
- Return `Optional.empty()` for empty files.
- Trim non-empty first lines.
- Close file resources.
- Keep the method signature unchanged.
```

Create `task_packs/java-skills-bench/tasks/static-quality/null-resource-exception/expected/TestRunner.java`:

```java
import com.agentlab.staticquality.ResourceLoader;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

public class TestRunner {
    public static void main(String[] args) throws Exception {
        ResourceLoader loader = new ResourceLoader();
        Path dir = Files.createTempDirectory("agent-lab-static");
        Path present = dir.resolve("present.txt");
        Path empty = dir.resolve("empty.txt");
        Files.writeString(present, "  value  \nsecond\n");
        Files.writeString(empty, "");

        assertEquals(Optional.of("value"), loader.loadFirstLine(present), "trims first line");
        assertEquals(Optional.empty(), loader.loadFirstLine(empty), "empty file");
        assertEquals(Optional.empty(), loader.loadFirstLine(dir.resolve("missing.txt")), "missing file");
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
```

- [ ] **Step 7: Create architecture Java fixture and hidden test**

Create `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/fixture/src/main/java/com/agentlab/architecture/OrderEvent.java`:

```java
package com.agentlab.architecture;

public record OrderEvent(String eventId, String orderId, int version, String type, int amount) {
}
```

Create `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/fixture/src/main/java/com/agentlab/architecture/OrderView.java`:

```java
package com.agentlab.architecture;

public record OrderView(String status, int amount, int version) {
}
```

Create `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/fixture/src/main/java/com/agentlab/architecture/OrderEventConsumer.java`:

```java
package com.agentlab.architecture;

import java.util.HashMap;
import java.util.Map;

public class OrderEventConsumer {
    private final Map<String, OrderView> orders = new HashMap<>();

    public void apply(OrderEvent event) {
        if ("order_created".equals(event.type())) {
            orders.put(event.orderId(), new OrderView("created", event.amount(), event.version()));
        } else if ("payment_authorized".equals(event.type())) {
            OrderView current = orders.get(event.orderId());
            orders.put(event.orderId(), new OrderView("paid", current.amount(), event.version()));
        } else if ("order_cancelled".equals(event.type())) {
            OrderView current = orders.get(event.orderId());
            orders.put(event.orderId(), new OrderView("cancelled", current.amount(), event.version()));
        }
    }

    public Map<String, OrderView> orders() {
        return orders;
    }
}
```

Create `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/fixture/README.md`:

```markdown
# DDIA Idempotent Consumer

Fix `OrderEventConsumer.apply(OrderEvent)` for at-least-once event delivery.

Requirements:

- Ignore duplicate `eventId` values.
- Ignore stale lower-version events.
- Do not create an order from payment before creation.
- Preserve terminal cancellation.
- Keep the implementation in memory.
```

Create `task_packs/java-skills-bench/tasks/architecture/ddia-idempotent-consumer/expected/TestRunner.java`:

```java
import com.agentlab.architecture.OrderEvent;
import com.agentlab.architecture.OrderEventConsumer;
import com.agentlab.architecture.OrderView;

public class TestRunner {
    public static void main(String[] args) {
        OrderEventConsumer consumer = new OrderEventConsumer();

        consumer.apply(new OrderEvent("late-pay", "o2", 2, "payment_authorized", 0));
        assertTrue(!consumer.orders().containsKey("o2"), "late payment must not create order");

        consumer.apply(new OrderEvent("e1", "o1", 1, "order_created", 42));
        consumer.apply(new OrderEvent("e2", "o1", 2, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e2", "o1", 2, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e4", "o1", 4, "order_cancelled", 0));
        consumer.apply(new OrderEvent("e3", "o1", 3, "payment_authorized", 0));
        consumer.apply(new OrderEvent("e5", "o1", 5, "payment_authorized", 0));

        OrderView order = consumer.orders().get("o1");
        assertEquals("cancelled", order.status(), "cancellation remains terminal");
        assertEquals(42, order.amount(), "amount preserved");
        assertEquals(5, order.version(), "version evidence advances for invalid newer event");

        OrderEventConsumer replay = new OrderEventConsumer();
        OrderEvent[] stream = new OrderEvent[] {
            new OrderEvent("e1", "o1", 1, "order_created", 42),
            new OrderEvent("e2", "o1", 2, "payment_authorized", 0),
            new OrderEvent("e2", "o1", 2, "payment_authorized", 0),
            new OrderEvent("e4", "o1", 4, "order_cancelled", 0),
            new OrderEvent("e3", "o1", 3, "payment_authorized", 0),
            new OrderEvent("e5", "o1", 5, "payment_authorized", 0)
        };
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        for (OrderEvent event : stream) {
            replay.apply(event);
        }
        assertEquals(order, replay.orders().get("o1"), "replay is idempotent");
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
```

- [ ] **Step 8: Create security Java fixture and hidden test**

Create `task_packs/java-skills-bench/tasks/security-appsec/sql-injection/fixture/src/main/java/com/agentlab/security/Query.java`:

```java
package com.agentlab.security;

import java.util.List;

public record Query(String sql, List<String> parameters) {
}
```

Create `task_packs/java-skills-bench/tasks/security-appsec/sql-injection/fixture/src/main/java/com/agentlab/security/UserSearch.java`:

```java
package com.agentlab.security;

import java.util.List;

public class UserSearch {
    public Query buildFindByEmail(String email) {
        return new Query("select id, email from users where email = '" + email + "'", List.of());
    }
}
```

Create `task_packs/java-skills-bench/tasks/security-appsec/sql-injection/fixture/README.md`:

```markdown
# SQL Injection

Fix `UserSearch.buildFindByEmail(String)`.

Requirements:

- Keep returning a `Query`.
- Put user-controlled email in `Query.parameters`.
- Keep SQL stable when email contains quotes or SQL syntax.
- Do not add dependencies.
```

Create `task_packs/java-skills-bench/tasks/security-appsec/sql-injection/expected/TestRunner.java`:

```java
import com.agentlab.security.Query;
import com.agentlab.security.UserSearch;

import java.util.List;

public class TestRunner {
    public static void main(String[] args) {
        UserSearch search = new UserSearch();
        String attack = "a@example.com' OR '1'='1";
        Query query = search.buildFindByEmail(attack);

        assertEquals("select id, email from users where email = ?", query.sql(), "parameterized sql");
        assertEquals(List.of(attack), query.parameters(), "bound email parameter");
        assertTrue(!query.sql().contains(attack), "raw input must not appear in SQL");
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
```

- [ ] **Step 9: Run sample asset and scorer checks**

Run:

```bash
docker compose run --build --rm coding-agent pytest tests/eval_lab/test_sample_assets.py::test_java_skills_bench_task_pack_is_valid -q
```

Expected: sample asset validation passes.

Then run one scorer directly to confirm Java compile/test plumbing works:

```bash
docker compose run --rm coding-agent python /lab/task_packs/java-skills-bench/scorers/java_assertions.py \
  --workspace /lab/task_packs/java-skills-bench/tasks/security-appsec/sql-injection/fixture \
  --expected /lab/task_packs/java-skills-bench/tasks/security-appsec/sql-injection/expected \
  --agent-output /tmp/nonexistent-agent-output.json
```

Expected: JSON output with `"score": 0` because the fixture is intentionally vulnerable.

- [ ] **Step 10: Commit**

```bash
git add agent/tests/eval_lab/test_sample_assets.py task_packs/java-skills-bench
git commit -m "feat: add Java workflow benchmark pack"
```

---

### Task 7: Document The Java Workflow Benchmark Command

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section**

Append this section to `README.md`:

```markdown
## Java Agent Workflow Bench

Agent Lab can evaluate Java coding-agent workflows, not only direct skill
prompts. The first Java benchmark pack covers one case per track:

- `static-quality`: resource handling and null-safe behavior
- `architecture`: DDIA-style idempotent event processing
- `security-appsec`: SQL injection prevention

Run a local comparison:

```bash
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment ./skills/ddia-system-design \
  --task-pack ./task_packs/java-skills-bench \
  --api-url http://localhost:8000 \
  --runs 1 \
  --network \
  --timeout-seconds 300
```

Each workflow task records node artifacts under the run workspace and includes
workflow node status in the eval report.
```
```

- [ ] **Step 2: Verify README renders as valid Markdown fences**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text(encoding="utf-8")
assert text.count("```") % 2 == 0
print("markdown fences balanced")
PY
```

Expected: prints `markdown fences balanced`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: explain Java workflow benchmark"
```

---

### Task 8: Final Verification

**Files:**
- No edits.

- [ ] **Step 1: Run focused workflow tests**

Run:

```bash
docker compose run --build --rm coding-agent pytest \
  tests/eval_lab/test_workflows.py \
  tests/eval_lab/test_workflow_runner.py \
  tests/eval_lab/test_manifests.py \
  tests/eval_lab/test_runner.py \
  tests/eval_lab/test_report.py \
  tests/eval_lab/test_sample_assets.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
docker compose run --build --rm coding-agent pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Validate Docker Compose config**

Run:

```bash
docker compose config >/tmp/agent-lab-compose-java-workflow.yaml
```

Expected: command exits 0.

- [ ] **Step 4: Run one live Java workflow smoke comparison**

Start services:

```bash
docker compose up -d --build
```

Run:

```bash
rm -rf /tmp/agent-lab-java-workflow-smoke
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment ./skills/ddia-system-design \
  --task-pack ./task_packs/java-skills-bench \
  --api-url http://localhost:8000 \
  --runs 1 \
  --network \
  --timeout-seconds 300 \
  --output-dir /tmp/agent-lab-java-workflow-smoke
```

Expected:

- command exits 0
- `/tmp/agent-lab-java-workflow-smoke/comparison.json` exists
- `/tmp/agent-lab-java-workflow-smoke/comparison.md` exists
- at least one report score contains `details.workflow_nodes`

Check workflow-node evidence:

```bash
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/agent-lab-java-workflow-smoke/comparison.json").read_text(encoding="utf-8"))
reports = payload["baseline"]["run_ids"] + payload["treatment"]["run_ids"]
print("run_ids", reports)
assert reports
PY
```

Then fetch one report from the API and inspect `workflow_nodes`:

```bash
python3 - <<'PY'
import json
import urllib.request
from pathlib import Path

payload = json.loads(Path("/tmp/agent-lab-java-workflow-smoke/comparison.json").read_text(encoding="utf-8"))
run_id = payload["baseline"]["run_ids"][0]
with urllib.request.urlopen(f"http://localhost:8000/eval-runs/{run_id}/report", timeout=30) as response:
    report = json.loads(response.read().decode("utf-8"))
nodes = report.get("workflow_nodes", [])
print(json.dumps(nodes, indent=2))
assert nodes
assert any(node["node_id"] == "agent_fix" for node in nodes)
PY
```

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected: clean working tree after all commits.
