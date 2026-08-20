from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# Configuration
# ============================================================

def use_real_llm() -> bool:
    """
    Enable the real Groq-backed reasoning path.

    Default is False so automated tests remain deterministic.
    """

    value = os.getenv(
        "STATE_GRAPH_USE_REAL_LLM",
        "false",
    ).lower()

    return value in {
        "1",
        "true",
        "yes",
        "on",
    }


# ============================================================
# ReAct schemas
# ============================================================

class ReactAction(BaseModel):
    """
    One constrained ReAct action.
    """

    thought: str = Field(
        min_length=3
    )

    action: Literal[
        "get_ticket",
        "search_open_tickets",
        "search_by_team",
        "update_ticket_status",
        "generate_report",
        "dashboard_tool",
    ]

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


class ReactPlan(BaseModel):
    """
    Small bounded ReAct plan.
    """

    actions: list[ReactAction] = Field(
        min_length=1,
        max_length=3,
    )


# ============================================================
# LATS schemas
# ============================================================

class LATSAlternative(BaseModel):
    """
    One candidate recovery strategy.
    """

    strategy: Literal[
        "retry",
        "alternative_action",
        "escalate_to_admin",
    ]

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    rationale: str = Field(
        min_length=3
    )


class LATSPlan(BaseModel):
    """
    Bounded LATS recovery plan.

    The model may return one or more candidates.
    Safety filtering happens later in LATSRecoverySelector.
    """

    candidates: list[LATSAlternative] = Field(
        min_length=1,
        max_length=4,
    )


# ============================================================
# LLM factory
# ============================================================

def _get_llm():
    """
    Reuse the repository's existing GroqChatModel.
    """

    from planning.groq_model import GroqChatModel

    return GroqChatModel(
        use_real_llm=True
    )


# ============================================================
# ReAct validation
# ============================================================

def _validate_react_plan(
    plan: ReactPlan,
    allowed_tools: list[str],
) -> ReactPlan:
    """
    Enforce the graph's actual MCP tool whitelist.
    """

    allowed = set(
        allowed_tools
    )

    validated_actions: list[ReactAction] = []

    for action in plan.actions:

        if action.action not in allowed:
            raise ValueError(
                f"LLM proposed disallowed MCP tool: "
                f"{action.action}. "
                f"Allowed tools: {sorted(allowed)}"
            )

        validated_actions.append(
            action
        )

    if not validated_actions:
        raise ValueError(
            "LLM produced no valid constrained actions."
        )

    return ReactPlan(
        actions=validated_actions
    )


# ============================================================
# ReAct generation
# ============================================================

def generate_react_plan(
    *,
    context: str,
    allowed_tools: list[str],
) -> dict[str, Any]:
    """
    Generate a constrained ReAct plan.

    Real mode:
        Groq structured output.

    Test mode:
        deterministic fallback.

    The caller's tool whitelist is enforced after generation.
    """

    if not allowed_tools:
        raise ValueError(
            "allowed_tools cannot be empty."
        )

    # ---------------------------------------------------------
    # Deterministic mode
    # ---------------------------------------------------------

    if not use_real_llm():

        fallback_tool = (
            "get_ticket"
            if "get_ticket" in allowed_tools
            else allowed_tools[0]
        )

        plan = ReactPlan(
            actions=[
                ReactAction(
                    thought=(
                        "Use the explicitly allowed MCP tool "
                        "needed to continue the workflow."
                    ),
                    action=fallback_tool,
                    arguments={},
                )
            ]
        )

        return {
            "llm_used": False,
            "plan": _validate_react_plan(
                plan,
                allowed_tools,
            ),
        }

    # ---------------------------------------------------------
    # Real LLM mode
    # ---------------------------------------------------------

    llm = _get_llm()

    prompt = f"""
You are the constrained ReAct planner for a support-ticket state graph.

Allowed MCP tools:
{json.dumps(allowed_tools)}

Rules:
1. Use ONLY tools from the allowed list.
2. Never invent a tool.
3. Produce at most 3 actions.
4. Each action must contain:
   - thought
   - action
   - arguments
5. Do not fabricate ticket IDs.
6. Do not fabricate customer information.
7. Use only the supplied context.
8. Prefer the smallest safe action plan.
9. Never perform an action outside the allowed tools.

Context:
{context}

Return a ReAct plan.
"""

    structured = llm.with_structured_output(
        ReactPlan
    )

    result = structured.invoke(
        [
            (
                "system",
                (
                    "You are a constrained support workflow "
                    "planner. Follow tool restrictions exactly."
                ),
            ),
            (
                "human",
                prompt,
            ),
        ]
    )

    validated = _validate_react_plan(
        result,
        allowed_tools,
    )

    return {
        "llm_used": True,
        "plan": validated,
    }


# ============================================================
# LATS validation
# ============================================================

def _validate_lats_plan(
    plan: LATSPlan,
) -> LATSPlan:
    """
    Validate LATS candidates and remove duplicate strategies.

    One candidate is allowed because the LLM may correctly conclude
    that only one safe strategy exists for a given failure context.
    """

    if not plan.candidates:
        raise ValueError(
            "LATS produced no recovery candidates."
        )

    seen: set[str] = set()
    unique: list[LATSAlternative] = []

    for candidate in plan.candidates:

        if candidate.strategy in seen:
            continue

        seen.add(
            candidate.strategy
        )

        unique.append(
            candidate
        )

    return LATSPlan(
        candidates=unique
    )


# ============================================================
# Deterministic LATS fallback
# ============================================================

def _deterministic_lats_plan() -> LATSPlan:
    """
    Deterministic fallback used by tests and local development.
    """

    return LATSPlan(
        candidates=[
            LATSAlternative(
                strategy="retry",
                score=0.55,
                rationale=(
                    "Retry is appropriate only when the "
                    "failed action is explicitly retryable."
                ),
            ),
            LATSAlternative(
                strategy="alternative_action",
                score=0.65,
                rationale=(
                    "An alternative read-only action may "
                    "provide a safer recovery path."
                ),
            ),
            LATSAlternative(
                strategy="escalate_to_admin",
                score=0.90,
                rationale=(
                    "Unexpected failures should be reviewed "
                    "by an administrator before recovery."
                ),
            ),
        ]
    )


# ============================================================
# Extract JSON from LLM response
# ============================================================

def _extract_json_object(
    content: str,
) -> str:
    """
    Extract the JSON object from a Groq response.

    Some Groq models can return a <think>...</think> section
    before the final JSON even when the prompt requests JSON only.

    Example:

        <think>
        ...
        </think>

        {
            "candidates": [...]
        }

    This function isolates the final JSON object safely.
    """

    if not content:
        raise ValueError(
            "Groq returned an empty response."
        )

    text = content.strip()

    # ---------------------------------------------------------
    # Remove Markdown code fences if present.
    # ---------------------------------------------------------

    text = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace(
        "```",
        "",
    ).strip()

    # ---------------------------------------------------------
    # Remove <think>...</think> content.
    # ---------------------------------------------------------

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    # ---------------------------------------------------------
    # Find the outermost JSON object.
    # ---------------------------------------------------------

    start = text.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object was found in the Groq response."
        )

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start,
        len(text),
    ):

        char = text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return text[
                    start:index + 1
                ]

    raise ValueError(
        "Could not find a complete JSON object "
        "in the Groq response."
    )


# ============================================================
# Parse LATS JSON
# ============================================================

def _parse_lats_json(
    content: str,
) -> LATSPlan:
    """
    Parse a normal JSON response and validate it through Pydantic.
    """

    cleaned = _extract_json_object(
        content
    )

    try:
        payload = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Groq returned invalid JSON for LATS: "
            f"{cleaned}"
        ) from exc

    try:

        plan = LATSPlan.model_validate(
            payload
        )

    except Exception as exc:

        raise ValueError(
            "Groq returned an invalid LATS plan: "
            f"{payload}"
        ) from exc

    return _validate_lats_plan(
        plan
    )


# ============================================================
# LATS generation
# ============================================================

def generate_lats_plan(
    *,
    context: str,
) -> dict[str, Any]:
    """
    Generate recovery candidates using LATS-style reasoning.

    Real mode:
        Groq generates multiple candidates when appropriate.

    Test mode:
        deterministic candidates are returned.

    Important:
        The model is allowed to return only one candidate if the
        supplied context makes every other strategy unsafe.

    Actual execution safety is enforced later by
    LATSRecoverySelector.
    """

    # ---------------------------------------------------------
    # Deterministic mode
    # ---------------------------------------------------------

    if not use_real_llm():

        plan = _deterministic_lats_plan()

        return {
            "llm_used": False,
            "plan": _validate_lats_plan(
                plan
            ),
        }

    # ---------------------------------------------------------
    # Real LLM mode
    # ---------------------------------------------------------

    llm = _get_llm()

    prompt = f"""
You are selecting recovery strategies for a support-ticket state graph.

Consider these recovery strategies:

- retry
- alternative_action
- escalate_to_admin

Important:
1. Generate multiple candidates when multiple strategies are
   genuinely safe and applicable.
2. Do NOT invent an unavailable strategy.
3. Do NOT recommend retry when the context says the action
   is not retryable.
4. Do NOT recommend alternative_action when no alternative
   is available.
5. Prefer human escalation for ambiguous, unsafe, or
   potentially duplicate-write failures.
6. Score every candidate from 0.0 to 1.0.
7. Include a short rationale.
8. If only ONE strategy is actually safe, return only that
   one strategy.
9. Return ONLY a JSON object.
10. Do NOT include Markdown.
11. Do NOT include <think> text in the requested output.

Required JSON shape:

{{
  "candidates": [
    {{
      "strategy": "escalate_to_admin",
      "score": 0.95,
      "rationale": "Human investigation is safest."
    }}
  ]
}}

Failure context:
{context}
"""

    response = llm.invoke(
        [
            (
                "system",
                (
                    "You are a safe recovery-strategy planner. "
                    "Return a JSON object describing safe candidates."
                ),
            ),
            (
                "human",
                prompt,
            ),
        ]
    )

    content = str(
        response.content
    )

    plan = _parse_lats_json(
        content
    )

    return {
        "llm_used": True,
        "plan": plan,
    }


# ============================================================
# RAG grounding-verdict schema
#
# This is the actual "RAG" LLM-call addition for the Customer
# Follow-up graph: retrieved policy evidence (grounding.py) is
# passed to the LLM, which generates a grounded verdict instead
# of leaving the decision to raw keyword matching.
# ============================================================

class GroundingVerdict(BaseModel):
    """
    LLM-generated verdict over retrieved policy evidence.
    """

    supported: bool

    rationale: str = Field(
        min_length=3
    )


def _deterministic_grounding_verdict(
    *,
    policies_checked: list[str],
    evidence: list[dict[str, Any]],
) -> GroundingVerdict:
    """
    Deterministic fallback used by tests and local development.

    Mirrors the previous keyword-matching behavior exactly, so
    existing deterministic tests are unaffected.
    """

    supported = bool(
        policies_checked
        and evidence
    )

    return GroundingVerdict(
        supported=supported,
        rationale=(
            "Deterministic fallback: supported because matching "
            "policy evidence was retrieved."
            if supported
            else "Deterministic fallback: no matching policy "
            "evidence was retrieved."
        ),
    )


def generate_grounding_verdict(
    *,
    query: str,
    policies_checked: list[str],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Retrieval-Augmented Generation over the retrieved policy evidence.

    Real mode:
        The LLM reads the retrieved evidence (from PolicyGrounder)
        and generates a grounded supported/rationale verdict.

    Test mode:
        deterministic fallback identical to the prior keyword-only
        behavior.
    """

    if not use_real_llm():

        return {
            "llm_used": False,
            "verdict": _deterministic_grounding_verdict(
                policies_checked=policies_checked,
                evidence=evidence,
            ),
        }

    llm = _get_llm()

    evidence_text = json.dumps(
        evidence,
        ensure_ascii=False,
    )

    prompt = f"""
You are grounding a customer follow-up reply against retrieved
company policy evidence.

Customer reply / query:
{query}

Policies checked:
{json.dumps(policies_checked)}

Retrieved evidence (from the policy files):
{evidence_text}

Rules:
1. Base your verdict ONLY on the retrieved evidence above.
2. Do NOT invent policy content that is not in the evidence.
3. "supported" must be true only if the retrieved evidence
   actually addresses the customer reply.
4. Give a short rationale explaining your verdict using the
   evidence.
5. Return ONLY a JSON object: {{"supported": bool, "rationale": str}}
"""

    structured = llm.with_structured_output(
        GroundingVerdict
    )

    verdict = structured.invoke(
        [
            (
                "system",
                (
                    "You are a strict grounding verifier. Only "
                    "use the supplied evidence."
                ),
            ),
            (
                "human",
                prompt,
            ),
        ]
    )

    return {
        "llm_used": True,
        "verdict": verdict,
    }