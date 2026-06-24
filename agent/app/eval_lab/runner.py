from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.config import Settings

from .hashing import hash_directory
from .manifests import load_skill_manifest, load_task_pack_manifest
from .paths import ensure_child_path
from .repository import EvalRepository
from .sandbox import DockerSandbox, SandboxRunResult
from .scorer import run_scorer
from .workflow_runner import WorkflowRunner, WorkflowRunResult
from .workflows import load_workflow_manifest


class EvalRunner:
    def __init__(
        self,
        repo: EvalRepository | None = None,
        sandbox: DockerSandbox | None = None,
        workflow_runner: WorkflowRunner | None = None,
        runs_root: Path | None = None,
        host_runs_root: Path | None = None,
    ) -> None:
        self.repo = repo or EvalRepository()
        self.sandbox = sandbox or DockerSandbox()
        self.workflow_runner = workflow_runner or WorkflowRunner(sandbox=self.sandbox)
        if runs_root is None:
            self.runs_root = Path(Settings.eval_lab_container_runs_dir)
            self.host_runs_root = Path(host_runs_root or Settings.eval_lab_host_runs_dir)
        else:
            self.runs_root = Path(runs_root)
            self.host_runs_root = Path(host_runs_root or runs_root)

    def run(
        self,
        skill_dir: Path,
        task_pack_dir: Path,
        network_enabled: bool,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        skill_dir = Path(skill_dir)
        task_pack_dir = Path(task_pack_dir)
        skill_manifest = load_skill_manifest(skill_dir)
        task_pack_manifest = load_task_pack_manifest(task_pack_dir)
        skill_hash = hash_directory(skill_dir)
        task_pack_hash = hash_directory(task_pack_dir)

        self.repo.upsert_skill(
            skill_id=skill_manifest.id,
            name=skill_manifest.name,
            version_hash=skill_hash,
            source_type="local",
            source_path=str(skill_dir.resolve()),
            manifest=skill_manifest.model_dump(),
        )
        self.repo.upsert_task_pack(
            task_pack_id=task_pack_manifest.id,
            name=task_pack_manifest.name,
            domain=task_pack_manifest.domain,
            version_hash=task_pack_hash,
            source_path=str(task_pack_dir.resolve()),
            manifest=task_pack_manifest.model_dump(),
        )

        eval_run = self.repo.create_eval_run(skill_manifest.id, task_pack_manifest.id)
        run_id = eval_run["id"]
        run_dir = ensure_child_path(self.runs_root, self.runs_root / run_id)
        trace_ids: list[str] = []

        try:
            if run_dir.exists():
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True)
            self.repo.mark_run_running(run_id, str(run_dir))
            task_statuses = []

            for task in task_pack_manifest.tasks:
                workspace_dir = ensure_child_path(run_dir, run_dir / task.id)
                workspace_host_dir = self._host_path_for_run_workspace(workspace_dir)
                fixture_dir = task_pack_dir / task.fixture
                expected_dir = task_pack_dir / task.expected
                scorer_path = task_pack_dir / task.scorer
                shutil.copytree(fixture_dir, workspace_dir)

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
                        sandbox_workspace_host_dir=workspace_host_dir,
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
                        workspace_host_dir=workspace_host_dir,
                        network_enabled=network_enabled,
                        timeout_seconds=timeout_seconds,
                    )
                if not result.changed_files:
                    result.changed_files = self._list_workspace_files(workspace_dir)
                if workflow_result is not None:
                    trace_ids.extend(workflow_result.trace_ids)
                else:
                    trace_ids.extend(result.trace_ids)

                output_path = workspace_dir / "agent_output.json"
                output_path.write_text(
                    json.dumps(result.model_dump(), indent=2, sort_keys=True),
                    encoding="utf-8",
                )

                score = run_scorer(
                    scorer_path=scorer_path,
                    workspace_path=workspace_dir,
                    expected_path=expected_dir,
                    agent_output_path=output_path,
                    timeout_seconds=timeout_seconds,
                )
                normalized_score = round(score.score / score.max_score * task.max_score, 6)
                if workflow_result is not None:
                    workflow_nodes = [node.model_dump() for node in workflow_result.nodes]
                    execution_status = workflow_result.status
                else:
                    workflow_nodes = []
                    execution_status = result.status
                task_statuses.append(
                    self._task_status_from_score(
                        normalized_score=normalized_score,
                        max_score=task.max_score,
                        sandbox_status=execution_status,
                    )
                )
                score_details = {
                    **score.details,
                    "scorer_score": score.score,
                    "scorer_max_score": score.max_score,
                    "sandbox_status": result.status,
                    "sandbox_changed_files": result.changed_files,
                    "sandbox_error": result.agent_output if result.status != "passed" else None,
                    "workflow_nodes": workflow_nodes,
                }
                if workflow_result is not None:
                    score_details["workflow_status"] = workflow_result.status

                self.repo.add_score(
                    eval_run_id=run_id,
                    task_id=task.id,
                    score_type="auto",
                    score=normalized_score,
                    max_score=task.max_score,
                    details=score_details,
                )

            status = self._finish_status(task_statuses)
            self.repo.finish_run(run_id, status, trace_ids)
        except Exception as exc:
            self.repo.finish_run(run_id, "error", trace_ids, str(exc))

        return self.repo.get_eval_run(run_id)

    def _finish_status(self, task_statuses: list[str]) -> str:
        if not task_statuses:
            return "error"
        if all(status == "passed" for status in task_statuses):
            return "passed"
        return "failed"

    def _task_status_from_score(self, normalized_score: float, max_score: float, sandbox_status: str) -> str:
        if sandbox_status != "passed":
            return "failed"
        return "passed" if normalized_score / max_score >= 0.6 else "failed"

    def _host_path_for_run_workspace(self, workspace_dir: Path) -> Path:
        container_runs_root = self.runs_root.resolve()
        resolved_workspace = ensure_child_path(container_runs_root, workspace_dir)
        relative_workspace = resolved_workspace.relative_to(container_runs_root)
        return ensure_child_path(self.host_runs_root, self.host_runs_root / relative_workspace)

    def _list_workspace_files(self, workspace_dir: Path) -> list[str]:
        return sorted(
            path.relative_to(workspace_dir).as_posix()
            for path in workspace_dir.rglob("*")
            if path.is_file()
        )
