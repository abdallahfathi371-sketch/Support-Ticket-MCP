from __future__ import annotations

import asyncio

from agent.client import MCPClient

from state_graph.common.store import StateStore

from state_graph.graphs.customer_followup import (
    start_customer_followup,
    submit_customer_reply_with_mcp,
    resolve_customer_followup,
)

from state_graph.graphs.failure_recovery import (
    start_failure_recovery,
    execute_action,
    get_recovery_plan,
    resume_with_mcp_recovery,
)


DB_PATH = "db/support.db"


async def demo_live_customer_followup() -> None:
    print("=" * 70)
    print("LIVE CUSTOMER FOLLOW-UP")
    print("=" * 70)

    # ---------------------------------------------------------
    # Real MCP client
    # ---------------------------------------------------------

    mcp_client = MCPClient()

    await mcp_client.connect()

    print("MCP CLIENT: CONNECTED")

    # ---------------------------------------------------------
    # Start durable graph
    # ---------------------------------------------------------

    run_id, initial_state = start_customer_followup(
        ticket_id=1,
        reason=(
            "Customer replied with reproduction "
            "information for an export error."
        ),
        db_path=DB_PATH,
    )

    print("RUN ID:", run_id)
    print("INITIAL STATE:", initial_state)

    # ---------------------------------------------------------
    # External customer reply
    #
    # This path performs:
    #
    #   Grounding
    #       ↓
    #   Real LLM ReAct
    #       ↓
    #   Constrained MCP tool
    #       ↓
    #   HITL
    # ---------------------------------------------------------

    result = await submit_customer_reply_with_mcp(
        run_id,
        (
            "The error appears after clicking Export. "
            "Code: E-104."
        ),
        mcp_client,
        db_path=DB_PATH,
    )

    print(
        "AFTER CUSTOMER REPLY:",
        result,
    )

    # ---------------------------------------------------------
    # HITL task
    # ---------------------------------------------------------

    if not result.startswith(
        "WAITING_HITL:"
    ):
        print(
            "ERROR: Customer Follow-up "
            "did not reach HITL."
        )
        return

    task_id = result.split(
        ":",
        1,
    )[1]

    print(
        "HITL TASK:",
        task_id,
    )

    # ---------------------------------------------------------
    # Inspect durable state
    # ---------------------------------------------------------

    store = StateStore(DB_PATH)

    checkpoint = store.latest_checkpoint(
        run_id
    )

    if checkpoint is not None:

        state = checkpoint[
            "state"
        ]

        print(
            "CHECKPOINT STATE:",
            checkpoint["state_name"],
        )

        print(
            "REACT LLM USED:",
            state.get(
                "react_llm_used"
            ),
        )

        print(
            "REACT SUCCESS:",
            state.get(
                "react_success"
            ),
        )

        print(
            "GROUNDING SUPPORTED:",
            state.get(
                "grounding_supported"
            ),
        )

        print(
            "POLICIES CHECKED:",
            state.get(
                "policies_checked"
            ),
        )

        print(
            "REACT TRACE:",
            state.get(
                "react_trace"
            ),
        )

    # ---------------------------------------------------------
    # Admin decision
    #
    # For the final platform this will be triggered by
    # the admin UI, not by console code.
    # ---------------------------------------------------------

    decision_result = (
        resolve_customer_followup(
            task_id=task_id,
            decision="approve",
            admin_id="admin-demo",
            db_path=DB_PATH,
        )
    )

    print(
        "AFTER ADMIN DECISION:",
        decision_result,
    )

    final_checkpoint = (
        store.latest_checkpoint(
            run_id
        )
    )

    if final_checkpoint is not None:

        print(
            "FINAL CUSTOMER GRAPH STATE:",
            final_checkpoint["state_name"],
        )

        print(
            "FINAL CUSTOMER GRAPH STATUS:",
            final_checkpoint["state"].get(
                "status"
            ),
        )


async def demo_live_failure_recovery() -> None:
    print()
    print("=" * 70)
    print("LIVE FAILURE RECOVERY")
    print("=" * 70)

    # ---------------------------------------------------------
    # Start recovery graph
    # ---------------------------------------------------------

    run_id, initial_state = (
        start_failure_recovery(
            ticket_id=1,
            db_path=DB_PATH,
        )
    )

    print(
        "RECOVERY RUN:",
        run_id,
    )

    print(
        "INITIAL STATE:",
        initial_state,
    )

    # ---------------------------------------------------------
    # Deliberate unexpected failure
    #
    # This creates a real failure ticket.
    # ---------------------------------------------------------

    def failing_action():
        raise RuntimeError(
            "Simulated MCP/tool execution failure"
        )

    result = execute_action(
        run_id,
        failing_action,
        db_path=DB_PATH,
    )

    print(
        "AFTER FAILURE:",
        result,
    )

    if not result.startswith(
        "FAILED:"
    ):
        print(
            "ERROR: Failure ticket was not created."
        )
        return

    failure_id = result.split(
        ":",
        1,
    )[1]

    print(
        "FAILURE ID:",
        failure_id,
    )

    # ---------------------------------------------------------
    # LATS recovery plan
    # ---------------------------------------------------------

    recovery_plan = get_recovery_plan(
        failure_id,
        db_path=DB_PATH,
    )

    print(
        "LATS STRATEGY:",
        recovery_plan[
            "strategy"
        ],
    )

    print(
        "LATS SCORE:",
        recovery_plan[
            "score"
        ],
    )

    print(
        "LATS REASON:",
        recovery_plan[
            "reason"
        ],
    )

    print(
        "LATS LLM USED:",
        recovery_plan.get(
            "llm_used"
        ),
    )

    # ---------------------------------------------------------
    # Resolve failure as admin
    #
    # In the real platform this will happen through the
    # admin UI.
    # ---------------------------------------------------------

    store = StateStore(DB_PATH)

    store.resolve_failure(
        failure_id=failure_id,
        resolution=(
            "Administrator reviewed the failed MCP action "
            "and approved recovery."
        ),
        admin_id="admin-demo",
    )

    print(
        "FAILURE STATUS: RESOLVED"
    )

    # ---------------------------------------------------------
    # New MCP client representing a new process/session
    # ---------------------------------------------------------

    recovery_client = MCPClient()

    await recovery_client.connect()

    print(
        "RECOVERY MCP CLIENT: CONNECTED"
    )

    # ---------------------------------------------------------
    # Resume:
    #
    #   checkpoint
    #       ↓
    #   LATS
    #       ↓
    #   constrained ReAct
    #       ↓
    #   MCP get_ticket
    #       ↓
    #   VERIFY_RECOVERY
    #       ↓
    #   DONE
    # ---------------------------------------------------------

    recovered_run = (
        await resume_with_mcp_recovery(
            failure_id,
            recovery_client,
            db_path=DB_PATH,
        )
    )

    print(
        "RECOVERED RUN:",
        recovered_run,
    )

    checkpoint = (
        store.latest_checkpoint(
            recovered_run
        )
    )

    if checkpoint is not None:

        state = checkpoint[
            "state"
        ]

        print(
            "FINAL FAILURE GRAPH STATE:",
            checkpoint[
                "state_name"
            ],
        )

        print(
            "FINAL FAILURE GRAPH STATUS:",
            state.get(
                "status"
            ),
        )

        print(
            "RECOVERY STRATEGY:",
            state.get(
                "recovery_strategy"
            ),
        )

        print(
            "RECOVERY LLM USED:",
            state.get(
                "recovery_llm_used"
            ),
        )

        print(
            "RECOVERY TRACE:",
            state.get(
                "recovery_trace"
            ),
        )


async def main() -> None:

    await demo_live_customer_followup()

    await demo_live_failure_recovery()


if __name__ == "__main__":
    asyncio.run(main())