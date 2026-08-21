from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable


class MCPToolAdapter:
    """
    Adapter around the existing agent.MCPClient.

    The state graph never calls arbitrary MCP tools directly.
    Every action must pass through this adapter and the allowed
    tool whitelist.
    """

    DEFAULT_ALLOWED_TOOLS = frozenset(
        {
            "get_ticket",
            "search_open_tickets",
            "search_by_team",
            "update_ticket_status",
            "generate_report",
            "dashboard_tool",
        }
    )

    def __init__(
        self,
        mcp_client: Any,
        allowed_tools: set[str] | None = None,
    ) -> None:
        self.mcp_client = mcp_client

        self.allowed_tools = frozenset(
            allowed_tools
            if allowed_tools is not None
            else self.DEFAULT_ALLOWED_TOOLS
        )

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools

    def list_allowed_tools(self) -> list[str]:
        return sorted(self.allowed_tools)

    async def execute(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute one whitelisted MCP operation.

        The adapter prefers explicit methods on MCPClient.
        The generic execute_tool() fallback is intentionally allowed
        only for tool names already present in the whitelist.
        """

        if not self.is_allowed(tool_name):
            return {
                "success": False,
                "tool": tool_name,
                "error": (
                    f"Tool '{tool_name}' is not allowed. "
                    f"Allowed tools: {self.list_allowed_tools()}"
                ),
            }

        try:
            method = getattr(
                self.mcp_client,
                tool_name,
                None,
            )

            # dashboard_tool exists on the MCP server but the
            # client exposes it as get_dashboard().
            if tool_name == "dashboard_tool":
                method = getattr(
                    self.mcp_client,
                    "get_dashboard",
                    None,
                )

            if method is None:
                method = getattr(
                    self.mcp_client,
                    "execute_tool",
                    None,
                )

                if method is None:
                    return {
                        "success": False,
                        "tool": tool_name,
                        "error": (
                            f"MCPClient has no method for "
                            f"'{tool_name}'."
                        ),
                    }

                result = method(
                    tool_name,
                    kwargs,
                )

            else:
                result = method(
                    **kwargs
                )

            if inspect.isawaitable(result):
                result = await result

            return {
                "success": True,
                "tool": tool_name,
                "data": result,
            }

        except Exception as exc:
            return {
                "success": False,
                "tool": tool_name,
                "error": f"{type(exc).__name__}: {exc}",
            }


class ConstrainedMCPReAct:
    """
    Small async ReAct execution layer for state graphs.

    Each action has:
        thought
        action
        arguments

    Only whitelisted MCP tools can be executed.
    """

    def __init__(
        self,
        adapter: MCPToolAdapter,
    ) -> None:
        self.adapter = adapter

    async def execute(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:

        steps: list[dict[str, Any]] = []

        for action_spec in actions:

            thought = str(
                action_spec.get(
                    "thought",
                    "",
                )
            ).strip()

            tool_name = str(
                action_spec.get(
                    "action",
                    "",
                )
            ).strip()

            arguments = action_spec.get(
                "arguments",
                {},
            )

            if not isinstance(
                arguments,
                dict,
            ):
                return {
                    "success": False,
                    "error": (
                        "ReAct action arguments "
                        "must be a dictionary."
                    ),
                    "steps": steps,
                }

            result = await self.adapter.execute(
                tool_name,
                **arguments,
            )

            step = {
                "thought": thought,
                "action": tool_name,
                "arguments": arguments,
                "observation": result,
            }

            steps.append(step)

            if not result["success"]:
                return {
                    "success": False,
                    "failed_action": tool_name,
                    "error": result["error"],
                    "steps": steps,
                }

            # Nested MCP tool payloads may report success=False
            # (elicitation, not found, authorization) without raising.
            data = result.get("data")
            if isinstance(data, dict) and data.get("success") is False:
                return {
                    "success": False,
                    "failed_action": tool_name,
                    "error": str(
                        data.get("message")
                        or data.get("error")
                        or "MCP tool reported success=False"
                    ),
                    "steps": steps,
                    "elicitation": data.get("elicitation"),
                }

        return {
            "success": True,
            "steps": steps,
        }