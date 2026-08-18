from state_graph.common.store import StateStore
from state_graph.graphs.customer_followup import (
    start_customer_followup,
    submit_customer_reply,
    resolve_customer_followup,
)


def test_customer_followup_reaches_waiting_customer(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, state = start_customer_followup(
        ticket_id=1,
        reason="Need more information",
        db_path=str(db_path),
    )

    assert run_id
    assert state == "WAITING_FOR_CUSTOMER"

    store = StateStore(db_path)

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint is not None
    assert checkpoint["state_name"] == "WAITING_FOR_CUSTOMER"


def test_customer_reply_creates_hitl(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, _ = start_customer_followup(
        ticket_id=1,
        reason="Need reproduction steps",
        db_path=str(db_path),
    )

    result = submit_customer_reply(
        run_id,
        "Error occurs after clicking Export. Code E-104.",
        db_path=str(db_path),
    )

    assert result.startswith("WAITING_HITL:")

    task_id = result.split(":", 1)[1]

    store = StateStore(db_path)

    task = store.get_hitl_task(task_id)

    assert task is not None
    assert task["status"] == "PENDING"
    assert task["run_id"] == run_id


def test_customer_followup_admin_approval_resolves(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, _ = start_customer_followup(
        ticket_id=1,
        reason="Need more information",
        db_path=str(db_path),
    )

    result = submit_customer_reply(
        run_id,
        "The error occurs after Export.",
        db_path=str(db_path),
    )

    task_id = result.split(":", 1)[1]

    final_state = resolve_customer_followup(
        task_id=task_id,
        decision="approve",
        admin_id="admin-test",
        db_path=str(db_path),
    )

    assert final_state == "RESOLVE"

    store = StateStore(db_path)

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint["state_name"] == "RESOLVE"
    assert checkpoint["state"]["status"] == "RESOLVED"


def test_customer_followup_admin_rejection_returns_to_customer(
    tmp_path,
):
    db_path = tmp_path / "test.db"

    run_id, _ = start_customer_followup(
        ticket_id=1,
        reason="Need more information",
        db_path=str(db_path),
    )

    result = submit_customer_reply(
        run_id,
        "Some incomplete information.",
        db_path=str(db_path),
    )

    task_id = result.split(":", 1)[1]

    final_state = resolve_customer_followup(
        task_id=task_id,
        decision="reject",
        admin_id="admin-test",
        db_path=str(db_path),
    )

    assert final_state == "WAITING_FOR_CUSTOMER"

    store = StateStore(db_path)

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint["state_name"] == "WAITING_FOR_CUSTOMER"