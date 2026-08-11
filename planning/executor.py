from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from .models import Plan


load_dotenv()


MODEL_NAME = "llama-3.3-70b-versatile"


def get_groq_client() -> Groq:
    """
    Create the Groq client using GROQ_API_KEY from .env.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set in the environment."
        )

    return Groq(api_key=api_key)


def ask_groq(prompt: str) -> str:
    """
    Use Groq for reasoning and synthesis tasks.

    This function must only reason over supplied evidence.
    It must not invent company data.
    """

    client = get_groq_client()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a support-ticket planning assistant. "
                    "Use only the information supplied in the prompt. "
                    "Never invent ticket data, priorities, statuses, "
                    "customers, teams, or database results."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return content.strip()


def _extract_ticket_id(instruction: str) -> int | None:
    """
    Extract an explicitly mentioned ticket ID.

    Examples:
        ticket 5
        ticket #5
        ticket id 5
        ticket ID: 5
    """

    patterns = [
        r"ticket\s+#?\s*(\d+)",
        r"ticket\s+id\s*[:=]?\s*(\d+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            instruction,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

    return None


def _extract_team_name(instruction: str) -> str | None:
    """
    Extract a known team name from the instruction.

    This is deliberately restricted to the teams that exist
    in the current Support-Ticket project.
    """

    known_teams = {
        "backend",
        "frontend",
        "support",
        "product",
    }

    text = instruction.lower()

    for team in known_teams:

        if team in text:
            return team

    return None


async def _execute_mcp_operation(
    instruction: str,
    mcp_client,
) -> str | None:
    """
    Route a deterministic task to an existing MCP operation.

    Returns None when the instruction requires reasoning rather
    than a deterministic MCP call.
    """

    text = instruction.lower()

    # =========================================================
    # SEARCH OPEN TICKETS
    # =========================================================

    if (
        "open tickets" in text
        or "open support tickets" in text
        or "all open ticket" in text
        or "search open ticket" in text
        or "retrieve open ticket" in text
    ):

        result = await mcp_client.search_open_tickets()

        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # =========================================================
    # GET SPECIFIC TICKET
    # =========================================================

    ticket_id = _extract_ticket_id(instruction)

    if ticket_id is not None and (
        "get" in text
        or "retrieve" in text
        or "inspect" in text
        or "look up" in text
        or "details" in text
    ):

        result = await mcp_client.get_ticket(
            ticket_id
        )

        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # =========================================================
    # SEARCH BY TEAM
    # =========================================================

    team_name = _extract_team_name(instruction)

    if team_name is not None and (
        "team" in text
        or "assigned" in text
    ):

        result = await mcp_client.search_by_team(
            team_name
        )

        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # =========================================================
# DASHBOARD
# =========================================================

    if (
        "dashboard" in text
        or "ticket dashboard" in text
        or "support workload" in text
        or "workload" in text
):
      result = await mcp_client.get_dashboard()

    return json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    # =========================================================
    # REPORT
    # =========================================================

    if (
        "generate report" in text
        or "ticket report" in text
    ):

        result = await mcp_client.generate_report()

        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # =========================================================
    # UPDATE STATUS
    # =========================================================

    if (
        "update" in text
        and "status" in text
        and ticket_id is not None
    ):

        status = None

        if "closed" in text:
            status = "Closed"

        elif "pending" in text:
            status = "Pending"

        elif "open" in text:
            status = "Open"

        if status is not None:

            result = await mcp_client.update_ticket_status(
                ticket_id,
                status,
            )

            return json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

    # No deterministic MCP mapping.
    return None


async def execute_task(
    task_id: str,
    instruction: str,
    context: dict[str, str],
    mcp_client,
) -> str:
    """
    Execute one DAG task.

    Deterministic company-data operations are sent to the
    existing MCP server.

    Reasoning tasks are handled by Groq using the evidence
    returned by previous tasks.
    """

    mcp_result = await _execute_mcp_operation(
        instruction=instruction,
        mcp_client=mcp_client,
    )

    if mcp_result is not None:
        return mcp_result

    context_text = json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    prompt = f"""
You are executing one task inside a validated
support-ticket planning DAG.

Overall task:

{instruction}

Evidence from prerequisite tasks:

{context_text}

Complete only the current task.

Rules:

1. Use ONLY the evidence provided above.
2. Do not invent tickets.
3. Do not invent priorities.
4. Do not invent customer information.
5. Do not invent team assignments.
6. Do not invent database results.
7. If the available evidence is insufficient, say so explicitly.
8. Return a concise but useful analysis.
"""

    return ask_groq(prompt)


async def execute_plan(
    plan: Plan,
    mcp_client,
) -> dict[str, str]:
    """
    Execute the validated DAG in dependency-safe batches.

    Independent tasks in the same batch execute concurrently.
    """

    outputs: dict[str, str] = {}

    for batch in plan.execution_batches():

        print(
            f"\n[Planning] Executing batch: {batch}"
        )

        async def run_task(
            task_id: str,
        ) -> tuple[str, str]:

            task = plan.task(task_id)

            context = {
                dependency: outputs[dependency]
                for dependency in task.depends_on
            }

            result = await execute_task(
                task_id=task.id,
                instruction=task.instruction,
                context=context,
                mcp_client=mcp_client,
            )

            return task_id, result

        results = await asyncio.gather(
            *(
                run_task(task_id)
                for task_id in batch
            )
        )

        for task_id, result in results:

            outputs[task_id] = result

            print(
                f"[Planning] Completed {task_id}"
            )

    return outputs


def synthesize_plan(
    plan: Plan,
    outputs: dict[str, str],
) -> str:
    """
    Produce the final answer from the complete execution trace.
    """

    terminal_tasks = plan.terminal_tasks()

    if len(terminal_tasks) != 1:
        raise ValueError(
            "Expected exactly one terminal synthesis task, "
            f"found: {terminal_tasks}"
        )

    terminal_id = terminal_tasks[0]

    all_outputs = json.dumps(
        outputs,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    prompt = f"""
You are producing the final answer for this
support-ticket request:

{plan.goal}

Terminal synthesis task:

{plan.task(terminal_id).instruction}

Execution results:

{all_outputs}

Produce the final answer.

Requirements:

1. Answer the original request directly.
2. Use only retrieved and analyzed information.
3. Mention relevant ticket IDs when available.
4. Explain the reasoning behind the result.
5. Never invent missing information.
6. Clearly state uncertainty when evidence is insufficient.
7. Keep the answer concise but useful.
"""

    return ask_groq(prompt)


async def run_planning(
    goal: str,
    mcp_client,
) -> dict[str, Any]:
    """
    Complete decomposition-first planning workflow.

    1. Generate the DAG using the reference decomposition algorithm.
    2. Validate it using Pydantic + NetworkX.
    3. Execute it in dependency-safe batches.
    4. Synthesize the final result.
    """

    from .planner import create_plan

    print("\n[Planning] Creating DAG...")

    plan = create_plan(goal)

    print("\n[Planning] DAG created:")

    print(
        json.dumps(
            plan.model_dump(),
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        "\n[Planning] Execution batches:",
        plan.execution_batches(),
    )

    outputs = await execute_plan(
        plan=plan,
        mcp_client=mcp_client,
    )

    print(
        "\n[Planning] Synthesizing final answer..."
    )

    final_answer = synthesize_plan(
        plan=plan,
        outputs=outputs,
    )

    return {
        "success": True,
        "goal": goal,
        "plan": plan.model_dump(),
        "outputs": outputs,
        "final_output": final_answer,
    }