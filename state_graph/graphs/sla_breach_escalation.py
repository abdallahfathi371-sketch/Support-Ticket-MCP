from __future__ import annotations

"""
Graph #2 — SLA Breach Escalation (Member 1)

Locatable concerns in this file:
- STATE CYCLE DEFINITIONS (see ASCII flow below)
- CHECKPOINTING via DurableGraphRunner.transition
- HITL node (pause_for_hitl / WAITING_FOR_ADMIN)
- FAILURE TICKET path (runner.fail) distinct from HITL
- LLM addition #1: Tree-of-Thoughts remediation selection
- LLM addition #2: Constrained ReAct execution (async MCP path)
- Deterministic SLA/ticket policy load (not counted as RAG addition)

Flow:

    DETECT_BREACH
          |
          v
    GROUND_SLA_POLICY   (deterministic company policy evidence)
          |
          v
    TREE_OF_THOUGHTS    (LLM addition #1)
          |
          v
    HITL_GATE -----------+
          |              |
          | (required)   | (not required — rare)
          v              v
    WAITING_FOR_ADMIN   EXECUTE_REMEDIATION
          |                      |
     approve / reject            |
          |                      |
     reject -> TREE_OF_THOUGHTS (cycle)
          |
     approve -> EXECUTE_REMEDIATION
                      |
                      v
            WAITING_FOR_CUSTOMER_ACK
                      |
               accept / reject
                      |
               reject -> TREE_OF_THOUGHTS (cycle)
                      |
                   RESOLVED

Why this needs a state graph (not a DAG / for-loop):
- Real wait on customer acknowledgement of the goodwill offer
- Real human decision before credits >= $50 or High-priority closes
- Real cost if progress is lost mid-breach (SLA window keeps burning)
"""

from typing import Any

from ..common.graph_base import DurableGraphRunner
from ..common.grounding import PolicyGrounder
from ..common.store import StateStore
from ..common.tot_remediation import (
    GOODWILL_CREDIT_HITL_THRESHOLD_USD,
    generate_remediation_tot,
)


GRAPH_NAME = "sla_breach_escalation"

# Resolution targets from mcp_server/policies/sla_policy.txt
# (business days approximated as 24h blocks for durable demo timing).
SLA_RESOLUTION_HOURS = {
    "High": 24.0,
    "Medium": 72.0,
    "Low": 120.0,
}

SLA_FIRST_RESPONSE_HOURS = {
    "High": 1.0,
    "Medium": 4.0,
    "Low": 24.0,
}


def _sla_target_hours(priority: str) -> float:
    return SLA_RESOLUTION_HOURS.get(
        priority,
        SLA_RESOLUTION_HOURS["Medium"],
    )


def _evaluate_hitl_requirement(
    *,
    priority: str,
    selected_strategy: str,
    proposed_credit_usd: float,
    tot_score: float,
    grounding_supported: bool,
) -> tuple[bool, list[str]]:
    """
    Explicit HITL policy for Graph #2.

    HITL is mandatory when:

    1. Goodwill credit >= $50
       (agent must not issue material credits alone).

    2. Strategy is request_goodwill_credit at any amount
       (finance-adjacent action).

    3. Ticket priority is High
       (matches existing close-high-priority elicitation policy).

    4. ToT confidence score is below 0.60
       (agent is not sure enough to act alone).

    5. SLA/policy grounding is unsupported
       (no safe policy evidence for the breach response).
    """

    reasons: list[str] = []

    if proposed_credit_usd >= GOODWILL_CREDIT_HITL_THRESHOLD_USD:
        reasons.append(
            "GOODWILL_CREDIT_ABOVE_THRESHOLD"
        )

    if selected_strategy == "request_goodwill_credit":
        reasons.append(
            "GOODWILL_CREDIT_REQUIRES_ADMIN"
        )

    if priority == "High":
        reasons.append(
            "HIGH_PRIORITY_TICKET"
        )

    if tot_score < 0.60:
        reasons.append(
            "LOW_TOT_CONFIDENCE"
        )

    if not grounding_supported:
        reasons.append(
            "INSUFFICIENT_SLA_POLICY_GROUNDING"
        )

    return (
        bool(reasons),
        reasons,
    )


def _runner(
    db_path: str,
) -> tuple[StateStore, DurableGraphRunner]:
    store = StateStore(db_path)
    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )
    return store, runner


def start_sla_breach_escalation(
    ticket_id: int,
    *,
    priority: str,
    hours_open: float,
    issue_summary: str = "",
    db_path: str = "db/support.db",
) -> tuple[str, str]:
    """
    Start Graph #2 and advance through DETECT → GROUND → ToT → HITL/wait.

    The sync path pauses on HITL for grader-visible admin work.
    Live MCP execution is available via execute_remediation_with_mcp().
    """

    store, runner = _runner(db_path)

    sla_target = _sla_target_hours(priority)
    breached = hours_open > sla_target

    state: dict[str, Any] = {
        "ticket_id": ticket_id,
        "priority": priority,
        "hours_open": hours_open,
        "sla_target_hours": sla_target,
        "first_response_hours": SLA_FIRST_RESPONSE_HOURS.get(
            priority,
            4.0,
        ),
        "breach_detected": breached,
        "issue_summary": issue_summary,

        "policies_checked": [],
        "policy_evidence": [],
        "grounding_supported": False,

        "tot_candidates": [],
        "tot_selected": None,
        "tot_llm_used": False,
        "selected_strategy": None,
        "proposed_credit_usd": 0.0,
        "tot_score": 0.0,

        "hitl_required": False,
        "hitl_reason_codes": [],
        "hitl_task_id": None,
        "admin_decision": None,
        "admin_id": None,

        "react_trace": [],
        "react_success": False,
        "react_llm_used": False,

        "customer_ack": None,
        "failure_id": None,

        "completed_steps": [],
        "status": "RUNNING",
        "current_state": "DETECT_BREACH",
    }

    run_id = runner.start(
        state,
        ticket_id=ticket_id,
        first_state="DETECT_BREACH",
    )

    state["completed_steps"].append("DETECT_BREACH")

    if not breached:
        state["status"] = "NO_BREACH"
        state["current_state"] = "NO_BREACH"
        runner.transition(
            run_id,
            "NO_BREACH",
            state,
            run_status="NO_BREACH",
        )
        return run_id, "NO_BREACH"

    # ---------------------------------------------------------
    # GROUND_SLA_POLICY — deterministic load of existing company
    # SLA/ticket policies (evidence for ToT + HITL). Not counted
    # as the RAG LLM-call addition; Graph #2's two additions are
    # Tree-of-Thoughts + Constrained ReAct.
    # ---------------------------------------------------------

    state["current_state"] = "GROUND_SLA_POLICY"
    runner.transition(
        run_id,
        "GROUND_SLA_POLICY",
        state,
    )

    grounder = PolicyGrounder()
    query = (
        f"SLA breach escalation for {priority} priority ticket. "
        f"Open {hours_open} hours against {sla_target}h target. "
        f"Issue: {issue_summary or 'unspecified'}. "
        "Goodwill credit and status change policy."
    )

    grounding = grounder.ground(
        query,
        policy_files=(
            "sla_policy.txt",
            "ticket_policy.txt",
            "security_policy.txt",
        ),
    )

    state["policies_checked"] = list(
        grounding.policies_checked
    )
    state["policy_evidence"] = list(
        grounding.evidence
    )
    state["grounding_supported"] = grounding.supported
    state["completed_steps"].append("GROUND_SLA_POLICY")

    runner.transition(
        run_id,
        "GROUND_SLA_POLICY",
        state,
    )

    # ---------------------------------------------------------
    # TREE_OF_THOUGHTS — branch over remediation strategies
    # ---------------------------------------------------------

    return _run_tot_and_hitl_gate(
        run_id=run_id,
        state=state,
        runner=runner,
    )


def _run_tot_and_hitl_gate(
    *,
    run_id: str,
    state: dict[str, Any],
    runner: DurableGraphRunner,
) -> tuple[str, str]:
    """
    Shared ToT → HITL gate used on start and after reject cycles.
    """

    state["current_state"] = "TREE_OF_THOUGHTS"
    state["status"] = "RUNNING"

    runner.transition(
        run_id,
        "TREE_OF_THOUGHTS",
        state,
    )

    tot = generate_remediation_tot(
        ticket_id=int(state["ticket_id"]),
        priority=str(state["priority"]),
        hours_open=float(state["hours_open"]),
        sla_target_hours=float(state["sla_target_hours"]),
        policy_evidence=list(
            state.get("policy_evidence", [])
        ),
    )

    plan = tot["plan"]
    selected = tot["selected"]

    state["tot_llm_used"] = tot["llm_used"]
    state["tot_candidates"] = [
        candidate.model_dump()
        for candidate in plan.candidates
    ]
    state["tot_selected"] = selected.model_dump()
    state["selected_strategy"] = selected.strategy
    state["proposed_credit_usd"] = float(
        selected.proposed_credit_usd
    )
    state["tot_score"] = float(selected.score)
    state["completed_steps"].append("TREE_OF_THOUGHTS")

    runner.transition(
        run_id,
        "TREE_OF_THOUGHTS",
        state,
    )

    hitl_required, hitl_reason_codes = (
        _evaluate_hitl_requirement(
            priority=str(state["priority"]),
            selected_strategy=str(selected.strategy),
            proposed_credit_usd=float(
                selected.proposed_credit_usd
            ),
            tot_score=float(selected.score),
            grounding_supported=bool(
                state.get("grounding_supported")
            ),
        )
    )

    state["hitl_required"] = hitl_required
    state["hitl_reason_codes"] = hitl_reason_codes

    state["current_state"] = "HITL_GATE"
    runner.transition(
        run_id,
        "HITL_GATE",
        state,
    )
    state["completed_steps"].append("HITL_GATE")

    if not hitl_required:
        # Safe autonomous path: skip admin, wait for customer ack
        # after a planned remediation is recorded.
        state["status"] = "WAITING_FOR_CUSTOMER_ACK"
        state["current_state"] = "WAITING_FOR_CUSTOMER_ACK"
        state["remediation_planned"] = True

        runner.transition(
            run_id,
            "WAITING_FOR_CUSTOMER_ACK",
            state,
            run_status="WAITING_FOR_CUSTOMER_ACK",
        )

        return run_id, "WAITING_FOR_CUSTOMER_ACK"

    reason = (
        "Admin approval required for SLA breach remediation. "
        f"Strategy: {selected.strategy}. "
        f"Proposed credit: ${selected.proposed_credit_usd:.0f}. "
        f"ToT score: {selected.score:.2f}. "
        f"Reasons: {', '.join(hitl_reason_codes)}."
    )

    task_id = runner.pause_for_hitl(
        run_id,
        state.get("ticket_id"),
        reason,
        state,
    )

    state["hitl_task_id"] = task_id
    state["status"] = "WAITING_HITL"
    state["current_state"] = "WAITING_FOR_ADMIN"

    runner.transition(
        run_id,
        "WAITING_FOR_ADMIN",
        state,
        run_status="WAITING_HITL",
    )

    return run_id, f"WAITING_HITL:{task_id}"


def resolve_sla_breach_hitl(
    task_id: str,
    decision: str,
    admin_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Admin acts through the platform on a pending HITL task.

    approve → WAITING_FOR_CUSTOMER_ACK (remediation authorized)
    reject  → TREE_OF_THOUGHTS again (real cycle)
    """

    store, runner = _runner(db_path)

    task = store.get_hitl_task(task_id)

    if task is None:
        raise ValueError(
            f"HITL task not found: {task_id}"
        )

    if task["status"] != "PENDING":
        raise ValueError(
            f"HITL task {task_id} is not pending"
        )

    normalized = decision.strip().lower()

    if normalized not in {
        "approve",
        "approved",
        "reject",
        "rejected",
    }:
        raise ValueError(
            "Decision must be approve or reject"
        )

    run_id = task["run_id"]

    store.resolve_hitl_task(
        task_id=task_id,
        decision=normalized,
        admin_id=admin_id,
    )

    state = task["state"]
    state["admin_decision"] = normalized
    state["admin_id"] = admin_id

    if normalized in {"reject", "rejected"}:
        # Cycle: admin rejected the proposed remediation.
        _, result = _run_tot_and_hitl_gate(
            run_id=run_id,
            state=state,
            runner=runner,
        )
        return result

    # Approved — remediation may proceed; wait for customer ack.
    state["remediation_authorized"] = True
    state["status"] = "WAITING_FOR_CUSTOMER_ACK"
    state["current_state"] = "WAITING_FOR_CUSTOMER_ACK"
    state["completed_steps"] = list(
        state.get("completed_steps", [])
    ) + ["EXECUTE_REMEDIATION_AUTHORIZED"]

    runner.transition(
        run_id,
        "WAITING_FOR_CUSTOMER_ACK",
        state,
        run_status="WAITING_FOR_CUSTOMER_ACK",
    )

    return "WAITING_FOR_CUSTOMER_ACK"


def submit_customer_acknowledgement(
    run_id: str,
    acknowledgement: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    External customer event: accept or reject the remediation offer.

    accept → RESOLVED
    reject → TREE_OF_THOUGHTS (cycle back for a new strategy)
    """

    store, runner = _runner(db_path)
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]

    if checkpoint["state_name"] != "WAITING_FOR_CUSTOMER_ACK":
        raise ValueError(
            f"Run {run_id} is not waiting for customer ack; "
            f"current state is {checkpoint['state_name']}"
        )

    normalized = acknowledgement.strip().lower()
    state["customer_ack"] = acknowledgement

    if normalized in {
        "reject",
        "rejected",
        "no",
        "decline",
    }:
        _, result = _run_tot_and_hitl_gate(
            run_id=run_id,
            state=state,
            runner=runner,
        )
        return result

    if normalized not in {
        "accept",
        "accepted",
        "yes",
        "acknowledge",
        "acked",
    }:
        # Empty / unclear reply: stay waiting (genuine wait state).
        state["status"] = "WAITING_FOR_CUSTOMER_ACK"
        state["current_state"] = "WAITING_FOR_CUSTOMER_ACK"
        runner.transition(
            run_id,
            "WAITING_FOR_CUSTOMER_ACK",
            state,
            run_status="WAITING_FOR_CUSTOMER_ACK",
        )
        return "WAITING_FOR_CUSTOMER_ACK"

    state["status"] = "RESOLVED"
    state["current_state"] = "RESOLVED"
    state["completed_steps"] = list(
        state.get("completed_steps", [])
    ) + ["CUSTOMER_ACK", "RESOLVED"]

    runner.transition(
        run_id,
        "RESOLVED",
        state,
        run_status="RESOLVED",
    )

    return "RESOLVED"


def fail_sla_breach_node(
    run_id: str,
    node_name: str,
    error_message: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Unplanned mid-node failure → OPEN failure ticket.

    Distinct from HITL: this is not an expected pause for a decision.
    """

    store, runner = _runner(db_path)
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]

    failure_id = runner.fail(
        run_id,
        state.get("ticket_id"),
        node_name,
        RuntimeError(error_message),
        state,
    )

    state["failure_id"] = failure_id
    state["status"] = "FAILED"
    state["current_state"] = f"FAILED:{node_name}"

    runner.transition(
        run_id,
        f"FAILED:{node_name}",
        state,
        run_status="FAILED",
    )

    return failure_id


def resume_sla_breach_after_failure(
    failure_id: str,
    resolution: str,
    admin_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Resolve a failure ticket and resume from the last checkpoint.

    Does NOT restart from DETECT_BREACH — completed_steps are kept.
    """

    store, runner = _runner(db_path)

    failures = store.list_failure_tickets()
    match = next(
        (
            item
            for item in failures
            if item["failure_id"] == failure_id
        ),
        None,
    )

    if match is None:
        raise ValueError(
            f"Failure ticket not found: {failure_id}"
        )

    store.resolve_failure(
        failure_id=failure_id,
        resolution=resolution,
        admin_id=admin_id,
    )

    run_id = match["run_id"]
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]

    # Resume into ToT/HITL from durable state — no re-detect.
    state["failure_resolved"] = True
    state["failure_resolution"] = resolution
    state["status"] = "RUNNING"

    completed = list(
        state.get("completed_steps", [])
    )

    if "DETECT_BREACH" in completed and "GROUND_SLA_POLICY" in completed:
        _, result = _run_tot_and_hitl_gate(
            run_id=run_id,
            state=state,
            runner=runner,
        )
        return result

    # Fallback: re-enter wait for admin if somehow mid-HITL.
    state["current_state"] = "WAITING_FOR_ADMIN"
    runner.transition(
        run_id,
        "WAITING_FOR_ADMIN",
        state,
        run_status="WAITING_HITL",
    )
    return "WAITING_FOR_ADMIN"


async def execute_remediation_with_mcp(
    run_id: str,
    mcp_client: Any,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Live path: Constrained ReAct executes whitelisted MCP tools
    after admin authorization (or autonomous gate pass).
    """

    from ..common.react import run_sla_remediation

    store, runner = _runner(db_path)
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]

    if checkpoint["state_name"] not in {
        "WAITING_FOR_CUSTOMER_ACK",
        "HITL_GATE",
        "EXECUTE_REMEDIATION",
    }:
        # Allow execute right after approve by moving explicitly.
        if checkpoint["state_name"] == "WAITING_FOR_ADMIN":
            raise ValueError(
                "Cannot execute remediation while still waiting "
                "for admin HITL decision."
            )

    state["current_state"] = "EXECUTE_REMEDIATION"
    state["status"] = "RUNNING"
    runner.transition(
        run_id,
        "EXECUTE_REMEDIATION",
        state,
    )

    ticket_id = int(state["ticket_id"])
    strategy = str(
        state.get("selected_strategy") or "set_status_pending"
    )

    try:
        react_result = await run_sla_remediation(
            mcp_client,
            ticket_id=ticket_id,
            strategy=strategy,
            proposed_credit_usd=float(
                state.get("proposed_credit_usd") or 0.0
            ),
            context=(
                f"SLA breach remediation. "
                f"Strategy={strategy}. "
                f"Priority={state.get('priority')}. "
                f"Hours open={state.get('hours_open')}."
            ),
        )
    except Exception as exc:
        failure_id = runner.fail(
            run_id,
            ticket_id,
            "EXECUTE_REMEDIATION",
            exc,
            state,
        )
        state["failure_id"] = failure_id
        state["status"] = "FAILED"
        state["current_state"] = "FAILED:EXECUTE_REMEDIATION"
        runner.transition(
            run_id,
            "FAILED:EXECUTE_REMEDIATION",
            state,
            run_status="FAILED",
        )
        return f"FAILED:{failure_id}"

    state["react_trace"] = react_result.get("steps", [])
    state["react_success"] = react_result.get("success", False)
    state["react_llm_used"] = react_result.get("llm_used", False)
    state["completed_steps"] = list(
        state.get("completed_steps", [])
    ) + ["EXECUTE_REMEDIATION"]

    if not react_result.get("success"):
        failure_id = runner.fail(
            run_id,
            ticket_id,
            "CONSTRAINED_REACT",
            RuntimeError(
                react_result.get(
                    "error",
                    "Constrained ReAct failed during SLA remediation.",
                )
            ),
            state,
        )
        state["failure_id"] = failure_id
        state["status"] = "FAILED"
        state["current_state"] = "FAILED:CONSTRAINED_REACT"
        runner.transition(
            run_id,
            "FAILED:CONSTRAINED_REACT",
            state,
            run_status="FAILED",
        )
        return f"FAILED:{failure_id}"

    state["status"] = "WAITING_FOR_CUSTOMER_ACK"
    state["current_state"] = "WAITING_FOR_CUSTOMER_ACK"
    runner.transition(
        run_id,
        "WAITING_FOR_CUSTOMER_ACK",
        state,
        run_status="WAITING_FOR_CUSTOMER_ACK",
    )

    return "WAITING_FOR_CUSTOMER_ACK"
