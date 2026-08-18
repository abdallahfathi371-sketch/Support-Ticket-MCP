from state_graph.common.store import StateStore

from state_graph.graphs.customer_followup import (
    start_customer_followup,
    submit_customer_reply,
    resolve_customer_followup,
)

from state_graph.graphs.failure_recovery import (
    start_failure_recovery,
    execute_action,
    get_recovery_plan,
    resume_after_failure,
)


DB_PATH = "db/support.db"


def demo_followup() -> None:

    print("=== Customer Follow-up ===")

    run_id, state = start_customer_followup(
        ticket_id=1,
        reason="Need reproduction steps and error message",
        db_path=DB_PATH,
    )

    print("FOLLOW-UP RUN:", run_id)
    print("STATE:", state)

    result = submit_customer_reply(
        run_id,
        "The error appears after clicking Export. Code: E-104.",
        db_path=DB_PATH,
    )

    print("AFTER CUSTOMER REPLY:", result)

    if not result.startswith(
        "WAITING_HITL:"
    ):
        print(
            "No HITL task was created."
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

    store = StateStore(DB_PATH)

    pending = store.list_pending_hitl()

    print(
        "PENDING HITL:",
        pending,
    )

    checkpoint = store.latest_checkpoint(
        run_id
    )

    if checkpoint is not None:

        state_data = checkpoint["state"]

        print(
            "POLICIES RETRIEVED:"
        )

        for item in state_data.get(
            "policy_evidence",
            [],
        ):

            print(
                f"  - {item['name']}: "
                f"{'FOUND' if item['found'] else 'MISSING'}"
            )

    final_state = (
        resolve_customer_followup(
            task_id=task_id,
            decision="approve",
            admin_id="admin-demo",
            db_path=DB_PATH,
        )
    )

    print(
        "AFTER ADMIN DECISION:",
        final_state,
    )


def demo_failure_recovery() -> None:

    print()
    print("=== Failure Recovery ===")

    run_id, state = (
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
        "STATE:",
        state,
    )

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

    failure_id = result.split(
        ":",
        1,
    )[1]

    print(
        "FAILURE ID:",
        failure_id,
    )

    store = StateStore(DB_PATH)

    failure = next(
        item
        for item in store.list_failure_tickets()
        if item["failure_id"] == failure_id
    )

    print(
        "FAILURE TICKET:",
        failure["status"],
    )

    recovery_plan = get_recovery_plan(
        failure_id,
        db_path=DB_PATH,
    )

    print(
        "RECOVERY STRATEGY:"
    )

    print(
        "  strategy:",
        recovery_plan["strategy"],
    )

    print(
        "  score:",
        recovery_plan["score"],
    )

    print(
        "  reason:",
        recovery_plan["reason"],
    )

    store.resolve_failure(
        failure_id=failure_id,
        resolution=(
            "Administrator reviewed the failure "
            "and approved recovery."
        ),
        admin_id="admin-demo",
    )

    resolved = next(
        item
        for item in store.list_failure_tickets()
        if item["failure_id"] == failure_id
    )

    print(
        "AFTER ADMIN RESOLUTION:",
        resolved["status"],
    )

    resumed_run = resume_after_failure(
        failure_id,
        db_path=DB_PATH,
    )

    print(
        "RESUMED RUN:",
        resumed_run,
    )


def main() -> None:

    demo_followup()

    print()

    demo_failure_recovery()


if __name__ == "__main__":
    main()