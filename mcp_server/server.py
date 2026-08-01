from fastmcp import FastMCP

import tools

from rag.knowledge import search_knowledge_base


mcp = FastMCP("Coderift Support MCP")


# ==========================
# Ticket Tools
# ==========================

@mcp.tool()
def get_ticket(ticket_id: int):
    """
    Retrieve a ticket by its ID.
    """
    return tools.get_ticket(ticket_id)


@mcp.tool()
def search_open_tickets():
    """
    Return all open tickets.
    """
    return tools.search_open_tickets()


@mcp.tool()
def search_by_team(team_name: str):
    """
    Return tickets assigned to a team.
    """
    return tools.search_by_team(team_name)


@mcp.tool()
def update_ticket_status(ticket_id: int, status: str):
    """
    Update ticket status.
    """
    return tools.update_ticket_status(ticket_id, status)


# ==========================
# RAG Tool
# ==========================

@mcp.tool()
def search_knowledge_base_tool(query: str, top_k: int = 3):
    """
    Search company policies using BM25 keyword search.
    """
    results = search_knowledge_base(query, top_k)

    if not results:
        return {
            "success": False,
            "message": "No matching policy was found."
        }

    return {
        "success": True,
        "count": len(results),
        "results": [
            {
                "document": r["metadata"]["document"],
                "content": r["payload"]
            }
            for r in results
        ]
    }


if __name__ == "__main__":
    mcp.run()