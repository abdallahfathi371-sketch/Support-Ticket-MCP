from __future__ import annotations

from typing import Literal


def route_method_for_instruction(instruction: str) -> Literal["MCP", "PS", "ToT", "LATS", "SelfRefine", "Reflexion"]:
    """
    Simple heuristic-based router that maps a task instruction to a planning method.

    - MCP: deterministic company-data operations that should be executed via MCP tools
    - PS: Plan-and-Solve (single deterministic plan then execute)
    - ToT: Tree-of-Thoughts for ranking / ordering problems
    - LATS: MCTS guided search for expensive-to-commit proposals (use grounded env)
    - SelfRefine: small cheap-to-redo revisions or text polishing
    - Reflexion: tasks that may require multiple trials and learning from reflections
    """

    text = instruction.lower()

    # Deterministic MCP operations
    mcp_indicators = ["open ticket", "get ticket", "search open", "search by team", "dashboard", "generate report", "update status"]
    for ind in mcp_indicators:
        if ind in text:
            return "MCP"

    # Self-Refine for short text-polishing / formatting / single-draft tasks
    if any(word in text for word in ["summarize", "format", "rephrase", "polish", "shorten", "improve"]):
        return "SelfRefine"

    # Tree-of-Thoughts for ranking / prioritization / combinatorial ordering
    if any(word in text for word in ["rank", "rank by", "priorit", "order", "which to handle first", "which ticket should"]):
        return "ToT"

    # LATS for proposals that may be validated against DB or have costly side-effects
    if any(word in text for word in ["propose", "proposal", "close", "reschedule", "reshuffle", "double-book"]):
        return "LATS"

    # Reflexion for tasks that historically require multiple attempts / learning
    if any(word in text for word in ["try again", "improve after", "retry", "reflexion", "reflect"]):
        return "Reflexion"

    # Default: Plan-and-Solve
    return "PS"
