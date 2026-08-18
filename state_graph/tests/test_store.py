from __future__ import annotations

import sqlite3

from state_graph.common.store import StateStore


def test_create_run_and_checkpoint(tmp_path):
    db_path = tmp_path / "test.db"

    store = StateStore(db_path)

    state = {
        "ticket_id": 1,
        "status": "RUNNING",
    }

    run_id = store.create_run(
        graph_name="test_graph",
        ticket_id=1,
        state=state,
        current_state="START",
    )

    assert run_id

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint is not None
    assert checkpoint["state_name"] == "START"
    assert checkpoint["state"]["ticket_id"] == 1


def test_checkpoint_is_persisted(tmp_path):
    db_path = tmp_path / "test.db"

    store = StateStore(db_path)

    run_id = store.create_run(
        graph_name="test_graph",
        ticket_id=1,
        state={"value": 1},
        current_state="START",
    )

    store.checkpoint(
        run_id,
        "NEXT_STATE",
        {"value": 2},
    )

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint["state_name"] == "NEXT_STATE"
    assert checkpoint["state"]["value"] == 2


def test_hitl_task_lifecycle(tmp_path):
    db_path = tmp_path / "test.db"

    store = StateStore(db_path)

    run_id = store.create_run(
        graph_name="test_graph",
        ticket_id=1,
        state={"status": "RUNNING"},
        current_state="START",
    )

    task_id = store.create_hitl_task(
        run_id=run_id,
        ticket_id=1,
        reason="Admin approval required",
        state={"status": "WAITING_HITL"},
    )

    task = store.get_hitl_task(task_id)

    assert task is not None
    assert task["status"] == "PENDING"
    assert task["ticket_id"] == 1

    pending = store.list_pending_hitl()

    assert any(
        item["task_id"] == task_id
        for item in pending
    )

    store.resolve_hitl_task(
        task_id=task_id,
        decision="approve",
        admin_id="admin-test",
    )

    resolved = store.get_hitl_task(task_id)

    assert resolved["status"] == "RESOLVED"
    assert resolved["decision"] == "approve"
    assert resolved["admin_id"] == "admin-test"


def test_failure_ticket_lifecycle(tmp_path):
    db_path = tmp_path / "test.db"

    store = StateStore(db_path)

    run_id = store.create_run(
        graph_name="test_graph",
        ticket_id=1,
        state={"status": "RUNNING"},
        current_state="EXECUTE_ACTION",
    )

    failure_id = store.create_failure_ticket(
        run_id=run_id,
        ticket_id=1,
        node_name="EXECUTE_ACTION",
        exc=RuntimeError("Test failure"),
        state={"status": "RUNNING"},
    )

    failures = store.list_failure_tickets()

    failure = next(
        item
        for item in failures
        if item["failure_id"] == failure_id
    )

    assert failure["status"] == "OPEN"
    assert failure["node_name"] == "EXECUTE_ACTION"
    assert failure["error_type"] == "RuntimeError"

    store.resolve_failure(
        failure_id=failure_id,
        resolution="Fixed by administrator",
        admin_id="admin-test",
    )

    resolved_failures = store.list_failure_tickets(
        status="RESOLVED"
    )

    resolved = next(
        item
        for item in resolved_failures
        if item["failure_id"] == failure_id
    )

    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None