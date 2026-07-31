import asyncio
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


SERVER_PATH = (
    Path(__file__).parent.parent
    / "mcp_server"
    / "server.py"
)


transport = StdioTransport(
    command=sys.executable,
    args=[
        "-u",
        str(SERVER_PATH)
    ]
)


class MCPClient:

    def __init__(self):
        self.client = Client(transport)


    async def get_ticket(self, ticket_id):

        async with self.client:
            result = await self.client.call_tool(
                "get_ticket",
                {
                    "ticket_id": ticket_id
                }
            )

            return result.data


    async def search_open_tickets(self):

        async with self.client:
            result = await self.client.call_tool(
                "search_open_tickets",
                {}
            )

            return result.data


    async def search_by_team(self, team_name):

        async with self.client:
            result = await self.client.call_tool(
                "search_by_team",
                {
                    "team_name": team_name
                }
            )

            return result.data


    async def update_ticket_status(self, ticket_id, status):

        async with self.client:
            result = await self.client.call_tool(
                "update_ticket_status",
                {
                    "ticket_id": ticket_id,
                    "status": status
                }
            )

            return result.data