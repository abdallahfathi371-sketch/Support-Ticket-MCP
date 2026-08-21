from __future__ import annotations

from typing import Any

from .llm_reasoning import (
    generate_react_plan,
    use_real_llm,
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


def build_sla_remediation_plan(
    ticket_id: int,
    *,
    strategy: str,
    proposed_credit_usd: float = 0.0,
    context: str = "",
) -> dict[str, Any]:
    """
    Constrained ReAct plan for Graph #2 (SLA Breach Escalation).

    Whitelist is intentionally narrow: inspect the ticket, then
    update status when the chosen strategy requires it.
    """

    allowed = [
        "get_ticket",
        "update_ticket_status",
    ]

    result = generate_react_plan(
        context=(
            f"Ticket ID: {ticket_id}\n"
            f"Remediation strategy: {strategy}\n"
            f"Proposed goodwill credit USD: {proposed_credit_usd}\n"
            f"{context}"
        ),
        allowed_tools=allowed,
    )

    plan = result["plan"]
    actions: list[dict[str, Any]] = []

    for item in plan.actions:
        arguments = dict(item.arguments)

        if item.action == "get_ticket":
            arguments["ticket_id"] = ticket_id

        if item.action == "update_ticket_status":
            arguments["ticket_id"] = ticket_id
            # Never invent Closed from the model alone.
            status = str(
                arguments.get("status", "Pending")
            )
            if status not in {"Open", "Pending"}:
                status = "Pending"
            arguments["status"] = status

        actions.append(
            {
                "thought": item.thought,
                "action": item.action,
                "arguments": arguments,
            }
        )

    # Deterministic minimum plan when the model omitted get_ticket.
    if not use_real_llm() or not any(
        action["action"] == "get_ticket"
        for action in actions
    ):
        actions = [
            {
                "thought": (
                    "Inspect the breached ticket before applying "
                    "any remediation."
                ),
                "action": "get_ticket",
                "arguments": {
                    "ticket_id": ticket_id,
                },
            },
            {
                "thought": (
                    f"Apply strategy '{strategy}' by moving the "
                    "ticket to Pending while the customer reviews "
                    "the goodwill offer."
                ),
                "action": "update_ticket_status",
                "arguments": {
                    "ticket_id": ticket_id,
                    "status": "Pending",
                },
            },
        ]

    return {
        "llm_used": result["llm_used"],
        "actions": actions,
    }


async def run_sla_remediation(
    mcp_client: Any,
    *,
    ticket_id: int,
    strategy: str,
    proposed_credit_usd: float = 0.0,
    context: str = "",
) -> dict[str, Any]:
    """
    Execute Graph #2 remediation through constrained MCP tools only.
    """

    adapter = MCPToolAdapter(
        mcp_client,
        allowed_tools={
            "get_ticket",
            "update_ticket_status",
        },
    )

    react = ConstrainedMCPReAct(adapter)

    plan = build_sla_remediation_plan(
        ticket_id,
        strategy=strategy,
        proposed_credit_usd=proposed_credit_usd,
        context=context,
    )

    result = await react.execute(plan["actions"])
    result["llm_used"] = plan["llm_used"]
    return result