from __future__ import annotations

from typing import Any

from .store import StateStore


class DurableGraphRunner:
    """
    Explicit durable state-graph runner.

    Responsibilities:
    - create runs
    - persist transitions
    - create HITL tasks
    - persist failures
    - recover latest checkpoint
    """

    def __init__(
        self,
        store: StateStore,
        graph_name: str,
    ):
        self.store = store
        self.graph_name = graph_name

    def start(
        self,
        state: dict[str, Any],
        ticket_id: int | None,
        first_state: str,
    ) -> str:
        return self.store.create_run(
            self.graph_name,
            ticket_id,
            state,
            first_state,
        )

    def transition(
        self,
        run_id: str,
        next_state: str,
        state: dict[str, Any],
        *,
        run_status: str = "RUNNING",
    ) -> str:
        return self.store.checkpoint(
            run_id,
            next_state,
            state,
            run_status=run_status,
        )

    def pause_for_hitl(
        self,
        run_id: str,
        ticket_id: int | None,
        reason: str,
        state: dict[str, Any],
    ) -> str:
        return self.store.create_hitl_task(
            run_id,
            ticket_id,
            reason,
            state,
        )

    def fail(
        self,
        run_id: str,
        ticket_id: int | None,
        node_name: str,
        exc: Exception,
        state: dict[str, Any],
    ) -> str:
        return self.store.create_failure_ticket(
            run_id,
            ticket_id,
            node_name,
            exc,
            state,
        )

    def recover(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        checkpoint = self.store.latest_checkpoint(
            run_id
        )

        if checkpoint is None:
            raise ValueError(
                f"No checkpoint exists for run {run_id}"
            )

        return checkpoint