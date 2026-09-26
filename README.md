# Docker Compose: FastAPI Coding Agent + Langfuse

This project runs a FastAPI coding agent service (`/health`, `/runs`) and a local Langfuse observability stack.

## 1) Start from scratch

```bash
cp .env.example .env
docker compose up --build -d
```

Set the model API endpoint explicitly if your provider is not OpenAI:

```bash
OPENAI_BASE_URL=<your_openai_compatible_base_url>/v1 \
OPENAI_API_BASE=<your_openai_compatible_base_url>/v1 \
OPENAI_API_KEY=<your_key> \
DEEP_AGENT_MODEL=openai:gpt-4o-mini \
LANGFUSE_ENABLED=true \
LANGFUSE_PUBLIC_KEY=<lf_public_key> \
LANGFUSE_SECRET_KEY=<lf_secret_key> \
docker compose up -d --force-recreate coding-agent
```

## 2) Verify startup

```bash
docker compose ps
curl http://localhost:8000/health
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"task":"List files in the workspace root."}'
```

Services:

- `langfuse-web`: `http://localhost:3000`
- `coding-agent`: `http://localhost:8000`
- `langfuse-worker`
- `postgres`
- `clickhouse`
- `redis`
- `minio`
- `proxy` (optional): route `/` to agent and `/langfuse/` to Langfuse

## 3) Optional services to consider

- `proxy` (nginx): unify public entry (`/` -> agent, `/langfuse/` -> Langfuse) and easy TLS termination.
- `monitoring`: Prometheus + Grafana for host/container metrics.
- `backup`: scheduled snapshots of `postgres` / `clickhouse` / `minio` volumes.

Logs:

```bash
docker compose logs -f coding-agent
```

## Skill Evaluation Lab

Run a sample skill evaluation:

```bash
mkdir -p /tmp/agent-lab-runs
docker compose up -d --build
python3 -m skill_lab.cli run \
  --skill ./skills/example-coding-skill \
  --task-pack ./task_packs/coding-basic \
  --api-url http://localhost:8000 \
  --network
```

Compare a treatment skill against a baseline skill:

```bash
python3 -m skill_lab.cli compare \
  --baseline ./skills/example-coding-skill \
  --treatment ./skills/ddia-system-design \
  --task-pack ./task_packs/ddia-coding-real \
  --api-url http://localhost:8000 \
  --runs 3 \
  --network \
  --timeout-seconds 300
```

The comparison output includes mean scores, score lift, pass-rate delta, error rate, timeout rate, run IDs, and a verdict.

Eval API:

- `POST /eval-runs`
- `GET /eval-runs/{id}`
- `GET /eval-runs/{id}/report`
