from __future__ import annotations

import os
import re
import uuid
import time
from pathlib import Path
from typing import Any

import docker
import httpx
from pydantic import BaseModel, Field

from app.config import Settings


_CONTAINER_NAME_MAX_LENGTH = 63
_TRACE_ID_PATTERN = re.compile(r'"trace_id"\s*:\s*"([0-9a-f]{32})"')


class SandboxRunResult(BaseModel):
    task_id: str
    status: str
    agent_output: str
    changed_files: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)


def build_task_prompt(skill_container_path: Path, task_prompt: str) -> str:
    return "\n".join(
        [
            f"Use the skill instructions at {skill_container_path.as_posix()}.",
            "Work inside /workspace.",
            "This is a bounded evaluation task.",
            "Edit only files needed to satisfy the task.",
            "Do not add dependencies.",
            "Do not spend time on documentation unless the task asks for it.",
            "Prefer a small correct implementation over exploration.",
            "When the implementation is complete, stop and return a concise summary.",
            f"Task: {task_prompt}",
        ]
    )


def build_container_name(run_id: str, task_id: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9.-]+", "-", f"agent-lab-{run_id}-{task_id}").strip("-.")
    suffix = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}:{task_id}").hex[:8]
    prefix_length = _CONTAINER_NAME_MAX_LENGTH - len(suffix) - 1
    prefix = base[:prefix_length].rstrip("-.") or "agent-lab"
    return f"{prefix}-{suffix}"


class DockerSandbox:
    def __init__(self) -> None:
        self.client = docker.from_env()

    def start_container(
        self,
        run_id: str,
        task_id: str,
        skill_host_dir: Path,
        fixture_host_dir: Path,
        workspace_host_dir: Path,
        network_enabled: bool,
    ) -> Any:
        container_name = build_container_name(run_id, task_id)
        volumes = {
            str(workspace_host_dir): {"bind": "/workspace", "mode": "rw"},
            str(skill_host_dir): {"bind": "/workspace/.skill/current", "mode": "ro"},
            str(fixture_host_dir): {"bind": "/fixture", "mode": "ro"},
        }
        environment = {
            "AGENT_WORKSPACE": "/workspace",
            "DEEP_AGENT_MODEL": Settings.model,
            "OPENAI_API_BASE": Settings.openai_api_base or "",
            "OPENAI_BASE_URL": Settings.openai_api_base or "",
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "EVAL_LAB_NETWORK_ENABLED": "true" if network_enabled else "false",
            "LANGFUSE_HOST": Settings.langfuse_host,
            "LANGFUSE_PUBLIC_KEY": Settings.langfuse_public_key or "",
            "LANGFUSE_SECRET_KEY": Settings.langfuse_secret_key or "",
            "LANGFUSE_ENABLED": "true" if Settings.langfuse_enabled else "false",
            "LANGFUSE_DEBUG": "true" if Settings.langfuse_debug else "false",
        }
        return self.client.containers.run(
            Settings.eval_lab_sandbox_image,
            detach=True,
            name=container_name,
            volumes=volumes,
            network=Settings.eval_lab_docker_network,
            environment=environment,
        )

    def wait_for_health(self, container_name: str, timeout_seconds: int | None = None) -> None:
        timeout = timeout_seconds or Settings.eval_lab_task_timeout_seconds
        deadline = time.time() + timeout
        url = f"http://{container_name}:8000/health"
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(1)
        if last_error is not None:
            raise TimeoutError(f"Sandbox '{container_name}' did not become healthy: {last_error}") from last_error
        raise TimeoutError(f"Sandbox '{container_name}' did not become healthy")

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
        timeout = timeout_seconds or Settings.eval_lab_task_timeout_seconds
        container = None
        try:
            container = self.start_container(
                run_id=run_id,
                task_id=task_id,
                skill_host_dir=skill_host_dir,
                fixture_host_dir=fixture_host_dir,
                workspace_host_dir=workspace_host_dir,
                network_enabled=Settings.eval_lab_network_enabled if network_enabled is None else network_enabled,
            )
            self.wait_for_health(container.name, timeout)
            response = httpx.post(
                f"http://{container.name}:8000/runs",
                json={"task": build_task_prompt(Path("/workspace/.skill/current/SKILL.md"), task_prompt)},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            changed_files = self._list_changed_files(workspace_host_dir)
            trace_ids = self._extract_trace_ids(self._container_logs(container))
            return SandboxRunResult(
                task_id=task_id,
                status="passed" if payload.get("success") else "failed",
                agent_output=payload.get("output", ""),
                changed_files=changed_files,
                trace_ids=trace_ids,
            )
        except Exception as exc:
            changed_files = self._list_changed_files(workspace_host_dir)
            trace_ids = self._extract_trace_ids(self._container_logs(container)) if container is not None else []
            return SandboxRunResult(
                task_id=task_id,
                status="error",
                agent_output=str(exc),
                changed_files=changed_files,
                trace_ids=trace_ids,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _list_changed_files(self, workspace_host_dir: Path) -> list[str]:
        if not workspace_host_dir.exists():
            return []
        return sorted(
            path.relative_to(workspace_host_dir).as_posix()
            for path in workspace_host_dir.rglob("*")
            if path.is_file()
        )

    def _container_logs(self, container: Any) -> str:
        try:
            logs = container.logs(tail=2000)
        except Exception:
            return ""
        if isinstance(logs, bytes):
            return logs.decode("utf-8", errors="replace")
        return str(logs)

    def _extract_trace_ids(self, logs: str) -> list[str]:
        seen = set()
        trace_ids = []
        for trace_id in _TRACE_ID_PATTERN.findall(logs):
            if trace_id not in seen:
                trace_ids.append(trace_id)
                seen.add(trace_id)
        return trace_ids
