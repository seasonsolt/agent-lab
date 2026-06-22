from __future__ import annotations

import os


class Settings:
    compose_project_name = os.getenv("COMPOSE_PROJECT_NAME", "agent-lab")
    workspace = os.getenv("AGENT_WORKSPACE", "/workspace")
    model = os.getenv("DEEP_AGENT_MODEL", "openai:gpt-4o-mini")
    openai_api_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    host = os.getenv("DEEP_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("DEEP_AGENT_PORT", "8000"))
    system_prompt = os.getenv(
        "DEEP_AGENT_SYSTEM_PROMPT",
        "You are a careful coding agent. Use tools to inspect and modify files in the workspace.",
    )
    langfuse_host = os.getenv("LANGFUSE_HOST", "http://langfuse-web:3000")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    langfuse_debug = os.getenv("LANGFUSE_DEBUG", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/postgres")
    eval_lab_host_project_dir = os.getenv("EVAL_LAB_HOST_PROJECT_DIR", os.getcwd())
    eval_lab_container_project_dir = os.getenv("EVAL_LAB_CONTAINER_PROJECT_DIR", "/lab")
    eval_lab_host_runs_dir = os.getenv("EVAL_LAB_HOST_RUNS_DIR", "/tmp/agent-lab-runs")
    eval_lab_container_runs_dir = os.getenv("EVAL_LAB_CONTAINER_RUNS_DIR", "/runs")
    eval_lab_sandbox_image = os.getenv("EVAL_LAB_SANDBOX_IMAGE", f"{compose_project_name}-coding-agent")
    eval_lab_docker_network = os.getenv("EVAL_LAB_DOCKER_NETWORK", f"{compose_project_name}_sandbox")
    eval_lab_network_enabled = os.getenv("EVAL_LAB_NETWORK_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    eval_lab_task_timeout_seconds = int(os.getenv("EVAL_LAB_TASK_TIMEOUT_SECONDS", "300"))
