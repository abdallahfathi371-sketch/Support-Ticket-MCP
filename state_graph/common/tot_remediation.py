from __future__ import annotations

"""
Tree-of-Thoughts remediation selector for Graph #2 (SLA Breach Escalation).

Locatable concern:
- Candidate generation (branching thoughts)
- Independent scoring of each candidate
- Beam selection of the best remediation strategy

This is distinct from Member 2's LATS recovery selector: LATS chooses
how to recover from an unplanned failure; ToT here chooses which
business remediation to propose for an SLA breach.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from .llm_reasoning import use_real_llm


RemediationStrategy = Literal[
    "escalate_priority",
    "set_status_pending",
    "request_goodwill_credit",
    "reassign_escalation_team",
]


class RemediationThought(BaseModel):
    """
    One ToT candidate for SLA breach remediation.
    """

    strategy: RemediationStrategy
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=3)
    proposed_credit_usd: float = Field(
        default=0.0,
        ge=0.0,
    )
    target_status: Literal[
        "Open",
        "Pending",
        "Closed",
    ] | None = None
    target_priority: Literal[
        "Low",
        "Medium",
        "High",
    ] | None = None


class RemediationToTPlan(BaseModel):
    """
    Bounded Tree-of-Thoughts plan over remediation strategies.
    """

    candidates: list[RemediationThought] = Field(
        min_length=2,
        max_length=4,
    )


GOODWILL_CREDIT_HITL_THRESHOLD_USD = 50.0


def _deterministic_tot_plan(
    *,
    priority: str,
    hours_open: float,
    breach_ratio: float,
) -> RemediationToTPlan:
    """
    Deterministic ToT used by tests and local development.

    Ranking intentionally depends on breach severity so the graph
    has a real branch, not a fixed single path.
    """

    credit = 25.0

    if breach_ratio >= 2.0:
        credit = 75.0
    elif breach_ratio >= 1.5:
        credit = 55.0

    candidates = [
        RemediationThought(
            strategy="escalate_priority",
            score=0.72 if priority != "High" else 0.35,
            rationale=(
                "Raise ticket priority so the queue honors SLA "
                "ordering for remaining work."
            ),
            proposed_credit_usd=0.0,
            target_priority="High",
            target_status=None,
        ),
        RemediationThought(
            strategy="set_status_pending",
            score=0.58,
            rationale=(
                "Move the ticket to Pending while engineering "
                "confirms a fix, preserving an honest customer wait."
            ),
            proposed_credit_usd=0.0,
            target_status="Pending",
            target_priority=None,
        ),
        RemediationThought(
            strategy="request_goodwill_credit",
            score=0.88 if credit >= GOODWILL_CREDIT_HITL_THRESHOLD_USD else 0.62,
            rationale=(
                f"Offer a goodwill credit of ${credit:.0f} because "
                f"the ticket has been open {hours_open:.1f}h past SLA."
            ),
            proposed_credit_usd=credit,
            target_status="Pending",
            target_priority=None,
        ),
        RemediationThought(
            strategy="reassign_escalation_team",
            score=0.80 if priority == "High" else 0.55,
            rationale=(
                "Reassign ownership to the Support escalation path "
                "so a senior agent owns the breach response."
            ),
            proposed_credit_usd=0.0,
            target_status="Open",
            target_priority=None,
        ),
    ]

    ranked = sorted(
        candidates,
        key=lambda item: item.score,
        reverse=True,
    )

    return RemediationToTPlan(
        candidates=ranked
    )


def select_best_thought(
    plan: RemediationToTPlan,
) -> RemediationThought:
    """
    Beam width = 1: keep the highest-scoring thought.
    """

    return sorted(
        plan.candidates,
        key=lambda item: item.score,
        reverse=True,
    )[0]


def generate_remediation_tot(
    *,
    ticket_id: int,
    priority: str,
    hours_open: float,
    sla_target_hours: float,
    policy_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Tree-of-Thoughts over SLA breach remediation strategies.

    Real mode: Groq scores multiple distinct remediation thoughts.
    Test mode: deterministic scoring from breach severity.
    """

    breach_ratio = (
        hours_open / sla_target_hours
        if sla_target_hours > 0
        else 1.0
    )

    if not use_real_llm():
        plan = _deterministic_tot_plan(
            priority=priority,
            hours_open=hours_open,
            breach_ratio=breach_ratio,
        )

        best = select_best_thought(plan)

        return {
            "llm_used": False,
            "plan": plan,
            "selected": best,
        }

    from .llm_reasoning import _get_llm
    import json

    llm = _get_llm()

    prompt = f"""
You are running Tree-of-Thoughts for an SLA breach on a support ticket.

Ticket ID: {ticket_id}
Priority: {priority}
Hours open: {hours_open}
SLA resolution target (hours): {sla_target_hours}
Breach ratio: {breach_ratio:.2f}

Retrieved policy evidence:
{json.dumps(policy_evidence, ensure_ascii=False)}

Allowed strategies (use ONLY these):
- escalate_priority
- set_status_pending
- request_goodwill_credit
- reassign_escalation_team

Rules:
1. Produce 2-4 DISTINCT candidate thoughts.
2. Score each candidate from 0.0 to 1.0.
3. For request_goodwill_credit, set proposed_credit_usd sensibly
   (25, 55, or 75). Credits >= 50 require human approval later.
4. Do not invent tools or ticket IDs.
5. Prefer safer, policy-aligned remediations for High priority.
6. Return ONLY the structured plan.
"""

    structured = llm.with_structured_output(
        RemediationToTPlan
    )

    plan = structured.invoke(
        [
            (
                "system",
                (
                    "You are a Tree-of-Thoughts planner for SLA "
                    "breach remediation. Branch, score, and stay "
                    "inside the allowed strategy set."
                ),
            ),
            (
                "human",
                prompt,
            ),
        ]
    )

    best = select_best_thought(plan)

    return {
        "llm_used": True,
        "plan": plan,
        "selected": best,
    }
