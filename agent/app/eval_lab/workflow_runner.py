from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
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

            batch = ready[: manifest.max_parallel_nodes]
            for node in batch:
                remaining.remove(node)

            runnable_nodes: list[WorkflowNodeSpec] = []
            batch_results: dict[str, tuple[WorkflowNodeRecord, SandboxRunResult | None]] = {}
            for node in batch:
                if any(dependency in skipped for dependency in node.needs):
                    skipped.add(node.id)
                    batch_results[node.id] = (
                        WorkflowNodeRecord(
                            node_id=node.id,
                            node_type=node.type,
                            status="skipped",
                            duration_ms=0,
                            error="Upstream dependency was skipped.",
                        ),
                        None,
                    )
                else:
                    runnable_nodes.append(node)

            with ThreadPoolExecutor(max_workers=manifest.max_parallel_nodes) as executor:
                future_by_node = {
                    executor.submit(
                        self._run_node_with_duration,
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
                    ): node
                    for node in runnable_nodes
                }
                for future, node in future_by_node.items():
                    batch_results[node.id] = future.result()

            fail_workflow = False
            for node in batch:
                record, node_sandbox_result = batch_results[node.id]
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
                    fail_workflow = fail_workflow or node.on_failure == "fail_workflow"

            if fail_workflow:
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

    def _run_node_with_duration(
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
        started = time.monotonic()
        try:
            record, sandbox_result = self._run_node(
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
                timeout_seconds=timeout_seconds,
            )
        except ValueError as exc:
            record = WorkflowNodeRecord(
                node_id=node.id,
                node_type=node.type,
                status="failed",
                duration_ms=0,
                error=str(exc),
            )
            sandbox_result = None
        record.duration_ms = int((time.monotonic() - started) * 1000)
        return record, sandbox_result

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
                task_prompt=self._build_agent_prompt(node, node_by_id, task_prompt, artifacts_dir),
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
        try:
            artifact_path = self._write_text_artifact(artifacts_dir, node, output)
        except ValueError as exc:
            return WorkflowNodeRecord(
                node_id=node.id,
                node_type=node.type,
                status="failed",
                duration_ms=0,
                error=str(exc),
            )
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

    def _build_agent_prompt(
        self,
        node: WorkflowNodeSpec,
        node_by_id: dict[str, WorkflowNodeSpec],
        task_prompt: str,
        artifacts_dir: Path,
    ) -> str:
        prompt_parts = [task_prompt]
        if node.prompt:
            prompt_parts.append(node.prompt)
        for dependency in node.needs:
            upstream = node_by_id[dependency]
            artifact = artifacts_dir / _artifact_name(upstream)
            if artifact.exists():
                prompt_parts.append(f"Workflow artifact from {dependency}:\n{artifact.read_text(encoding='utf-8')}")
        return "\n\n".join(prompt_parts)

    def _write_text_artifact(self, artifacts_dir: Path, node: WorkflowNodeSpec, text: str) -> str:
        artifact_name = _artifact_name(node)
        path = artifacts_dir / artifact_name
        path.write_text(text, encoding="utf-8")
        return path.relative_to(artifacts_dir.parent.parent).as_posix()


def _artifact_name(node: WorkflowNodeSpec) -> str:
    if node.outputs:
        return _validate_artifact_name(node.outputs[0], node.id)
    suffix = "md" if node.type == "aggregate" else "txt"
    return _validate_artifact_name(f"{node.id}.{suffix}", node.id)


def _validate_artifact_name(artifact_name: str, node_id: str) -> str:
    artifact_path = Path(artifact_name)
    if (
        not artifact_name
        or artifact_path.is_absolute()
        or artifact_path.parts != (artifact_name,)
        or "/" in artifact_name
        or "\\" in artifact_name
        or artifact_name in {".", ".."}
    ):
        raise ValueError(f"Unsafe workflow artifact output name for node '{node_id}': {artifact_name}")
    return artifact_name


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
