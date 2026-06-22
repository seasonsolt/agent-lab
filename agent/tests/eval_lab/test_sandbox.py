from __future__ import annotations

from pathlib import Path

import httpx

from app.eval_lab.sandbox import DockerSandbox, SandboxRunResult, build_container_name, build_task_prompt


def test_build_task_prompt_includes_skill_workspace_and_task():
    prompt = build_task_prompt(
        skill_container_path=Path("/skills/demo/SKILL.md"),
        task_prompt="Fix the failing test.",
    )

    assert "/skills/demo/SKILL.md" in prompt
    assert "/workspace" in prompt
    assert "Fix the failing test." in prompt


def test_sandbox_result_defaults_lists():
    result = SandboxRunResult(task_id="task-1", status="passed", agent_output="done")

    assert result.changed_files == []
    assert result.trace_ids == []


class FakeContainers:
    def __init__(self) -> None:
        self.run_kwargs = None

    def run(self, image, **kwargs):
        self.run_kwargs = {"image": image, **kwargs}
        return FakeContainer("agent-lab-run-1-task-1")


class FakeDockerClient:
    def __init__(self) -> None:
        self.containers = FakeContainers()


class FakeContainer:
    def __init__(self, name: str, fail_remove: bool = False, logs: bytes = b"") -> None:
        self.name = name
        self.fail_remove = fail_remove
        self.log_output = logs
        self.removed = False

    def logs(self, tail: int | None = None) -> bytes:
        return self.log_output

    def remove(self, force: bool = False) -> None:
        if self.fail_remove:
            raise RuntimeError("remove failed")
        self.removed = force


def test_start_container_uses_configured_network_and_agent_environment(monkeypatch, tmp_path):
    docker_client = FakeDockerClient()
    monkeypatch.setattr("app.eval_lab.sandbox.docker.from_env", lambda: docker_client)
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.eval_lab_sandbox_image", "coding-agent:test")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.eval_lab_docker_network", "agent-lab_sandbox")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.eval_lab_network_enabled", False)
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.model", "openai:test-model")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.openai_api_base", "http://openai-proxy")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.langfuse_host", "http://langfuse")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.langfuse_public_key", "pk")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.langfuse_secret_key", "sk")
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.langfuse_enabled", True)
    monkeypatch.setattr("app.eval_lab.sandbox.Settings.langfuse_debug", False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://should-not-leak")
    monkeypatch.setenv("DOCKER_HOST", "tcp://should-not-leak:2375")

    sandbox = DockerSandbox()
    sandbox.start_container(
        run_id="run_1",
        task_id="task_1",
        skill_host_dir=tmp_path / "skill",
        fixture_host_dir=tmp_path / "fixture",
        workspace_host_dir=tmp_path / "workspace",
        network_enabled=False,
    )

    kwargs = docker_client.containers.run_kwargs
    assert kwargs["image"] == "coding-agent:test"
    assert kwargs["network"] == "agent-lab_sandbox"
    assert kwargs["volumes"][str(tmp_path / "skill")] == {"bind": "/workspace/.skill/current", "mode": "ro"}
    assert kwargs["volumes"][str(tmp_path / "fixture")] == {"bind": "/fixture", "mode": "ro"}
    assert kwargs["volumes"][str(tmp_path / "workspace")] == {"bind": "/workspace", "mode": "rw"}
    assert all("/var/run/docker.sock" not in source for source in kwargs["volumes"])
    assert kwargs["environment"]["EVAL_LAB_NETWORK_ENABLED"] == "false"
    assert kwargs["environment"]["OPENAI_API_KEY"] == "test-key"
    assert "DATABASE_URL" not in kwargs["environment"]
    assert "DOCKER_HOST" not in kwargs["environment"]


def test_build_container_name_sanitizes_and_adds_hash_suffix():
    name = build_container_name("run/with spaces:and_symbols", "task/with spaces:and_symbols")

    assert len(name) <= 63
    assert "/" not in name
    assert " " not in name
    assert ":" not in name
    assert name.startswith("agent-lab-run-with-spaces-and-symbols-task")


def test_run_task_posts_prompt_and_lists_changed_files(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    nested = workspace / "src"
    nested.mkdir(parents=True)
    (nested / "answer.py").write_text("print('done')\n", encoding="utf-8")
    container = FakeContainer("sandbox-1")
    requests = []

    monkeypatch.setattr(
        DockerSandbox,
        "start_container",
        lambda self, **kwargs: container,
    )
    monkeypatch.setattr(DockerSandbox, "wait_for_health", lambda self, container_name, timeout_seconds: None)

    def fake_post(url, json, timeout):
        requests.append({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(
            200,
            json={"success": True, "output": "agent done"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.eval_lab.sandbox.httpx.post", fake_post)
    sandbox = DockerSandbox.__new__(DockerSandbox)

    result = sandbox.run_task(
        run_id="run-1",
        task_id="task-1",
        task_prompt="Do the work.",
        skill_host_dir=tmp_path / "skill",
        fixture_host_dir=tmp_path / "fixture",
        workspace_host_dir=workspace,
        network_enabled=True,
        timeout_seconds=30,
    )

    assert requests[0]["url"] == "http://sandbox-1:8000/runs"
    assert "/workspace/.skill/current/SKILL.md" in requests[0]["json"]["task"]
    assert "Do the work." in requests[0]["json"]["task"]
    assert result == SandboxRunResult(
        task_id="task-1",
        status="passed",
        agent_output="agent done",
        changed_files=["src/answer.py"],
        trace_ids=[],
    )
    assert container.removed is True


def test_run_task_ignores_cleanup_failure(monkeypatch, tmp_path):
    container = FakeContainer("sandbox-1", fail_remove=True)
    monkeypatch.setattr(DockerSandbox, "start_container", lambda self, **kwargs: container)
    monkeypatch.setattr(DockerSandbox, "wait_for_health", lambda self, container_name, timeout_seconds: None)

    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={"success": True, "output": "agent done"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.eval_lab.sandbox.httpx.post", fake_post)
    sandbox = DockerSandbox.__new__(DockerSandbox)

    result = sandbox.run_task(
        run_id="run-1",
        task_id="task-1",
        task_prompt="Do the work.",
        skill_host_dir=tmp_path / "skill",
        fixture_host_dir=tmp_path / "fixture",
        workspace_host_dir=tmp_path / "workspace",
        network_enabled=True,
        timeout_seconds=30,
    )

    assert result.status == "passed"
    assert result.agent_output == "agent done"


def test_run_task_returns_error_result_without_real_docker(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "partial.py").write_text("changed\n", encoding="utf-8")
    container = FakeContainer(
        "sandbox-1",
        logs=(
            b'{"context": {"trace_id": "11111111111111111111111111111111"}}\n'
            b'{"context": {"trace_id": "11111111111111111111111111111111"}}\n'
            b'{"context": {"trace_id": "22222222222222222222222222222222"}}\n'
        ),
    )
    monkeypatch.setattr(DockerSandbox, "start_container", lambda self, **kwargs: container)
    monkeypatch.setattr(
        DockerSandbox,
        "wait_for_health",
        lambda self, container_name, timeout_seconds: (_ for _ in ()).throw(TimeoutError("not healthy")),
    )
    sandbox = DockerSandbox.__new__(DockerSandbox)

    result = sandbox.run_task(
        run_id="run-1",
        task_id="task-1",
        task_prompt="Do the work.",
        skill_host_dir=tmp_path / "skill",
        fixture_host_dir=tmp_path / "fixture",
        workspace_host_dir=workspace,
        network_enabled=True,
        timeout_seconds=1,
    )

    assert result.task_id == "task-1"
    assert result.status == "error"
    assert "not healthy" in result.agent_output
    assert result.changed_files == ["partial.py"]
    assert result.trace_ids == ["11111111111111111111111111111111", "22222222222222222222222222222222"]
    assert container.removed is True
