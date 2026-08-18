from __future__ import annotations

import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class StateStore:
    """
    Durable storage for:

    - graph runs
    - graph checkpoints
    - HITL tasks
    - failure tickets
    """

    def __init__(
        self,
        db_path: str | Path = "db/support.db",
    ):
        self.db_path = str(db_path)

        Path(
            self.db_path
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_schema()

    def _connect(self) -> sqlite3.Connection:

        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row

        return conn

    def _init_schema(self) -> None:

        with self._connect() as conn:

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_runs (
                    run_id TEXT PRIMARY KEY,
                    graph_name TEXT NOT NULL,
                    ticket_id INTEGER,
                    status TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    state_name TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES graph_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS
                idx_checkpoints_run
                ON graph_checkpoints(run_id, created_at);

                CREATE TABLE IF NOT EXISTS hitl_tasks (
                    task_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    ticket_id INTEGER,
                    reason TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    admin_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(run_id)
                        REFERENCES graph_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS
                idx_hitl_status
                ON hitl_tasks(status);

                CREATE TABLE IF NOT EXISTS failure_tickets (
                    failure_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    ticket_id INTEGER,
                    node_name TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolution TEXT,
                    admin_id TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY(run_id)
                        REFERENCES graph_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS
                idx_failure_status
                ON failure_tickets(status);
                """
            )

    # =========================================================
    # Graph Runs
    # =========================================================

    def create_run(
        self,
        graph_name: str,
        ticket_id: int | None,
        state: dict[str, Any],
        current_state: str,
    ) -> str:

        run_id = str(
            uuid.uuid4()
        )

        now = utc_now()

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO graph_runs
                (
                    run_id,
                    graph_name,
                    ticket_id,
                    status,
                    current_state,
                    state_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    graph_name,
                    ticket_id,
                    "RUNNING",
                    current_state,
                    json.dumps(
                        state,
                        ensure_ascii=False,
                        default=str,
                    ),
                    now,
                    now,
                ),
            )

        self.checkpoint(
            run_id,
            current_state,
            state,
        )

        return run_id

    # =========================================================
    # Checkpoints
    # =========================================================

    def checkpoint(
        self,
        run_id: str,
        state_name: str,
        state: dict[str, Any],
        *,
        run_status: str = "RUNNING",
    ) -> str:

        checkpoint_id = str(
            uuid.uuid4()
        )

        now = utc_now()

        state_json = json.dumps(
            state,
            ensure_ascii=False,
            default=str,
        )

        with self._connect() as conn:

            conn.execute(
                """
                UPDATE graph_runs
                SET
                    status = ?,
                    current_state = ?,
                    state_json = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    run_status,
                    state_name,
                    state_json,
                    now,
                    run_id,
                ),
            )

            conn.execute(
                """
                INSERT INTO graph_checkpoints
                (
                    checkpoint_id,
                    run_id,
                    state_name,
                    state_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    run_id,
                    state_name,
                    state_json,
                    now,
                ),
            )

        return checkpoint_id

    def latest_checkpoint(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT
                    checkpoint_id,
                    state_name,
                    state_json,
                    created_at
                FROM graph_checkpoints
                WHERE run_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "checkpoint_id": row[
                "checkpoint_id"
            ],
            "state_name": row[
                "state_name"
            ],
            "state": json.loads(
                row["state_json"]
            ),
            "created_at": row[
                "created_at"
            ],
        }

    def get_run(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM graph_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        result = dict(row)

        result["state"] = json.loads(
            result.pop("state_json")
        )

        return result

    # =========================================================
    # HITL
    # =========================================================

    def create_hitl_task(
        self,
        run_id: str,
        ticket_id: int | None,
        reason: str,
        state: dict[str, Any],
    ) -> str:

        task_id = str(
            uuid.uuid4()
        )

        now = utc_now()

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO hitl_tasks
                (
                    task_id,
                    run_id,
                    ticket_id,
                    reason,
                    state_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    run_id,
                    ticket_id,
                    reason,
                    json.dumps(
                        state,
                        ensure_ascii=False,
                        default=str,
                    ),
                    "PENDING",
                    now,
                ),
            )

        self.checkpoint(
            run_id,
            "WAITING_FOR_ADMIN",
            state,
            run_status="WAITING_HITL",
        )

        return task_id

    def resolve_hitl_task(
        self,
        task_id: str,
        decision: str,
        admin_id: str,
    ) -> None:

        now = utc_now()

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT run_id
                FROM hitl_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    f"HITL task not found: {task_id}"
                )

            conn.execute(
                """
                UPDATE hitl_tasks
                SET
                    status = 'RESOLVED',
                    decision = ?,
                    admin_id = ?,
                    resolved_at = ?
                WHERE task_id = ?
                """,
                (
                    decision,
                    admin_id,
                    now,
                    task_id,
                ),
            )

            conn.execute(
                """
                UPDATE graph_runs
                SET
                    status = 'RUNNING',
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    now,
                    row["run_id"],
                ),
            )

    def get_hitl_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT *
                FROM hitl_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        result = dict(row)

        result["state"] = json.loads(
            result.pop("state_json")
        )

        return result

    def list_pending_hitl(
        self,
    ) -> list[dict[str, Any]]:

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    task_id,
                    run_id,
                    ticket_id,
                    reason,
                    status,
                    created_at
                FROM hitl_tasks
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # =========================================================
    # Failure Tickets
    # =========================================================

    def create_failure_ticket(
        self,
        run_id: str,
        ticket_id: int | None,
        node_name: str,
        exc: Exception,
        state: dict[str, Any],
    ) -> str:

        failure_id = str(
            uuid.uuid4()
        )

        now = utc_now()

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO failure_tickets
                (
                    failure_id,
                    run_id,
                    ticket_id,
                    node_name,
                    error_type,
                    error_message,
                    state_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    failure_id,
                    run_id,
                    ticket_id,
                    node_name,
                    type(exc).__name__,
                    str(exc),
                    json.dumps(
                        state,
                        ensure_ascii=False,
                        default=str,
                    ),
                    "OPEN",
                    now,
                ),
            )

        self.checkpoint(
            run_id,
            f"FAILED:{node_name}",
            state,
            run_status="FAILED",
        )

        return failure_id

    def resolve_failure(
        self,
        failure_id: str,
        resolution: str,
        admin_id: str,
    ) -> None:

        now = utc_now()

        with self._connect() as conn:

            row = conn.execute(
                """
                SELECT run_id
                FROM failure_tickets
                WHERE failure_id = ?
                """,
                (failure_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    f"Failure ticket not found: {failure_id}"
                )

            conn.execute(
                """
                UPDATE failure_tickets
                SET
                    status = 'RESOLVED',
                    resolution = ?,
                    admin_id = ?,
                    resolved_at = ?
                WHERE failure_id = ?
                """,
                (
                    resolution,
                    admin_id,
                    now,
                    failure_id,
                ),
            )

            conn.execute(
                """
                UPDATE graph_runs
                SET
                    status = 'RUNNING',
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    now,
                    row["run_id"],
                ),
            )

    def list_failure_tickets(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:

        query = """
            SELECT
                failure_id,
                run_id,
                ticket_id,
                node_name,
                error_type,
                error_message,
                status,
                created_at,
                resolved_at
            FROM failure_tickets
        """

        params: tuple[Any, ...] = ()

        if status:

            query += """
                WHERE status = ?
            """

            params = (
                status,
            )

        query += """
            ORDER BY created_at DESC
        """

        with self._connect() as conn:

            rows = conn.execute(
                query,
                params,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]