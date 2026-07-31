from fastmcp import FastMCP
import tools

mcp = FastMCP("Coderift Support MCP")


@mcp.tool
def get_ticket(ticket_id: int):
    return tools.get_ticket(ticket_id)


@mcp.tool
def search_open_tickets():
    return tools.search_open_tickets()


@mcp.tool
def search_by_team(team_name: str):
    return tools.search_by_team(team_name)


@mcp.tool
def update_ticket_status(ticket_id: int, status: str):
    return tools.update_ticket_status(ticket_id, status)


if __name__ == "__main__":
    mcp.run()