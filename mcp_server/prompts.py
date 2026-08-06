from .app import mcp



@mcp.prompt()
def ticket_analysis_prompt(
    ticket_id: int
):
    """
    Generate a reusable prompt
    for analyzing a support ticket.
    """

    return f"""

Analyze support ticket {ticket_id}.

Provide:

1. Problem summary
2. Possible root cause
3. Recommended action
4. Required team

Use only information retrieved
from MCP tools.

"""