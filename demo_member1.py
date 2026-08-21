"""
Member 1 demo — Graph #2 SLA Breach Escalation

Shows:
1. HITL pause + admin resolve through the shared store (platform-ready)
2. Failure ticket path distinct from HITL
3. Resume from checkpoint after failure (no restart from DETECT)
4. Customer acknowledgement wait + resolve
"""

from state_graph.common.store import StateStore
from state_graph.graphs.sla_breach_escalation import (
    fail_sla_breach_node,
    resolve_sla_breach_hitl,
    resume_sla_breach_after_failure,
    start_sla_breach_escalation,
    submit_customer_acknowledgement,
)


DB_PATH = "db/support.db"


def demo_hitl_path() -> None:
    print("=== Graph #2: SLA Breach - HITL path ===")

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        issue_summary="Login API returns 500 error",
        db_path=DB_PATH,
    )

    print("RUN:", run_id)
    print("STATE:", result)

    if not result.startswith("WAITING_HITL:"):
        print("Expected HITL pause; got:", result)
        return

    task_id = result.split(":", 1)[1]
    store = StateStore(DB_PATH)

    print("HITL TASK:", task_id)
    print("PENDING HITL:", store.list_pending_hitl())

    checkpoint = store.latest_checkpoint(run_id)
    state = checkpoint["state"] if checkpoint else {}

    print("SELECTED STRATEGY:", state.get("selected_strategy"))
    print("PROPOSED CREDIT:", state.get("proposed_credit_usd"))
    print("HITL REASONS:", state.get("hitl_reason_codes"))
    print("TOT CANDIDATES:")
    for candidate in state.get("tot_candidates", []):
        print(
            f"  - {candidate['strategy']}: "
            f"score={candidate['score']:.2f} "
            f"credit=${candidate.get('proposed_credit_usd', 0):.0f}"
        )

    mid = resolve_sla_breach_hitl(
        task_id=task_id,
        decision="approve",
        admin_id="admin-member1",
        db_path=DB_PATH,
    )
    print("AFTER ADMIN APPROVE:", mid)

    final = submit_customer_acknowledgement(
        run_id,
        "accept",
        db_path=DB_PATH,
    )
    print("AFTER CUSTOMER ACK:", final)

    final_cp = store.latest_checkpoint(run_id)
    print("FINAL STATE:", final_cp["state_name"] if final_cp else None)
    print("COMPLETED STEPS:", final_cp["state"].get("completed_steps") if final_cp else None)


def demo_failure_and_resume() -> None:
    print("\n=== Graph #2: SLA Breach - Failure ticket + resume ===")

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=60.0,
        issue_summary="Login API returns 500 error",
        db_path=DB_PATH,
    )

    print("RUN:", run_id)
    print("STATE:", result)

    failure_id = fail_sla_breach_node(
        run_id,
        "EXECUTE_REMEDIATION",
        "Simulated MCP schema validation failure",
        db_path=DB_PATH,
    )

    store = StateStore(DB_PATH)
    print("FAILURE TICKET:", failure_id)
    print("OPEN FAILURES:", store.list_failure_tickets(status="OPEN"))

    before = store.latest_checkpoint(run_id)
    print(
        "COMPLETED BEFORE RESUME:",
        before["state"].get("completed_steps") if before else None,
    )

    resumed = resume_sla_breach_after_failure(
        failure_id=failure_id,
        resolution="Repaired MCP response schema; safe to continue",
        admin_id="admin-member1",
        db_path=DB_PATH,
    )

    print("AFTER RESUME:", resumed)

    after = store.latest_checkpoint(run_id)
    print(
        "COMPLETED AFTER RESUME:",
        after["state"].get("completed_steps") if after else None,
    )
    print(
        "FAILURE RESOLVED FLAG:",
        after["state"].get("failure_resolved") if after else None,
    )


if __name__ == "__main__":
    demo_hitl_path()
    demo_failure_and_resume()
