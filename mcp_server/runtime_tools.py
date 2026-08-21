from __future__ import annotations

from typing import Iterable


DEFAULT_TOOL_NAMES = {
    "support_ticket_mcp": [
        "get_ticket",
        "search_open_tickets",
        "search_by_team",
        "update_ticket_status",
        "dashboard_tool",
        "generate_report",
    ],
    "memory_rag_agent": [
        "search_knowledge",
        "ingest_document",
        "list_documents",
    ],
    "planning_agent": [
        "plan_task",
        "decompose_goal",
        "self_refine",
    ],
    "state_graph_agent": [
        "start_sla_breach_escalation",
        "start_customer_followup",
        "start_failure_recovery",
        "start_claim_appeal",
    ],
}

_AGENT_TOOL_REGISTRY: dict[str, set[str]] = {
    agent: set(tools)
    for agent, tools in DEFAULT_TOOL_NAMES.items()
}


def list_tools(agent_name: str) -> list[str]:
    tools = _AGENT_TOOL_REGISTRY.get(agent_name, set())
    return sorted(tools)


def set_tool_enabled(agent_name: str, tool_name: str, enabled: bool) -> bool:
    tools = _AGENT_TOOL_REGISTRY.setdefault(agent_name, set())
    if enabled:
        tools.add(tool_name)
        return True
    tools.discard(tool_name)
    return tool_name not in tools


def add_tool(agent_name: str, tool_name: str) -> None:
    _AGENT_TOOL_REGISTRY.setdefault(agent_name, set()).add(tool_name)


def remove_tool(agent_name: str, tool_name: str) -> None:
    _AGENT_TOOL_REGISTRY.setdefault(agent_name, set()).discard(tool_name)


def list_all_agents() -> list[str]:
    return sorted(_AGENT_TOOL_REGISTRY)


def list_all_tools() -> dict[str, list[str]]:
    return {
        agent: sorted(tools)
        for agent, tools in _AGENT_TOOL_REGISTRY.items()
    }
