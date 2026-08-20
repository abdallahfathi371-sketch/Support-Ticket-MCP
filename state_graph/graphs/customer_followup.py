from __future__ import annotations

from typing import Any

from ..common.graph_base import DurableGraphRunner
from ..common.grounding import ground_customer_followup
from ..common.llm_reasoning import generate_grounding_verdict
from ..common.store import StateStore


GRAPH_NAME = "customer_followup"


def _extract_ticket_from_react(
    react_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Extract the ticket returned by the constrained ReAct
    get_ticket observation.
    """

    for step in react_result.get(
        "steps",
        [],
    ):
        observation = step.get(
            "observation",
            {},
        )

        if not isinstance(
            observation,
            dict,
        ):
            continue

        data = observation.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        ticket = data.get(
            "ticket"
        )

        if isinstance(
            ticket,
            dict,
        ):
            return ticket

    return None


def _evaluate_hitl_requirement(
    *,
    ticket: dict[str, Any] | None,
    grounding_supported: bool,
    react_success: bool,
) -> tuple[bool, list[str]]:
    """
    Explicit HITL policy.

    HITL is mandatory when:

    1. Ticket priority is High.
       A high-priority ticket must not be resolved
       autonomously.

    2. Company-policy grounding is insufficient.
       The agent does not have enough policy evidence
       to make a safe decision.

    3. MCP validation failed.
       The graph cannot establish that the ticket state
       is safe to resolve.

    The returned reason codes are persisted in graph state
    and visible to the admin.
    """

    reasons: list[str] = []

    if not react_success:
        reasons.append(
            "MCP_VALIDATION_FAILED"
        )

    if not grounding_supported:
        reasons.append(
            "INSUFFICIENT_POLICY_GROUNDING"
        )

    priority = None

    if ticket is not None:
        priority = ticket.get(
            "priority"
        )

    if priority == "High":
        reasons.append(
            "HIGH_PRIORITY_TICKET"
        )

    return (
        bool(reasons),
        reasons,
    )


def start_customer_followup(
    ticket_id: int,
    reason: str,
    *,
    db_path: str = "db/support.db",
) -> tuple[str, str]:

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    state: dict[str, Any] = {
        "ticket_id": ticket_id,
        "reason": reason,
        "customer_reply": None,
        "required_information": [],
        "retrieved_policy": None,

        "grounding": None,
        "policies_checked": [],
        "policy_evidence": [],
        "grounding_supported": False,

        "react_trace": [],
        "react_success": False,
        "react_llm_used": False,
        "validated_ticket": None,

        "hitl_required": False,
        "hitl_reason_codes": [],
        "hitl_task_id": None,

        "admin_decision": None,
        "admin_id": None,

        "status": "RUNNING",
        "current_state": "COLLECT_TICKET",
    }

    run_id = runner.start(
        state,
        ticket_id=ticket_id,
        first_state="COLLECT_TICKET",
    )

    state["current_state"] = (
        "REQUEST_CUSTOMER_INFO"
    )

    runner.transition(
        run_id,
        "REQUEST_CUSTOMER_INFO",
        state,
    )

    state["current_state"] = (
        "WAITING_FOR_CUSTOMER"
    )

    state["status"] = (
        "WAITING_FOR_CUSTOMER"
    )

    runner.transition(
        run_id,
        "WAITING_FOR_CUSTOMER",
        state,
        run_status="WAITING_FOR_CUSTOMER",
    )

    return (
        run_id,
        "WAITING_FOR_CUSTOMER",
    )


def submit_customer_reply(
    run_id: str,
    reply: str,
    *,
    db_path: str = "db/support.db",
) -> str:

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    checkpoint = runner.recover(
        run_id
    )

    state = checkpoint["state"]

    if checkpoint["state_name"] != (
        "WAITING_FOR_CUSTOMER"
    ):
        raise ValueError(
            f"Run {run_id} is not waiting "
            f"for a customer reply; "
            f"current state is "
            f"{checkpoint['state_name']}"
        )

    if not reply.strip():

        state["status"] = (
            "WAITING_FOR_CUSTOMER"
        )

        state["current_state"] = (
            "WAITING_FOR_CUSTOMER"
        )

        runner.transition(
            run_id,
            "WAITING_FOR_CUSTOMER",
            state,
            run_status="WAITING_FOR_CUSTOMER",
        )

        return (
            "WAITING_FOR_CUSTOMER"
        )

    state["customer_reply"] = reply
    state["status"] = "RUNNING"
    state["current_state"] = (
        "VALIDATE_REPLY"
    )

    runner.transition(
        run_id,
        "VALIDATE_REPLY",
        state,
    )

    grounding = ground_customer_followup(
        reply
    )

    state["grounding"] = (
        grounding.to_dict()
    )

    state["policies_checked"] = list(
        grounding.policies_checked
    )

    state["policy_evidence"] = list(
        grounding.evidence
    )

    # ---------------------------------------------------------
    # RAG: generate a grounded verdict from the retrieved
    # policy evidence, instead of trusting keyword matching
    # alone. Deterministic fallback keeps prior test behavior
    # unchanged when STATE_GRAPH_USE_REAL_LLM is not set.
    # ---------------------------------------------------------

    rag_result = generate_grounding_verdict(
        query=reply,
        policies_checked=grounding.policies_checked,
        evidence=grounding.evidence,
    )

    rag_verdict = rag_result["verdict"]

    grounding_supported = (
        rag_verdict.supported
        if rag_result["llm_used"]
        else grounding.supported
    )

    state["grounding_supported"] = (
        grounding_supported
    )

    state["rag_llm_used"] = (
        rag_result["llm_used"]
    )

    state["rag_rationale"] = (
        rag_verdict.rationale
    )

    runner.transition(
        run_id,
        "GROUNDING",
        state,
    )

    # ---------------------------------------------------------
    # Synchronous compatibility path
    #
    # MCP ticket details are not available here, so the graph
    # conservatively requires admin validation whenever ticket
    # safety cannot be established.
    # ---------------------------------------------------------

    hitl_required, hitl_reason_codes = (
        _evaluate_hitl_requirement(
            ticket=None,
            grounding_supported=(
                grounding_supported
            ),
            react_success=False,
        )
    )

    # Conservative safety fallback:
    # no MCP validation means autonomous resolution is forbidden.
    hitl_required = True

    if "MCP_VALIDATION_FAILED" not in (
        hitl_reason_codes
    ):
        hitl_reason_codes.append(
            "MCP_VALIDATION_REQUIRED"
        )

    state["hitl_required"] = (
        hitl_required
    )

    state["hitl_reason_codes"] = (
        hitl_reason_codes
    )

    policy_names = list(
        grounding.policies_checked
    )

    policies_text = (
        ", ".join(policy_names)
        if policy_names
        else "No company policies found"
    )

    reason = (
        "Admin validation is required because "
        "the graph cannot safely resolve the ticket "
        "without MCP ticket validation. "
        f"Customer reply: {reply}. "
        f"Policies checked: {policies_text}. "
        f"Reason codes: "
        f"{', '.join(hitl_reason_codes)}."
    )

    task_id = runner.pause_for_hitl(
        run_id,
        state.get("ticket_id"),
        reason,
        state,
    )

    state["hitl_task_id"] = (
        task_id
    )

    state["status"] = (
        "WAITING_HITL"
    )

    state["current_state"] = (
        "WAITING_FOR_ADMIN"
    )

    runner.transition(
        run_id,
        "WAITING_FOR_ADMIN",
        state,
        run_status="WAITING_HITL",
    )

    return (
        f"WAITING_HITL:{task_id}"
    )


def resolve_customer_followup(
    task_id: str,
    decision: str,
    admin_id: str,
    *,
    db_path: str = "db/support.db",
) -> str:

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    task = store.get_hitl_task(
        task_id
    )

    if task is None:
        raise ValueError(
            f"HITL task not found: {task_id}"
        )

    if task["status"] != "PENDING":
        raise ValueError(
            f"HITL task {task_id} is not pending"
        )

    normalized = (
        decision
        .strip()
        .lower()
    )

    if normalized not in {
        "approve",
        "approved",
        "resolve",
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

    state["admin_decision"] = (
        normalized
    )

    state["admin_id"] = (
        admin_id
    )

    if normalized in {
        "approve",
        "approved",
        "resolve",
    }:

        state["status"] = "RESOLVED"

        state["current_state"] = (
            "RESOLVE"
        )

        runner.transition(
            run_id,
            "RESOLVE",
            state,
            run_status="RESOLVED",
        )

        return "RESOLVE"

    state["status"] = (
        "WAITING_FOR_CUSTOMER"
    )

    state["current_state"] = (
        "WAITING_FOR_CUSTOMER"
    )

    runner.transition(
        run_id,
        "WAITING_FOR_CUSTOMER",
        state,
        run_status="WAITING_FOR_CUSTOMER",
    )

    return "WAITING_FOR_CUSTOMER"


admin_decision = (
    resolve_customer_followup
)


async def submit_customer_reply_with_mcp(
    run_id: str,
    reply: str,
    mcp_client: Any,
    *,
    db_path: str = "db/support.db",
) -> str:
    """
    Live integration path.

    Flow:

        customer reply
            ↓
        grounding
            ↓
        real/deterministic ReAct
            ↓
        MCP ticket validation
            ↓
        explicit HITL policy
            ↓
        admin
    """

    from ..common.react import (
        run_customer_validation,
    )

    store = StateStore(db_path)

    runner = DurableGraphRunner(
        store,
        GRAPH_NAME,
    )

    checkpoint = runner.recover(
        run_id
    )

    state = checkpoint["state"]

    if checkpoint["state_name"] != (
        "WAITING_FOR_CUSTOMER"
    ):
        raise ValueError(
            f"Run {run_id} is not waiting "
            f"for a customer reply; "
            f"current state is "
            f"{checkpoint['state_name']}"
        )

    if not reply.strip():

        state["status"] = (
            "WAITING_FOR_CUSTOMER"
        )

        state["current_state"] = (
            "WAITING_FOR_CUSTOMER"
        )

        runner.transition(
            run_id,
            "WAITING_FOR_CUSTOMER",
            state,
            run_status="WAITING_FOR_CUSTOMER",
        )

        return (
            "WAITING_FOR_CUSTOMER"
        )

    # ---------------------------------------------------------
    # Customer reply
    # ---------------------------------------------------------

    state["customer_reply"] = reply

    state["status"] = "RUNNING"

    state["current_state"] = (
        "VALIDATE_REPLY"
    )

    runner.transition(
        run_id,
        "VALIDATE_REPLY",
        state,
    )

    # ---------------------------------------------------------
    # Policy grounding
    # ---------------------------------------------------------

    grounding = ground_customer_followup(
        reply
    )

    state["grounding"] = (
        grounding.to_dict()
    )

    state["policies_checked"] = list(
        grounding.policies_checked
    )

    state["policy_evidence"] = list(
        grounding.evidence
    )

    # ---------------------------------------------------------
    # RAG: generate a grounded verdict from the retrieved
    # policy evidence, instead of trusting keyword matching
    # alone. Deterministic fallback keeps prior test behavior
    # unchanged when STATE_GRAPH_USE_REAL_LLM is not set.
    # ---------------------------------------------------------

    rag_result = generate_grounding_verdict(
        query=reply,
        policies_checked=grounding.policies_checked,
        evidence=grounding.evidence,
    )

    rag_verdict = rag_result["verdict"]

    state["grounding_supported"] = (
        rag_verdict.supported
        if rag_result["llm_used"]
        else grounding.supported
    )

    state["rag_llm_used"] = (
        rag_result["llm_used"]
    )

    state["rag_rationale"] = (
        rag_verdict.rationale
    )

    runner.transition(
        run_id,
        "GROUNDING",
        state,
    )

    # ---------------------------------------------------------
    # Constrained ReAct
    # ---------------------------------------------------------

    ticket_id = state.get(
        "ticket_id"
    )

    if ticket_id is None:
        raise ValueError(
            "Customer Follow-up state "
            "has no ticket_id."
        )

    react_result = (
        await run_customer_validation(
            mcp_client,
            int(ticket_id),
            context=(
                f"Customer reply: {reply}\n"
                f"Grounding evidence: "
                f"{state.get('policy_evidence', [])}"
            ),
        )
    )

    state["react_trace"] = (
        react_result.get(
            "steps",
            [],
        )
    )

    state["react_success"] = (
        react_result.get(
            "success",
            False,
        )
    )

    state["react_llm_used"] = (
        react_result.get(
            "llm_used",
            False,
        )
    )

    # ---------------------------------------------------------
    # Extract validated ticket from MCP observation.
    # ---------------------------------------------------------

    validated_ticket = (
        _extract_ticket_from_react(
            react_result
        )
    )

    state["validated_ticket"] = (
        validated_ticket
    )

    # ---------------------------------------------------------
    # Explicit HITL policy.
    # ---------------------------------------------------------

    hitl_required, hitl_reason_codes = (
        _evaluate_hitl_requirement(
            ticket=validated_ticket,
            grounding_supported=(
                state["grounding_supported"]
            ),
            react_success=(
                state["react_success"]
            ),
        )
    )

    state["hitl_required"] = (
        hitl_required
    )

    state["hitl_reason_codes"] = (
        hitl_reason_codes
    )

    # ---------------------------------------------------------
    # MCP / validation failure becomes a failure ticket.
    # ---------------------------------------------------------

    if not react_result["success"]:

        failure_id = runner.fail(
            run_id,
            ticket_id,
            "CONSTRAINED_REACT",
            RuntimeError(
                react_result.get(
                    "error",
                    "Constrained ReAct failed.",
                )
            ),
            state,
        )

        state["failure_id"] = (
            failure_id
        )

        state["status"] = "FAILED"

        state["current_state"] = (
            "FAILED_REACT"
        )

        runner.transition(
            run_id,
            "FAILED_REACT",
            state,
            run_status="FAILED",
        )

        return (
            f"FAILED:{failure_id}"
        )

    # ---------------------------------------------------------
    # HITL required
    # ---------------------------------------------------------

    if hitl_required:

        reason = (
            "Admin validation is required "
            "before resolving the ticket. "
            f"Customer reply: {reply}. "
            f"HITL reasons: "
            f"{', '.join(hitl_reason_codes)}."
        )

        task_id = runner.pause_for_hitl(
            run_id,
            ticket_id,
            reason,
            state,
        )

        state["hitl_task_id"] = (
            task_id
        )

        state["status"] = (
            "WAITING_HITL"
        )

        state["current_state"] = (
            "WAITING_FOR_ADMIN"
        )

        runner.transition(
            run_id,
            "WAITING_FOR_ADMIN",
            state,
            run_status="WAITING_HITL",
        )

        return (
            f"WAITING_HITL:{task_id}"
        )

    # ---------------------------------------------------------
    # Safe autonomous path
    #
    # This path exists for non-high-priority tickets whose
    # grounding and MCP validation are both sufficient.
    # ---------------------------------------------------------

    state["status"] = (
        "RESOLVED"
    )

    state["current_state"] = (
        "RESOLVE"
    )

    runner.transition(
        run_id,
        "RESOLVE",
        state,
        run_status="RESOLVED",
    )

    return "RESOLVE"