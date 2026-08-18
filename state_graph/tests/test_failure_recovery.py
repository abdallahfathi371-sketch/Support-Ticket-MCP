import pytest

from state_graph.common.store import StateStore
from state_graph.graphs.failure_recovery import (
    start_failure_recovery,
    execute_action,
    resume_after_failure,
)


def test_failure_is_persisted(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, state = start_failure_recovery(
        ticket_id=1,
        db_path=str(db_path),
    )

    assert run_id
    assert state == "EXECUTE_ACTION"

    def failing_action():
        raise RuntimeError("Simulated failure")

    result = execute_action(
        run_id,
        failing_action,
        db_path=str(db_path),
    )

    assert result.startswith("FAILED:")

    failure_id = result.split(":", 1)[1]

    store = StateStore(db_path)

    failures = store.list_failure_tickets(
        status="OPEN"
    )

    failure = next(
        item
        for item in failures
        if item["failure_id"] == failure_id
    )

    assert failure["status"] == "OPEN"
    assert failure["error_type"] == "RuntimeError"
    assert failure["node_name"] == "EXECUTE_ACTION"


def test_unresolved_failure_cannot_resume(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, _ = start_failure_recovery(
        ticket_id=1,
        db_path=str(db_path),
    )

    def failing_action():
        raise RuntimeError("Still broken")

    result = execute_action(
        run_id,
        failing_action,
        db_path=str(db_path),
    )

    failure_id = result.split(":", 1)[1]

    with pytest.raises(ValueError, match="RESOLVED"):
        resume_after_failure(
            failure_id,
            db_path=str(db_path),
        )


def test_resolved_failure_can_resume(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, _ = start_failure_recovery(
        ticket_id=1,
        db_path=str(db_path),
    )

    def failing_action():
        raise RuntimeError("Temporary failure")

    result = execute_action(
        run_id,
        failing_action,
        db_path=str(db_path),
    )

    failure_id = result.split(":", 1)[1]

    store = StateStore(db_path)

    store.resolve_failure(
        failure_id=failure_id,
        resolution="Administrator fixed the issue",
        admin_id="admin-test",
    )

    resumed_run_id = resume_after_failure(
        failure_id,
        db_path=str(db_path),
    )

    assert resumed_run_id == run_id

    checkpoint = store.latest_checkpoint(run_id)

    assert checkpoint["state_name"] == "RECOVERY_RESUME"

    assert (
        checkpoint["state"]["recovered_from_checkpoint"]
        == checkpoint["state"]["recovered_from_checkpoint"]
    )