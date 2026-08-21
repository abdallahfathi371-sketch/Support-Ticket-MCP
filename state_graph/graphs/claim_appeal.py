from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..common.graph_base import DurableGraphRunner
from ..common.grounding import PolicyGrounder
from ..common.store import StateStore


GRAPH_NAME = "claim_appeal"
CLAIM_HITL_THRESHOLD_USD = 3500.0


@dataclass
class ClaimCandidate:
    strategy: str
    action: str
    score: float
    claim_amount_usd: float
    rationale: str


def _runner(
    db_path: str,
) -> tuple[StateStore, DurableGraphRunner]:
    store = StateStore(db_path)
    runner = DurableGraphRunner(store, GRAPH_NAME)
    return store, runner


def _evaluate_hitl_requirement(
    *,
    priority: str,
    selected_strategy: str,
    claim_amount_usd: float,
    tot_score: float,
    grounding_supported: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if claim_amount_usd >= CLAIM_HITL_THRESHOLD_USD:
        reasons.append("CLAIM_AMOUNT_ABOVE_THRESHOLD")
    if selected_strategy in {"appeal_reject", "escalate_to_manual_review"}:
        reasons.append("APPEAL_REQUIRES_ADMIN")
    if priority == "High":
        reasons.append("HIGH_PRIORITY_CLAIM")
    if tot_score < 0.60:
        reasons.append("LOW_TOT_CONFIDENCE")
    if not grounding_supported:
        reasons.append("INSUFFICIENT_POLICY_GROUNDING")

    return bool(reasons), reasons


def generate_claim_tot(
    *,
    ticket_id: int,
    priority: str,
    claim_amount_usd: float,
    policy_evidence: list[str],
) -> dict[str, Any]:
    candidates = [
        ClaimCandidate(
            strategy="request_more_evidence",
            action="collect incident logs and repair invoices",
            score=0.74,
            claim_amount_usd=claim_amount_usd,
            rationale="The claim can be validated with missing supporting evidence.",
        ),
        ClaimCandidate(
            strategy="approve_partial",
            action="approve a partial payout and note the gap",
            score=0.82,
            claim_amount_usd=max(0.0, claim_amount_usd * 0.7),
            rationale="The evidence suggests partial coverage within policy limits.",
        ),
        ClaimCandidate(
            strategy="appeal_reject",
            action="prepare a formal appeal against the insurer decision",
            score=0.9 if claim_amount_usd >= CLAIM_HITL_THRESHOLD_USD else 0.68,
            claim_amount_usd=claim_amount_usd,
            rationale="The strongest strategy when insurer denial conflicts with documented policy support.",
        ),
    ]

    selected = max(candidates, key=lambda item: item.score)
    return {
        "plan": {"candidates": [candidate.__dict__ for candidate in candidates]},
        "selected": selected,
        "llm_used": False,
        "ticket_id": ticket_id,
        "priority": priority,
        "policy_evidence": policy_evidence,
    }


def _run_tot_and_hitl_gate(
    *,
    run_id: str,
    state: dict[str, Any],
    runner: DurableGraphRunner,
) -> tuple[str, str]:
    state["current_state"] = "TREE_OF_THOUGHTS"
    state["status"] = "RUNNING"
    runner.transition(run_id, "TREE_OF_THOUGHTS", state)

    tot = generate_claim_tot(
        ticket_id=int(state["ticket_id"]),
        priority=str(state["priority"]),
        claim_amount_usd=float(state["claim_amount_usd"]),
        policy_evidence=list(state.get("policy_evidence", [])),
    )
    plan = tot["plan"]
    selected = tot["selected"]

    state["tot_llm_used"] = tot["llm_used"]
    state["tot_candidates"] = [dict(candidate) for candidate in plan["candidates"]]
    state["tot_selected"] = selected.__dict__
    state["selected_strategy"] = selected.strategy
    state["claim_amount_usd"] = float(selected.claim_amount_usd)
    state["tot_score"] = float(selected.score)
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["TREE_OF_THOUGHTS"]
    runner.transition(run_id, "TREE_OF_THOUGHTS", state)

    hitl_required, hitl_reason_codes = _evaluate_hitl_requirement(
        priority=str(state["priority"]),
        selected_strategy=str(selected.strategy),
        claim_amount_usd=float(state["claim_amount_usd"]),
        tot_score=float(selected.score),
        grounding_supported=bool(state.get("grounding_supported", False)),
    )

    state["hitl_required"] = hitl_required
    state["hitl_reason_codes"] = hitl_reason_codes
    state["current_state"] = "HITL_GATE"
    runner.transition(run_id, "HITL_GATE", state)
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["HITL_GATE"]

    if not hitl_required:
        state["status"] = "WAITING_FOR_INSURER_ACK"
        state["current_state"] = "WAITING_FOR_INSURER_ACK"
        runner.transition(run_id, "WAITING_FOR_INSURER_ACK", state, run_status="WAITING_FOR_INSURER_ACK")
        return run_id, "WAITING_FOR_INSURER_ACK"

    reason = (
        "Admin approval required for claim escalation. "
        f"Strategy: {selected.strategy}. "
        f"Claim amount: ${selected.claim_amount_usd:.0f}. "
        f"ToT score: {selected.score:.2f}. "
        f"Reasons: {', '.join(hitl_reason_codes)}."
    )
    task_id = runner.pause_for_hitl(run_id, state.get("ticket_id"), reason, state)
    state["hitl_task_id"] = task_id
    state["status"] = "WAITING_HITL"
    state["current_state"] = "WAITING_FOR_ADMIN"
    runner.transition(run_id, "WAITING_FOR_ADMIN", state, run_status="WAITING_HITL")
    return run_id, f"WAITING_HITL:{task_id}"


def start_claim_appeal(
    ticket_id: int,
    *,
    priority: str,
    claim_amount_usd: float,
    issue_summary: str = "",
    db_path: str = "db/support.db",
) -> tuple[str, str]:
    store, runner = _runner(db_path)
    state: dict[str, Any] = {
        "ticket_id": ticket_id,
        "priority": priority,
        "claim_amount_usd": claim_amount_usd,
        "issue_summary": issue_summary,
        "policies_checked": [],
        "policy_evidence": [],
        "grounding_supported": False,
        "tot_candidates": [],
        "tot_selected": None,
        "tot_llm_used": False,
        "selected_strategy": None,
        "tot_score": 0.0,
        "hitl_required": False,
        "hitl_reason_codes": [],
        "hitl_task_id": None,
        "admin_decision": None,
        "admin_id": None,
        "customer_ack": None,
        "failure_id": None,
        "completed_steps": ["COLLECT_CLAIM"],
        "status": "RUNNING",
        "current_state": "COLLECT_CLAIM",
    }

    run_id = runner.start(state, ticket_id=ticket_id, first_state="COLLECT_CLAIM")
    state["current_state"] = "CHECK_POLICY"
    runner.transition(run_id, "CHECK_POLICY", state)
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["CHECK_POLICY"]

    grounder = PolicyGrounder()
    query = (
        f"Claim appeal workflow for {priority} priority claim of ${claim_amount_usd:.0f}. "
        f"Issue: {issue_summary or 'unspecified'}. "
        "Manual review, insurer denial, and appeal policy."
    )
    grounding = grounder.ground(query, policy_files=("ticket_policy.txt", "security_policy.txt"))
    state["policies_checked"] = list(grounding.policies_checked)
    state["policy_evidence"] = list(grounding.evidence)
    state["grounding_supported"] = grounding.supported
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["GROUND_POLICY"]
    runner.transition(run_id, "GROUND_POLICY", state)

    return _run_tot_and_hitl_gate(run_id=run_id, state=state, runner=runner)


def resolve_claim_hitl(
    task_id: str,
    decision: str,
    admin_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    store, runner = _runner(db_path)
    task = store.get_hitl_task(task_id)
    if task is None:
        raise ValueError(f"HITL task not found: {task_id}")
    if task["status"] != "PENDING":
        raise ValueError(f"HITL task {task_id} is not pending")

    normalized = decision.strip().lower()
    if normalized not in {"approve", "approved", "reject", "rejected"}:
        raise ValueError("Decision must be approve or reject")

    run_id = task["run_id"]
    store.resolve_hitl_task(task_id=task_id, decision=normalized, admin_id=admin_id)

    state = task["state"]
    state["admin_decision"] = normalized
    state["admin_id"] = admin_id

    if normalized in {"reject", "rejected"}:
        _, result = _run_tot_and_hitl_gate(run_id=run_id, state=state, runner=runner)
        return result

    state["status"] = "WAITING_FOR_INSURER_ACK"
    state["current_state"] = "WAITING_FOR_INSURER_ACK"
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["APPROVAL_AUTHORIZED"]
    runner.transition(run_id, "WAITING_FOR_INSURER_ACK", state, run_status="WAITING_FOR_INSURER_ACK")
    return "WAITING_FOR_INSURER_ACK"


def submit_claim_decision(
    run_id: str,
    insurer_response: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    store, runner = _runner(db_path)
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]

    if checkpoint["state_name"] != "WAITING_FOR_INSURER_ACK":
        raise ValueError(f"Run {run_id} is not waiting for insurer acknowledgement; current state is {checkpoint['state_name']}")

    normalized = insurer_response.strip().lower()
    state["customer_ack"] = insurer_response

    if normalized in {"reject", "rejected", "no", "decline"}:
        _, result = _run_tot_and_hitl_gate(run_id=run_id, state=state, runner=runner)
        return result

    if normalized not in {"accept", "accepted", "yes", "acknowledge", "acked"}:
        state["status"] = "WAITING_FOR_INSURER_ACK"
        state["current_state"] = "WAITING_FOR_INSURER_ACK"
        runner.transition(run_id, "WAITING_FOR_INSURER_ACK", state, run_status="WAITING_FOR_INSURER_ACK")
        return "WAITING_FOR_INSURER_ACK"

    state["status"] = "RESOLVED"
    state["current_state"] = "RESOLVED"
    state["completed_steps"] = list(state.get("completed_steps", [])) + ["INSURER_ACK", "RESOLVED"]
    runner.transition(run_id, "RESOLVED", state, run_status="RESOLVED")
    return "RESOLVED"


def fail_claim_node(
    run_id: str,
    node_name: str,
    error_message: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    store, runner = _runner(db_path)
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]
    failure_id = runner.fail(run_id, state.get("ticket_id"), node_name, RuntimeError(error_message), state)
    state["failure_id"] = failure_id
    state["status"] = "FAILED"
    state["current_state"] = f"FAILED:{node_name}"
    runner.transition(run_id, f"FAILED:{node_name}", state, run_status="FAILED")
    return failure_id


def resume_claim_after_failure(
    failure_id: str,
    resolution: str,
    admin_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:
    store, runner = _runner(db_path)
    failures = store.list_failure_tickets()
    match = next((item for item in failures if item["failure_id"] == failure_id), None)
    if match is None:
        raise ValueError(f"Failure ticket not found: {failure_id}")

    store.resolve_failure(failure_id=failure_id, resolution=resolution, admin_id=admin_id)
    run_id = match["run_id"]
    checkpoint = runner.recover(run_id)
    state = checkpoint["state"]
    state["failure_resolved"] = True
    state["failure_resolution"] = resolution
    state["status"] = "RUNNING"

    completed = list(state.get("completed_steps", []))
    if "COLLECT_CLAIM" in completed and "GROUND_POLICY" in completed:
        _, result = _run_tot_and_hitl_gate(run_id=run_id, state=state, runner=runner)
        return result

    state["current_state"] = "WAITING_FOR_ADMIN"
    runner.transition(run_id, "WAITING_FOR_ADMIN", state, run_status="WAITING_HITL")
    return "WAITING_FOR_ADMIN"
