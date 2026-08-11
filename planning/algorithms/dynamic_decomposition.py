from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable

from groq import Groq

from planning.models import Plan


# ============================================================
# Dynamic Decomposition System Prompt
# ============================================================

DYNAMIC_SYSTEM_PROMPT = """
You are a dynamic task-decomposition planner for a support-ticket
management system.

Your job is to decide the NEXT executable task after observing the
result of the previous task.

This is NOT a fixed plan.

Execution pattern:

    observe previous result
            ↓
    generate ONE next task
            ↓
    execute task
            ↓
    observe result
            ↓
    generate ONE next task
            ↓
           ...

Rules:

1. Generate exactly ONE next task at a time.

2. The next task MUST be based on:
   - the original user goal
   - all observations from previous tasks

3. If an observation changes the situation, change course.

4. Never assume that an earlier plan is still valid after a failure.

5. Never invent:
   - ticket IDs
   - ticket data
   - customer information
   - priorities
   - creation dates
   - team assignments
   - policies
   - database facts

6. Use existing MCP tools when real company information is required.

7. A task must have a concrete purpose.

8. Do NOT repeat an MCP retrieval if the required information
   is already present in previous observations.

9. Analysis tasks should analyze previous observations rather than
   retrieve the same information again.

10. If previous observations already contain enough evidence to answer
    the original user goal, the NEXT task MUST be a final synthesis task.

11. Do NOT create another analysis task after enough evidence has
    already been collected.

12. The final synthesis task MUST:
    - use previous observations
    - answer the original user goal
    - not invent missing information
    - not retrieve the same information again
    - have is_final=true

13. If multiple tickets have the same highest priority and there is
    no valid tie-breaker in the evidence, the final answer must state
    that a unique ticket cannot safely be selected.

14. Task IDs must be unique.

15. Every dependency must refer only to an already executed task.

16. Return JSON only.

17. Never wrap the JSON in Markdown fences.

18. The response MUST contain exactly these fields:
    - id
    - instruction
    - depends_on
    - is_final
"""


# ============================================================
# Dynamic Task
# ============================================================

class DynamicTask:
    """
    Represents one dynamically generated task.

    Dynamic tasks are generated one at a time during execution.
    """

    def __init__(
        self,
        task_id: str,
        instruction: str,
        depends_on: list[str] | None = None,
        is_final: bool = False,
    ):
        self.id = task_id
        self.instruction = instruction
        self.depends_on = depends_on or []
        self.is_final = is_final

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "depends_on": self.depends_on,
            "is_final": self.is_final,
        }


# ============================================================
# Dynamic Decomposer
# ============================================================

class DynamicDecomposer:
    """
    Dynamic/interleaved decomposition.

    Unlike decomposition-first planning, the complete DAG is NOT
    generated before execution.

    Instead:

        goal
          ↓
        generate next task
          ↓
        execute
          ↓
        observe
          ↓
        generate next task
          ↓
        ...

    This allows observations to influence future tasks.
    """

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
    ):
        self.model = model

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set in the environment."
            )

        self.client = Groq(
            api_key=api_key
        )

    # ========================================================
    # Ask LLM for next task
    # ========================================================

    def _ask_next_task(
        self,
        goal: str,
        previous_outputs: dict[str, str],
        task_counter: int,
    ) -> DynamicTask:
        """
        Ask the LLM to generate exactly one next task.
        """

        history = json.dumps(
            previous_outputs,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        if previous_outputs:
            observation_text = history
        else:
            observation_text = "No tasks have been executed yet."

        prompt = f"""
Original user goal:

{goal}

Tasks already executed and their observations:

{observation_text}

Executed task IDs:

{list(previous_outputs.keys())}

Now generate the NEXT task.

Important:

- Generate exactly ONE task.
- The task must react to the observations.
- Do not repeat an MCP retrieval when the required data already
  exists in the observations.
- If the previous observations contain enough evidence to answer
  the original goal, generate a FINAL SYNTHESIS task.
- If you generate a final synthesis task, is_final MUST be true.
- A final synthesis task should depend on all relevant previous tasks.
- If evidence is insufficient, generate the next evidence-gathering
  or analysis task instead.

For the first task:

{{
    "id": "d{task_counter}",
    "instruction": "Concrete task that retrieves the required evidence",
    "depends_on": [],
    "is_final": false
}}

For an analysis task:

{{
    "id": "d{task_counter}",
    "instruction": "Analyze the previous task output...",
    "depends_on": ["previous_task_id"],
    "is_final": false
}}

For a final synthesis task:

{{
    "id": "d{task_counter}",
    "instruction": "Synthesize the final answer using the previous evidence...",
    "depends_on": ["all_required_previous_tasks"],
    "is_final": true
}}

Return ONLY valid JSON.

Do not return explanations.
Do not return Markdown.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": DYNAMIC_SYSTEM_PROMPT,
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
                "Groq returned an empty dynamic-decomposition response."
            )

        content = content.strip()

        # ----------------------------------------------------
        # Remove accidental Markdown fences
        # ----------------------------------------------------

        if content.startswith("```"):
            lines = content.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            content = "\n".join(lines).strip()

        # ----------------------------------------------------
        # Handle JSON surrounded by text
        # ----------------------------------------------------

        if not content.startswith("{"):
            start = content.find("{")
            end = content.rfind("}")

            if start != -1 and end != -1 and end > start:
                content = content[start:end + 1]

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        try:
            data = json.loads(content)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Dynamic decomposition returned invalid JSON:\n"
                f"{content}"
            ) from exc

        # ----------------------------------------------------
        # Validate structure
        # ----------------------------------------------------

        required = {
            "id",
            "instruction",
            "depends_on",
            "is_final",
        }

        missing = required - set(data)

        if missing:
            raise RuntimeError(
                "Dynamic decomposition response is missing fields: "
                f"{sorted(missing)}"
            )

        if not isinstance(data["id"], str):
            raise RuntimeError(
                "Dynamic task 'id' must be a string."
            )

        if not isinstance(data["instruction"], str):
            raise RuntimeError(
                "Dynamic task 'instruction' must be a string."
            )

        if not isinstance(data["depends_on"], list):
            raise RuntimeError(
                "Dynamic task 'depends_on' must be a list."
            )

        return DynamicTask(
            task_id=data["id"],
            instruction=data["instruction"],
            depends_on=data["depends_on"],
            is_final=bool(data["is_final"]),
        )

    # ========================================================
    # Validate dependencies
    # ========================================================

    @staticmethod
    def _validate_dependencies(
        task: DynamicTask,
        executed_ids: set[str],
    ) -> None:
        """
        Dynamic tasks may depend only on already executed tasks.

        This prevents forward dependencies and cycles.
        """

        unknown = set(task.depends_on) - executed_ids

        if unknown:
            raise ValueError(
                f"Dynamic task {task.id} has invalid dependencies: "
                f"{sorted(unknown)}"
            )

        if task.id in task.depends_on:
            raise ValueError(
                f"Dynamic task {task.id} cannot depend on itself."
            )

    # ========================================================
    # Build final Plan
    # ========================================================

    @staticmethod
    def build_plan(
        goal: str,
        tasks: list[DynamicTask],
    ) -> Plan:
        """
        Convert the dynamic execution trace into the normal Plan model.
        """

        return Plan.model_validate(
            {
                "goal": goal,
                "tasks": [
                    {
                        "id": task.id,
                        "instruction": task.instruction,
                        "depends_on": task.depends_on,
                    }
                    for task in tasks
                ],
            }
        )

    # ========================================================
    # Generate next task
    # ========================================================

    def next_task(
        self,
        goal: str,
        previous_outputs: dict[str, str],
    ) -> DynamicTask:
        """
        Generate the next task after observing previous results.
        """

        task_counter = len(previous_outputs) + 1

        task = self._ask_next_task(
            goal=goal,
            previous_outputs=previous_outputs,
            task_counter=task_counter,
        )

        self._validate_dependencies(
            task,
            set(previous_outputs.keys()),
        )

        return task

    # ========================================================
    # Run Dynamic Planning
    # ========================================================

    async def run(
        self,
        goal: str,
        execute_task: Callable[
            [str, dict[str, str]],
            Awaitable[str],
        ],
        max_steps: int = 8,
    ) -> dict[str, Any]:
        """
        Execute dynamic decomposition.

        execute_task must be an async callable:

            await execute_task(
                instruction,
                previous_outputs
            )

        The planner generates one task, executes it, observes its
        result, and then generates the next task.

        Reaching max_steps after successfully executing the last task
        is NOT automatically a failure. This is important for tests
        and bounded dynamic workflows where the caller intentionally
        limits the number of steps.
        """

        if max_steps < 1:
            raise ValueError(
                "max_steps must be at least 1."
            )

        tasks: list[DynamicTask] = []

        outputs: dict[str, str] = {}

        terminated_by_limit = False

        for step_index in range(max_steps):

            task = self.next_task(
                goal=goal,
                previous_outputs=outputs,
            )

            # ------------------------------------------------
            # Prevent duplicate IDs
            # ------------------------------------------------

            existing_ids = {
                existing.id
                for existing in tasks
            }

            if task.id in existing_ids:
                raise RuntimeError(
                    "Dynamic planner generated duplicate task ID: "
                    f"{task.id}"
                )

            # ------------------------------------------------
            # Validate dependencies again before execution
            # ------------------------------------------------

            self._validate_dependencies(
                task,
                set(outputs.keys()),
            )

            tasks.append(task)

            print(
                f"\n[Dynamic Planning] Generated {task.id}: "
                f"{task.instruction}"
            )

            print(
                "[Dynamic Planning] Dependencies:",
                task.depends_on,
            )

            # ------------------------------------------------
            # Execute task
            # ------------------------------------------------

            result = await execute_task(
                task.instruction,
                outputs,
            )

            outputs[task.id] = str(result)

            print(
                f"[Dynamic Planning] Observation received for "
                f"{task.id}"
            )

            # ------------------------------------------------
            # Stop at final task
            # ------------------------------------------------

            if task.is_final:
                break

            # ------------------------------------------------
            # If this was the last allowed step, terminate
            # cleanly instead of raising an error.
            # ------------------------------------------------

            if step_index == max_steps - 1:
                terminated_by_limit = True

        # ----------------------------------------------------
        # Build validated plan
        # ----------------------------------------------------

        plan = self.build_plan(
            goal=goal,
            tasks=tasks,
        )

        return {
            "success": True,
            "method": "dynamic",
            "goal": goal,
            "plan": plan.model_dump(),
            "outputs": outputs,
            "steps": len(tasks),
            "terminated_by_limit": terminated_by_limit,
            "completed_with_final_task": bool(
                tasks and tasks[-1].is_final
            ),
        }