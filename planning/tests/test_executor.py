import pytest

from planning.executor import execute_task


class FakeMCPClient:
    """Fake client matching the real MCPClient interface."""

    async def search_open_tickets(self):
        return {
            "success": True,
            "count": 2,
            "tickets": [
                {
                    "ticket_id": 1,
                    "priority": "High",
                    "issue": "Login API returns 500 error",
                },
                {
                    "ticket_id": 4,
                    "priority": "High",
                    "issue": "Profile page crashes",
                },
            ],
        }

    async def get_dashboard(self):
        return {
            "success": True,
            "dashboard": {
                "total_tickets": 15,
                "open_tickets": 7,
                "pending_tickets": 4,
                "closed_tickets": 4,
            },
        }


@pytest.mark.asyncio
async def test_t1_uses_open_ticket_mcp_tool():

    client = FakeMCPClient()

    result = await execute_task(
        task_id="t1",
        instruction="Retrieve open tickets",
        context={},
        mcp_client=client,
    )

    assert "ticket_id" in result
    assert "Login API returns 500 error" in result


@pytest.mark.asyncio
async def test_t3_uses_dashboard_mcp_tool():

    client = FakeMCPClient()

    result = await execute_task(
        task_id="t3",
        instruction="Inspect support workload",
        context={},
        mcp_client=client,
    )

    assert "open_tickets" in result
    assert "pending_tickets" in result
