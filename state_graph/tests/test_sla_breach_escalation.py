from state_graph.common.store import StateStore
from state_graph.graphs.sla_breach_escalation import (
    fail_sla_breach_node,
    resolve_sla_breach_hitl,
    resume_sla_breach_after_failure,
    start_sla_breach_escalation,
    submit_customer_acknowledgement,
)


def test_sla_breach_no_breach_when_inside_sla(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, state = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=2.0,
        issue_summary="Login API returns 500",
        db_path=str(db_path),
    )

    assert run_id
    assert state == "NO_BREACH"

    store = StateStore(db_path)
    checkpoint = store.latest_checkpoint(run_id)
    assert checkpoint["state_name"] == "NO_BREACH"
    assert checkpoint["state"]["breach_detected"] is False


def test_sla_breach_starts_and_opens_hitl(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        issue_summary="Login API returns 500",
        db_path=str(db_path),
    )

    assert run_id
    assert result.startswith("WAITING_HITL:")

    task_id = result.split(":", 1)[1]
    store = StateStore(db_path)

    task = store.get_hitl_task(task_id)
    assert task is not None
    assert task["status"] == "PENDING"
    assert task["run_id"] == run_id

    checkpoint = store.latest_checkpoint(run_id)
    assert checkpoint["state_name"] == "WAITING_FOR_ADMIN"
    assert "DETECT_BREACH" in checkpoint["state"]["completed_steps"]
    assert "TREE_OF_THOUGHTS" in checkpoint["state"]["completed_steps"]
    assert checkpoint["state"]["hitl_required"] is True
    assert "HIGH_PRIORITY_TICKET" in checkpoint["state"]["hitl_reason_codes"]


def test_sla_breach_admin_approve_then_customer_ack(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        db_path=str(db_path),
    )

    task_id = result.split(":", 1)[1]

    mid = resolve_sla_breach_hitl(
        task_id=task_id,
        decision="approve",
        admin_id="admin-1",
        db_path=str(db_path),
    )
    assert mid == "WAITING_FOR_CUSTOMER_ACK"

    final = submit_customer_acknowledgement(
        run_id,
        "accept",
        db_path=str(db_path),
    )
    assert final == "RESOLVED"

    store = StateStore(db_path)
    checkpoint = store.latest_checkpoint(run_id)
    assert checkpoint["state_name"] == "RESOLVED"
    assert checkpoint["state"]["admin_decision"] in {
        "approve",
        "approved",
    }


def test_sla_breach_admin_reject_cycles_to_tot_hitl(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        db_path=str(db_path),
    )

    task_id = result.split(":", 1)[1]

    cycled = resolve_sla_breach_hitl(
        task_id=task_id,
        decision="reject",
        admin_id="admin-1",
        db_path=str(db_path),
    )

    assert cycled.startswith("WAITING_HITL:")

    store = StateStore(db_path)
    checkpoint = store.latest_checkpoint(run_id)
    assert checkpoint["state_name"] == "WAITING_FOR_ADMIN"
    # ToT ran again after reject (cycle), so it appears twice.
    assert checkpoint["state"]["completed_steps"].count(
        "TREE_OF_THOUGHTS"
    ) >= 2


def test_sla_breach_failure_ticket_distinct_from_hitl(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, result = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        db_path=str(db_path),
    )

    assert result.startswith("WAITING_HITL:")
    hitl_task_id = result.split(":", 1)[1]

    failure_id = fail_sla_breach_node(
        run_id,
        "TREE_OF_THOUGHTS",
        "Simulated malformed remediation schema",
        db_path=str(db_path),
    )

    store = StateStore(db_path)

    hitl = store.get_hitl_task(hitl_task_id)
    assert hitl["status"] == "PENDING"

    failures = store.list_failure_tickets(status="OPEN")
    assert len(failures) == 1
    assert failures[0]["failure_id"] == failure_id
    assert failures[0]["node_name"] == "TREE_OF_THOUGHTS"

    checkpoint = store.latest_checkpoint(run_id)
    assert checkpoint["state"]["status"] == "FAILED"
    assert "FAILED" in checkpoint["state_name"]


def test_sla_breach_resume_after_failure_keeps_completed_steps(tmp_path):
    db_path = tmp_path / "sla.db"

    run_id, _ = start_sla_breach_escalation(
        ticket_id=1,
        priority="High",
        hours_open=48.0,
        db_path=str(db_path),
    )

    failure_id = fail_sla_breach_node(
        run_id,
        "EXECUTE_REMEDIATION",
        "MCP tool schema validation failed",
        db_path=str(db_path),
    )

    store = StateStore(db_path)
    before = store.latest_checkpoint(run_id)
    completed_before = list(
        before["state"]["completed_steps"]
    )

    resumed = resume_sla_breach_after_failure(
        failure_id=failure_id,
        resolution="Fixed MCP tool response schema",
        admin_id="admin-1",
        db_path=str(db_path),
    )

    assert resumed.startswith("WAITING_HITL:")

    after = store.latest_checkpoint(run_id)
    # Prior completed work is preserved — no restart from scratch.
    for step in completed_before:
        assert step in after["state"]["completed_steps"]

    assert after["state"].get("failure_resolved") is True


def test_sla_breach_severe_breach_selects_credit_strategy(tmp_path):
    db_path = tmp_path / "sla.db"

    # High SLA target is 24h; 60h => ratio 2.5 => credit $75.
    run_id, result = start_sla_breach_escalation(
        ticket_id=2,
        priority="High",
        hours_open=60.0,
        db_path=str(db_path),
    )

    assert result.startswith("WAITING_HITL:")

    store = StateStore(db_path)
    checkpoint = store.latest_checkpoint(run_id)
    state = checkpoint["state"]

    assert state["selected_strategy"] == "request_goodwill_credit"
    assert state["proposed_credit_usd"] >= 50.0
    assert "GOODWILL_CREDIT_ABOVE_THRESHOLD" in state["hitl_reason_codes"]
