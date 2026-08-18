from __future__ import annotations

from typing import Any

from .llm_reasoning import (
    generate_react_plan,
)
from .mcp_adapter import (
    ConstrainedMCPReAct,
    MCPToolAdapter,
)


def build_customer_validation_plan(
    ticket_id: int,
    *,
    context: str = "",
) -> dict[str, Any]:
    """
    Generate a constrained ReAct plan.

    In real mode this uses the existing Groq model.
    In test mode it falls back to a deterministic plan.
    """

    result = generate_react_plan(
        context=(
            f"Ticket ID: {ticket_id}\n"
            f"{context}"
        ),
        allowed_tools=[
            "get_ticket",
        ],
    )

    plan = result["plan"]

    actions = []

    for item in plan.actions:
        arguments = dict(
            item.arguments
        )

        # The ticket ID is known from durable state.
        # Never trust the model to invent/override it.
        if item.action == "get_ticket":
            arguments["ticket_id"] = ticket_id

        actions.append(
            {
                "thought": item.thought,
                "action": item.action,
                "arguments": arguments,
            }
        )

    return {
        "llm_used": result["llm_used"],
        "actions": actions,
    }


async def run_customer_validation(
    mcp_client: Any,
    ticket_id: int,
    *,
    context: str = "",
) -> dict[str, Any]:
    """
    Execute the generated plan through the constrained MCP layer.
    """

    adapter = MCPToolAdapter(
        mcp_client,
        allowed_tools={
            "get_ticket",
        },
    )

    react = ConstrainedMCPReAct(
        adapter
    )

    plan = build_customer_validation_plan(
        ticket_id,
        context=context,
    )

    result = await react.execute(
        plan["actions"]
    )

    result["llm_used"] = plan["llm_used"]

    return result