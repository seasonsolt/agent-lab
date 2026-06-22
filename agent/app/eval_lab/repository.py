from __future__ import annotations

import uuid
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .db import connect


class EvalRepository:
    def upsert_skill(
        self,
        skill_id: str,
        name: str,
        version_hash: str,
        source_type: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO eval_skills (id, name, version_hash, source_type, source_path, manifest)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        version_hash = EXCLUDED.version_hash,
                        source_type = EXCLUDED.source_type,
                        source_path = EXCLUDED.source_path,
                        manifest = EXCLUDED.manifest
                    RETURNING *
                    """,
                    (skill_id, name, version_hash, source_type, source_path, Jsonb(manifest)),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    def upsert_task_pack(
        self,
        task_pack_id: str,
        name: str,
        domain: str,
        version_hash: str,
        source_path: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO eval_task_packs (id, name, domain, version_hash, source_path, manifest)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        domain = EXCLUDED.domain,
                        version_hash = EXCLUDED.version_hash,
                        source_path = EXCLUDED.source_path,
                        manifest = EXCLUDED.manifest
                    RETURNING *
                    """,
                    (task_pack_id, name, domain, version_hash, source_path, Jsonb(manifest)),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    def create_eval_run(self, skill_id: str, task_pack_id: str) -> dict[str, Any]:
        run_id = f"eval-{uuid.uuid4().hex}"
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO eval_runs (id, skill_id, task_pack_id, status)
                    VALUES (%s, %s, %s, 'queued')
                    RETURNING *
                    """,
                    (run_id, skill_id, task_pack_id),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    def mark_run_running(self, run_id: str, sandbox_container_id: str) -> None:
        with connect() as conn:
            cursor = conn.execute(
                """
                UPDATE eval_runs
                SET status = 'running', sandbox_container_id = %s, started_at = now()
                WHERE id = %s
                """,
                (sandbox_container_id, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(run_id)
            conn.commit()

    def finish_run(self, run_id: str, status: str, trace_ids: list[str], error: str | None = None) -> None:
        with connect() as conn:
            cursor = conn.execute(
                """
                UPDATE eval_runs
                SET status = %s, langfuse_trace_ids = %s, finished_at = now(), error = %s
                WHERE id = %s
                """,
                (status, Jsonb(trace_ids), error, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(run_id)
            conn.commit()

    def add_score(
        self,
        eval_run_id: str,
        task_id: str,
        score_type: str,
        score: float,
        max_score: float,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        score_id = f"score-{uuid.uuid4().hex}"
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO eval_scores (id, eval_run_id, task_id, score_type, score, max_score, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (score_id, eval_run_id, task_id, score_type, score, max_score, Jsonb(details)),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row)

    def get_eval_run(self, run_id: str) -> dict[str, Any]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM eval_runs WHERE id = %s", (run_id,))
                row = cur.fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM eval_skills WHERE id = %s", (skill_id,))
                row = cur.fetchone()
        if row is None:
            raise KeyError(skill_id)
        return dict(row)

    def get_task_pack(self, task_pack_id: str) -> dict[str, Any]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM eval_task_packs WHERE id = %s", (task_pack_id,))
                row = cur.fetchone()
        if row is None:
            raise KeyError(task_pack_id)
        return dict(row)

    def list_scores(self, eval_run_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM eval_scores WHERE eval_run_id = %s ORDER BY created_at ASC",
                    (eval_run_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]
