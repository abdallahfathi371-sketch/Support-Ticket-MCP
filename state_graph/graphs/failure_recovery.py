from __future__ import annotations

import inspect
from typing import Any, Callable

from ..common.graph_base import DurableGraphRunner
from ..common.store import StateStore
from ..common.react import ConstrainedMCPReAct
from ..common.mcp_adapter import MCPToolAdapter
from ..recovery.lats_selector import LATSRecoverySelector


GRAPH_NAME = "failure_recovery"


def start_failure_recovery(
    ticket_id: int,
    *,
    db_path: str = "db/support.db",
) -> tuple[str, str]:
    """
    Start the durable failure-recovery graph.

    Flow:

        LOAD_CHECKPOINTED_WORK
                |
        EXECUTE_ACTION
             /     \
        success   failure
                    |
                  FAILED
                    |
              LATS selection
                    |
              admin resolves
                    |
              RECOVERY_RESUME
                    |
            constrained ReAct
                    |
              VERIFY_RECOVERY
                    |
                   DONE
    """

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    state: dict[str, Any] = {
        "ticket_id": ticket_id,
        "status": "RUNNING",
        "current_state": "LOAD_CHECKPOINTED_WORK",
        "attempt": 0,
        "last_result": None,
        "failure_id": None,
        "failure_type": None,
        "failure_message": None,
        "recovery_strategy": None,
        "recovery_score": None,
        "recovery_reason": None,
        "recovery_llm_used": False,
        "recovery_trace": [],
        "recovery_result": None,
        "recovery_resumed_with_strategy": None,
        "recovered_from_checkpoint": None,
    }

    run_id = runner.start(
        state,
        ticket_id=ticket_id,
        first_state="LOAD_CHECKPOINTED_WORK",
    )

    state["current_state"] = "EXECUTE_ACTION"
    state["attempt"] = 1

    runner.transition(
        run_id,
        "EXECUTE_ACTION",
        state,
    )

    return run_id, "EXECUTE_ACTION"


def execute_action(
    run_id: str,
    action: Callable[[], Any],
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Execute a risky graph node.

    Unexpected exceptions become durable failure tickets.
    LATS selects and persists the recovery strategy.
    """

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    run = store.get_run(run_id)

    if run is None:
        raise ValueError(
            f"Run not found: {run_id}"
        )

    state = run["state"]
    ticket_id = run["ticket_id"]

    try:
        result = action()

        if inspect.isawaitable(result):
            raise RuntimeError(
                "execute_action received an async action. "
                "Use execute_async_action() instead."
            )

        state["last_result"] = result
        state["status"] = "RUNNING"
        state["current_state"] = "VERIFY_RESULT"

        runner.transition(
            run_id,
            "VERIFY_RESULT",
            state,
        )

        return "VERIFY_RESULT"

    except Exception as exc:

        # -----------------------------------------------------
        # LATS selects a recovery strategy once.
        # -----------------------------------------------------

        selector = LATSRecoverySelector()

        candidate = selector.select(
            error_type=type(exc).__name__,
            attempt=state.get(
                "attempt",
                1,
            ),
            action_retryable=False,
            alternative_available=False,
        )

        # -----------------------------------------------------
        # Persist failure ticket.
        #
        # The ticket stores the checkpoint at failure time.
        # The graph run is then updated with LATS metadata.
        # -----------------------------------------------------

        failure_id = runner.fail(
            run_id,
            ticket_id,
            "EXECUTE_ACTION",
            exc,
            state,
        )

        # -----------------------------------------------------
        # Persist complete recovery decision in graph state.
        # -----------------------------------------------------

        state["failure_id"] = failure_id

        state["failure_type"] = (
            type(exc).__name__
        )

        state["failure_message"] = str(exc)

        state["recovery_strategy"] = (
            candidate.strategy
        )

        state["recovery_score"] = (
            candidate.score
        )

        state["recovery_reason"] = (
            candidate.reason
        )

        state["recovery_llm_used"] = (
            candidate.llm_used
        )

        state["status"] = "FAILED"
        state["current_state"] = "FAILED"

        # IMPORTANT:
        # This checkpoint makes the LATS decision durable
        # in graph_runs.state_json and graph_checkpoints.
        runner.transition(
            run_id,
            "FAILED",
            state,
            run_status="FAILED",
        )

        return f"FAILED:{failure_id}"


async def execute_async_action(
    run_id: str,
    action: Callable[[], Any],
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Async version for risky MCP-backed actions.
    """

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    run = store.get_run(run_id)

    if run is None:
        raise ValueError(
            f"Run not found: {run_id}"
        )

    state = run["state"]
    ticket_id = run["ticket_id"]

    try:
        result = action()

        if inspect.isawaitable(result):
            result = await result

        state["last_result"] = result
        state["status"] = "RUNNING"
        state["current_state"] = "VERIFY_RESULT"

        runner.transition(
            run_id,
            "VERIFY_RESULT",
            state,
        )

        return "VERIFY_RESULT"

    except Exception as exc:

        selector = LATSRecoverySelector()

        candidate = selector.select(
            error_type=type(exc).__name__,
            attempt=state.get(
                "attempt",
                1,
            ),
            action_retryable=False,
            alternative_available=False,
        )

        failure_id = runner.fail(
            run_id,
            ticket_id,
            "EXECUTE_ACTION",
            exc,
            state,
        )

        state["failure_id"] = failure_id
        state["failure_type"] = (
            type(exc).__name__
        )
        state["failure_message"] = str(exc)

        state["recovery_strategy"] = (
            candidate.strategy
        )

        state["recovery_score"] = (
            candidate.score
        )

        state["recovery_reason"] = (
            candidate.reason
        )

        state["recovery_llm_used"] = (
            candidate.llm_used
        )

        state["status"] = "FAILED"
        state["current_state"] = "FAILED"

        runner.transition(
            run_id,
            "FAILED",
            state,
            run_status="FAILED",
        )

        return f"FAILED:{failure_id}"


def get_recovery_plan(
    failure_id: str,
    *,
    db_path: str = "db/support.db",
) -> dict[str, Any]:
    """
    Return the LATS recovery decision persisted in the graph run.

    IMPORTANT:
    The graph run is the source of truth because the LATS
    decision is checkpointed after the failure ticket is created.
    """

    store = StateStore(db_path)

    # ---------------------------------------------------------
    # Find the failure ticket and its run.
    # ---------------------------------------------------------

    with store._connect() as conn:
        row = conn.execute(
            """
            SELECT
                failure_id,
                run_id,
                status,
                error_type,
                error_message
            FROM failure_tickets
            WHERE failure_id = ?
            """,
            (failure_id,),
        ).fetchone()

    if row is None:
        raise ValueError(
            f"Failure ticket not found: {failure_id}"
        )

    # ---------------------------------------------------------
    # Get the latest durable graph state.
    #
    # This contains recovery_strategy, score, reason,
    # and whether the real LLM selected it.
    # ---------------------------------------------------------

    run = store.get_run(
        row["run_id"]
    )

    if run is None:
        raise ValueError(
            f"Run not found: {row['run_id']}"
        )

    state = run["state"]

    strategy = state.get(
        "recovery_strategy"
    )

    score = state.get(
        "recovery_score"
    )

    reason = state.get(
        "recovery_reason"
    )

    llm_used = state.get(
        "recovery_llm_used",
        False,
    )

    if not strategy:
        raise ValueError(
            "No persisted recovery strategy exists "
            f"for failure {failure_id}."
        )

    return {
        "failure_id": failure_id,
        "run_id": row["run_id"],
        "strategy": strategy,
        "score": score,
        "reason": reason,
        "llm_used": llm_used,
        "failure_status": row["status"],
        "error_type": row["error_type"],
        "error_message": row["error_message"],
    }


def _get_resolved_failure(
    store: StateStore,
    failure_id: str,
) -> tuple[str, dict[str, Any]]:
    """
    Validate the failure ticket and return the durable run state.
    """

    with store._connect() as conn:
        row = conn.execute(
            """
            SELECT
                run_id,
                status
            FROM failure_tickets
            WHERE failure_id = ?
            """,
            (failure_id,),
        ).fetchone()

    if row is None:
        raise ValueError(
            f"Failure ticket not found: {failure_id}"
        )

    if row["status"] != "RESOLVED":
        raise ValueError(
            "Failure ticket must be RESOLVED before resume"
        )

    run = store.get_run(
        row["run_id"]
    )

    if run is None:
        raise ValueError(
            f"Run not found: {row['run_id']}"
        )

    return (
        row["run_id"],
        run["state"],
    )


def resume_after_failure(
    failure_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Resume from the durable checkpoint after admin resolution.

    The persisted LATS decision is reused.
    No new LLM reasoning is performed here.
    """

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    run_id, state = _get_resolved_failure(
        store,
        failure_id,
    )

    checkpoint = runner.recover(
        run_id
    )

    state = checkpoint["state"]

    strategy = state.get(
        "recovery_strategy"
    )

    if not strategy:
        raise ValueError(
            "Cannot resume because no recovery strategy "
            "is persisted in the checkpoint."
        )

    state["status"] = "RUNNING"

    state["current_state"] = (
        "RECOVERY_RESUME"
    )

    state["recovery_resumed_with_strategy"] = (
        strategy
    )

    state["recovered_from_checkpoint"] = (
        checkpoint["checkpoint_id"]
    )

    runner.transition(
        run_id,
        "RECOVERY_RESUME",
        state,
    )

    return run_id


async def resume_with_mcp_recovery(
    failure_id: str,
    mcp_client: Any,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Resume the failed graph using the already-persisted LATS
    strategy, then execute a constrained MCP verification.

    Flow:

        FAILED
          |
        admin resolves
          |
        RECOVERY_RESUME
          |
        RECOVERY_STRATEGY_RESTORED
          |
        CONSTRAINED_REACT
          |
        VERIFY_RECOVERY
          |
        DONE
    """

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    run_id, state = _get_resolved_failure(
        store,
        failure_id,
    )

    checkpoint = runner.recover(
        run_id
    )

    state = checkpoint["state"]

    # ---------------------------------------------------------
    # Use the LATS strategy already stored in the checkpoint.
    # ---------------------------------------------------------

    recovery_strategy = state.get(
        "recovery_strategy"
    )

    if not recovery_strategy:
        raise ValueError(
            "No persisted recovery strategy exists "
            f"for failure {failure_id}."
        )

    state["status"] = "RUNNING"

    state["current_state"] = (
        "RECOVERY_RESUME"
    )

    state["recovered_from_checkpoint"] = (
        checkpoint["checkpoint_id"]
    )

    state["recovery_resumed_with_strategy"] = (
        recovery_strategy
    )

    # No new LATS / LLM call here.
    runner.transition(
        run_id,
        "RECOVERY_RESUME",
        state,
    )

    # ---------------------------------------------------------
    # Explicit checkpoint showing the persisted strategy was
    # restored after the admin's decision.
    # ---------------------------------------------------------

    runner.transition(
        run_id,
        "RECOVERY_STRATEGY_RESTORED",
        state,
    )

    # ---------------------------------------------------------
    # Constrained ReAct
    # ---------------------------------------------------------

    adapter = MCPToolAdapter(
        mcp_client,
        allowed_tools={
            "get_ticket",
        },
    )

    react = ConstrainedMCPReAct(
        adapter
    )

    ticket_id = state.get(
        "ticket_id"
    )

    if ticket_id is None:
        raise ValueError(
            "Recovery state has no ticket_id."
        )

    react_plan = [
        {
            "thought": (
                "Verify the current ticket state through "
                "the existing MCP server before completing recovery."
            ),
            "action": "get_ticket",
            "arguments": {
                "ticket_id": int(
                    ticket_id
                ),
            },
        }
    ]

    react_result = await react.execute(
        react_plan
    )

    state["recovery_trace"] = (
        react_result.get(
            "steps",
            [],
        )
    )

    state["recovery_result"] = (
        react_result
    )

    if not react_result["success"]:

        failure = RuntimeError(
            react_result.get(
                "error",
                "Recovery ReAct failed.",
            )
        )

        new_failure_id = runner.fail(
            run_id,
            ticket_id,
            "RECOVERY_REACT",
            failure,
            state,
        )

        state["failure_id"] = (
            new_failure_id
        )

        state["status"] = "FAILED"

        state["current_state"] = (
            "RECOVERY_REACT_FAILED"
        )

        runner.transition(
            run_id,
            "RECOVERY_REACT_FAILED",
            state,
            run_status="FAILED",
        )

        return (
            f"FAILED:{new_failure_id}"
        )

    # ---------------------------------------------------------
    # Verify recovery
    # ---------------------------------------------------------

    state["status"] = "RECOVERED"

    state["current_state"] = (
        "VERIFY_RECOVERY"
    )

    runner.transition(
        run_id,
        "VERIFY_RECOVERY",
        state,
    )

    # ---------------------------------------------------------
    # Complete
    # ---------------------------------------------------------

    state["status"] = "COMPLETED"

    state["current_state"] = "DONE"

    runner.transition(
        run_id,
        "DONE",
        state,
        run_status="COMPLETED",
    )

    return run_id