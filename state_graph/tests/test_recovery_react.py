import pytest

from state_graph.common.store import StateStore
from state_graph.graphs.failure_recovery import (
    start_failure_recovery,
    execute_action,
    get_recovery_plan,
    resume_with_mcp_recovery,
)


class FakeMCPClient:
    async def get_ticket(self, ticket_id: int):
        return {
            "success": True,
            "ticket": {
                "ticket_id": ticket_id,
                "status": "Open",
            },
        }


def test_lats_selects_recovery_strategy(tmp_path):
    db_path = tmp_path / "test.db"

    run_id, _ = start_failure_recovery(
        ticket_id=1,
        db_path=str(db_path),
    )

    def failing_action():
        raise RuntimeError(
            "Simulated MCP failure"
        )

    result = execute_action(
        run_id,
        failing_action,
        db_path=str(db_path),
    )

    failure_id = result.split(":", 1)[1]

    plan = get_recovery_plan(
        failure_id,
        db_path=str(db_path),
    )

    assert plan["strategy"] == "escalate_to_admin"
    assert plan["score"] > 0
    assert plan["failure_status"] == "OPEN"


@pytest.mark.asyncio
async def test_lats_plus_constrained_react_recovers(
    tmp_path,
):
    db_path = tmp_path / "test.db"

    run_id, _ = start_failure_recovery(
        ticket_id=1,
        db_path=str(db_path),
    )

    def failing_action():
        raise RuntimeError(
            "Simulated recoverable failure"
        )

    result = execute_action(
        run_id,
        failing_action,
        db_path=str(db_path),
    )

    failure_id = result.split(":", 1)[1]

    store = StateStore(db_path)

    store.resolve_failure(
        failure_id=failure_id,
        resolution="Administrator approved recovery.",
        admin_id="admin-test",
    )

    fake_client = FakeMCPClient()

    recovered_run = await resume_with_mcp_recovery(
        failure_id,
        fake_client,
        db_path=str(db_path),
    )

    assert recovered_run == run_id

    checkpoint = store.latest_checkpoint(
        run_id
    )

    assert checkpoint is not None
    assert checkpoint["state_name"] == "DONE"
    assert (
        checkpoint["state"]["status"]
        == "COMPLETED"
    )

    trace = checkpoint["state"]["recovery_trace"]

    assert len(trace) == 1
    assert trace[0]["action"] == "get_ticket"