from fastmcp import Client


class MCPClient:

    def __init__(self):

        self.client = Client(
            "http://127.0.0.1:8000/mcp"
        )


    async def connect(self):

        return True



    async def check_capabilities(self):

        async with self.client:

            return {
                "message": "Connected successfully"
            }



    async def get_dashboard(self):

        async with self.client:

            result = await self.client.call_tool(
                "dashboard_tool",
                {
                    "employee_id": 1
                }
            )

            return result.data



    async def get_ticket(
        self,
        ticket_id: int
    ):

        async with self.client:

            result = await self.client.call_tool(
                "get_ticket",
                {
                    "employee_id": 1,
                    "ticket_id": ticket_id
                }
            )

            return result.data



    async def search_open_tickets(self):

        async with self.client:

            result = await self.client.call_tool(
                "search_open_tickets",
                {
                    "employee_id": 1
                }
            )

            return result.data



    async def search_by_team(
        self,
        team_name: str
    ):

        async with self.client:

            result = await self.client.call_tool(
                "search_by_team",
                {
                    "employee_id": 1,
                    "team_name": team_name
                }
            )

            return result.data



    async def update_ticket_status(
        self,
        ticket_id: int,
        status: str,
        approved: bool = False,
    ):

        async with self.client:

            result = await self.client.call_tool(
                "update_ticket_status",
                {
                    "employee_id": 1,
                    "ticket_id": ticket_id,
                    "status": status,
                    "approved": approved,
                }
            )

            return result.data



    async def generate_report(self):

        async with self.client:

            result = await self.client.call_tool(
                "generate_report",
                {
                    "employee_id": 1
                }
            )

            return result.data



    async def execute_tool(
        self,
        tool_name: str,
        args: dict
    ):

        async with self.client:

            result = await self.client.call_tool(
                tool_name,
                args
            )

            return result.data



    async def list_tools(self):

        async with self.client:

            return await self.client.list_tools()



    async def list_prompts(self):

        async with self.client:

            return await self.client.list_prompts()