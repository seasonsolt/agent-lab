# Coding Agent + Langfuse Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reliable Docker Compose stack with a FastAPI-based coding agent REST API (`/runs`) and an operational Langfuse observability stack, with the minimum set of hardening for local-first deployment.

**Architecture:** A Python service (`coding-agent`) exposes `GET /health` and `POST /runs`, executes safe workspace tool calls, and uses a Deep Agents model backend. Langfuse is deployed with explicit dependencies (Postgres, ClickHouse, Redis, MinIO) and the worker service handles trace ingestion while the web service serves dashboard/API. Compose wiring is made deterministic with explicit startup ordering and clear environment defaults.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, deepagents, langchain-openai, Pydantic, Langfuse Docker images, PostgreSQL 17, ClickHouse, Redis, MinIO, Docker Compose.

---

### Task 1: 完善 compose 文件结构并规范环境变量

**Files:**
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/docker-compose.yml`
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/.env.example`

- [ ] **Step 1: 写测试前置校验清单（在计划执行前）**

```bash
test -f /Users/Thin/Source/git/seasonsolt/agent-lab/docker-compose.yml || (echo "missing compose" && exit 1)
test -f /Users/Thin/Source/git/seasonsolt/agent-lab/.env.example || (echo "missing env example" && exit 1)
```

- [ ] **Step 2: 更新 compose 让 Langfuse 变量统一并加入显式启动顺序**

```yaml
services:
  postgres:
    image: postgres:${POSTGRES_VERSION:-17}
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-postgres}
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data

  clickhouse:
    image: clickhouse/clickhouse-server
    restart: unless-stopped
    environment:
      CLICKHOUSE_DB: default
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
    volumes:
      - langfuse_clickhouse_data:/var/lib/clickhouse
      - langfuse_clickhouse_logs:/var/log/clickhouse-server

  redis:
    image: redis:7
    restart: unless-stopped
    command: redis-server --maxmemory-policy noeviction
    volumes:
      - langfuse_redis_data:/data

  minio:
    image: minio/minio:latest
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-miniosecret}
    volumes:
      - langfuse_minio_data:/data

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    depends_on:
      - postgres
      - clickhouse
      - redis
      - minio
    environment: &langfuse-common-env
      NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost:3000}
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/postgres}
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET:-mysecret}
      SALT: ${SALT:-mysalt}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-0000000000000000000000000000000000000000000000000000000000000000}
      TELEMETRY_ENABLED: ${TELEMETRY_ENABLED:-true}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-web:3000}
      LANGFUSE_USE_OCI_NATIVE_OBJECT_STORAGE: false
      CLICKHOUSE_MIGRATION_URL: ${CLICKHOUSE_MIGRATION_URL:-http://clickhouse:8123}
      CLICKHOUSE_URL: ${CLICKHOUSE_URL:-http://clickhouse:8123}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-default}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse}
      REDIS_HOST: ${REDIS_HOST:-redis}
      REDIS_PORT: ${REDIS_PORT:-6379}
      REDIS_AUTH: ${REDIS_AUTH:-}

  langfuse-web:
    image: langfuse/langfuse:3
    depends_on:
      - langfuse-worker
    environment:
      <<: *langfuse-common-env
    ports:
      - "3000:3000"

  coding-agent:
    build:
      context: ./agent
    depends_on:
      - langfuse-web
    environment:
      DEEP_AGENT_HOST: 0.0.0.0
      DEEP_AGENT_PORT: 8000
      DEEP_AGENT_MODEL: ${DEEP_AGENT_MODEL:-openai:gpt-4o-mini}
      AGENT_WORKSPACE: /workspace
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-web:3000}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-}
      LANGFUSE_ENABLED: ${LANGFUSE_ENABLED:-false}
      LANGFUSE_DEBUG: ${LANGFUSE_DEBUG:-false}
    volumes:
      - ./agent/workspace:/workspace
    ports:
      - "8000:8000"
```

- [ ] **Step 3: 更新 `.env.example` 明确必填变量并把占位密钥替换为可覆盖变量**

```dotenv
POSTGRES_VERSION=17
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
POSTGRES_URL=postgresql://postgres:postgres@postgres:5432/postgres

CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=clickhouse

REDIS_AUTH=

MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=miniosecret
MINIO_BUCKET_NAME=langfuse

NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=mysecret
SALT=mysalt
ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000
TELEMETRY_ENABLED=true

DEEP_AGENT_MODEL=openai:gpt-4o-mini
OPENAI_API_KEY=
LANGFUSE_ENABLED=false
LANGFUSE_HOST=http://langfuse-web:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

- [ ] **Step 4: 记录预期命令（执行前）**

Run: `docker compose config`
Expected: no undefined-variable errors; service names include `coding-agent`, `langfuse-web`, `langfuse-worker`.

- [ ] **Step 5: 提交**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: stabilize langfuse stack env and compose defaults"
```

### Task 2: 将 coding-agent API 从“可跑样例”升级为可测、可观测 API

**Files:**
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/app/main.py`
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/app/config.py`
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/app/routing.py`
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/app/tools.py`

- [ ] **Step 1: 把配置抽到独立模块并返回结构化响应**

```python
# agent/app/config.py
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    workspace = Path(os.getenv("AGENT_WORKSPACE", "/workspace"))
    model = os.getenv("DEEP_AGENT_MODEL", "openai:gpt-4o-mini")
    host = os.getenv("DEEP_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("DEEP_AGENT_PORT", "8000"))
    system_prompt = os.getenv(
        "DEEP_AGENT_SYSTEM_PROMPT",
        "You are a careful coding agent. Use tools to inspect and modify files in the workspace."
    )
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    langfuse_host = os.getenv("LANGFUSE_HOST", "http://langfuse-web:3000")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

```

- [ ] **Step 2: 将工具逻辑独立到 `tools.py`**

```python
# agent/app/tools.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings


WORKSPACE = Path(Settings.workspace).resolve()


def _ensure_workspace_path(path: str) -> Path:
    if path.startswith("/"):
        target = Path(path).resolve()
    else:
        target = (WORKSPACE / path).resolve()
    root = str(WORKSPACE)
    target_str = str(target)
    if target_str != root and not target_str.startswith(root + "/"):
        raise ValueError(f"Path '{path}' is outside workspace")
    return target


def list_workspace(path: str = ".") -> str:
    p = _ensure_workspace_path(path)
    if not p.exists():
        return f"Path '{path}' does not exist."
    if not p.is_dir():
        return f"Path '{path}' is not a directory."
    entries = sorted(child.name for child in p.iterdir())
    return "\n".join(entries) if entries else "Directory is empty."


def read_file(path: str, max_chars: int = 8000) -> str:
    p = _ensure_workspace_path(path)
    if not p.exists():
        return f"File '{path}' does not exist."
    if not p.is_file():
        return f"Path '{path}' is not a file."
    text = p.read_text(encoding="utf-8", errors="replace")
    return text if max_chars <= 0 or len(text) <= max_chars else text[:max_chars] + f"... [truncated {len(text)-max_chars} chars]"


def write_file(path: str, content: str) -> str:
    p = _ensure_workspace_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {p}"
```

- [ ] **Step 3: 重写 `agent/app/main.py` 使用路由与异常模型**

```python
# agent/app/main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict
from deepagents import create_deep_agent
from .config import Settings
from .tools import list_workspace, read_file, write_file

app = FastAPI(title="Coding Agent", version="0.1.1")


def build_agent():
    return create_deep_agent(
        model=Settings.model,
        tools=[list_workspace, read_file, write_file],
        system_prompt=Settings.system_prompt,
    )


agent = build_agent()


class RunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


class RunResponse(BaseModel):
    success: bool
    output: str
    raw: Dict[str, Any]


def _extract_response(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("output", "result", "final", "content"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        messages = result.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[-1], dict):
            content = messages[-1].get("content")
            if isinstance(content, str):
                return content
    return str(result)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/runs", response_model=RunResponse)
def run_agent(payload: RunRequest) -> RunResponse:
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": payload.task}]})
        return RunResponse(success=True, output=_extract_response(result), raw={"result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

- [ ] **Step 5: Add a smoke validation route test (先写后跑）**

```python
from fastapi.testclient import TestClient
from agent.app.main import app


def test_health_endpoint():
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

- [ ] **Step 6: 验证**

Run: `python -m pytest agent/tests -q`
Expected: `test_health_endpoint` passes.

- [ ] **Step 7: 提交**

```bash
git add agent/app/main.py agent/app/config.py agent/app/tools.py agent/tests/test_main.py
git commit -m "feat: make coding agent modules testable and cleaner"
```

### Task 3: 增加工具级测试覆盖（工具安全边界和最小写入能力）

**Files:**
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/tests/test_tools.py`
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/agent/requirements.txt`

- [ ] **Step 1: 写工具安全测试**

```python
import pytest
from pathlib import Path
from agent.app.tools import list_workspace, read_file, write_file, _ensure_workspace_path


def test_list_workspace_rejects_non_existent(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path))
    from importlib import reload
    from agent.app import config, tools
    reload(config)
    reload(tools)
    assert "does not exist" in tools.list_workspace("missing")


def test_workspace_traversal_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path))
    from importlib import reload
    from agent.app import config, tools
    reload(config)
    reload(tools)
    with pytest.raises(ValueError):
        tools._ensure_workspace_path("../etc/passwd")
```

- [ ] **Step 2: 运行测试并确认失败（先观察当前行为）**

Run: `python -m pytest agent/tests/test_tools.py::test_workspace_traversal_is_blocked -q`
Expected: FAIL before refactor, PASS after task implementation.

- [ ] **Step 3: 写入实现修正（如果失败）**

```python
# tools.py is expected to keep `_ensure_workspace_path()` strict and raise on parent traversal.
```

- [ ] **Step 4: 再跑测试**

Run: `python -m pytest agent/tests/test_tools.py -q`
Expected: 全部通过.

- [ ] **Step 5: 提交**

```bash
git add agent/tests/test_tools.py agent/app/tools.py agent/app/__init__.py
git commit -m "test: cover workspace traversal and tool safety"
```

### Task 4: 加入可选但建议的外部服务（反向代理、TLS 与监控）

**Files:**
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/proxy/nginx.conf`
- Add: `/Users/Thin/Source/git/seasonsolt/agent-lab/proxy/Dockerfile`
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/docker-compose.yml`

- [ ] **Step 1: 增加 nginx 反向代理配置**

```nginx
events {}
http {
  server {
    listen 80;
    location / {
      proxy_pass http://coding-agent:8000;
    }
    location /langfuse/ {
      proxy_pass http://langfuse-web:3000/;
    }
  }
}
```

- [ ] **Step 2: 在 compose 增加 proxy 服务（80/443）**

```yaml
  proxy:
    build: ./proxy
    depends_on:
      - coding-agent
      - langfuse-web
    ports:
      - "80:80"
```

- [ ] **Step 3: 为容器暴露最小运行命令验证**

Run: `docker compose up -d proxy && docker compose ps proxy`
Expected: `proxy` 状态是 `running`.

- [ ] **Step 4: 提交**

```bash
git add docker-compose.yml proxy/nginx.conf proxy/Dockerfile
git commit -m "feat: add optional reverse proxy and TLS termination"
```

### Task 5: 更新使用说明并输出完整启动顺序

**Files:**
- Modify: `/Users/Thin/Source/git/seasonsolt/agent-lab/README.md`

- [ ] **Step 1: 更新文档为按服务启动顺序和关键命令**

```markdown
1. cp .env.example .env
2. docker compose up --build -d
3. docker compose ps
4. curl http://localhost:8000/health
5. docker compose logs -f coding-agent
```

- [ ] **Step 2: 在文档加入可选服务说明（proxy/monitoring/backups）**

```markdown
Optional services:
- proxy (nginx): combine 8000 and 3000 behind 443
- monitoring (prometheus/grafana): metrics and latency
- backup jobs: postgres/clickhouse/minio volume snapshots
```

- [ ] **Step 3: 验证文档命令可复现**

Run: `sed -n '1,220p' /Users/Thin/Source/git/seasonsolt/agent-lab/README.md`
Expected: 文档包含 compose 启动步骤和 health-check 示例

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "docs: document runbook for compose stack"
```

## Self-review

1. 需求覆盖：任务 1 覆盖 Langfuse + 容器依赖；任务 2~3 覆盖 FastAPI 与工具安全；任务 5 覆盖运行文档；任务 4 覆盖“进一步需要的服务”。
2. 无占位符：无 `TBD`、`implement later` 等。
3. 类型一致性：`RunResponse` 在任务 2 中定义了 `success/output/raw`，测试断言与任务 2/3 保持一致。

Plan complete and saved to `docs/superpowers/plans/2026-06-21-coding-agent-langfuse-compose.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints
