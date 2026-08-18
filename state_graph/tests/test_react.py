import pytest

from state_graph.common.mcp_adapter import (
    MCPToolAdapter,
    ConstrainedMCPReAct,
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


@pytest.mark.asyncio
async def test_allowed_mcp_tool_executes():
    client = FakeMCPClient()

    adapter = MCPToolAdapter(
        client,
        allowed_tools={"get_ticket"},
    )

    react = ConstrainedMCPReAct(
        adapter
    )

    result = await react.execute(
        [
            {
                "thought": "Retrieve ticket",
                "action": "get_ticket",
                "arguments": {
                    "ticket_id": 1,
                },
            }
        ]
    )

    assert result["success"] is True
    assert result["steps"][0]["action"] == "get_ticket"


@pytest.mark.asyncio
async def test_disallowed_tool_is_blocked():
    client = FakeMCPClient()

    adapter = MCPToolAdapter(
        client,
        allowed_tools={"get_ticket"},
    )

    react = ConstrainedMCPReAct(
        adapter
    )

    result = await react.execute(
        [
            {
                "thought": "Try unauthorized tool",
                "action": "delete_ticket",
                "arguments": {
                    "ticket_id": 1,
                },
            }
        ]
    )

    assert result["success"] is False
    assert "not allowed" in result["error"]