import pytest

from planning.algorithms.dynamic_decomposition import DynamicDecomposer


class FakeMCPClient:
    async def execute_tool(self, tool_name, arguments):
        assert tool_name == "search_open_tickets"

        return {
            "success": True,
            "count": 3,
            "tickets": [
                {"id": 1, "priority": "High"},
                {"id": 4, "priority": "High"},
                {"id": 10, "priority": "High"},
            ],
        }


@pytest.mark.asyncio
async def test_dynamic_planning_integrates_with_mcp():
    client = FakeMCPClient()
    decomposer = DynamicDecomposer()

    goal = (
        "Find the open tickets, identify the highest priority "
        "tickets, and determine which ticket should be handled first."
    )

    async def execute_task(instruction, previous_outputs):
        text = instruction.lower()

        if (
            "open tickets" in text
            or "retrieve" in text
            or "find" in text
        ):
            result = await client.execute_tool(
                "search_open_tickets",
                {"employee_id": 1},
            )

            return str(result)

        return (
            "The highest priority tickets are 1, 4, and 10. "
            "There is insufficient evidence to select one uniquely."
        )

    result = await decomposer.run(
        goal=goal,
        execute_task=execute_task,
        max_steps=8,
    )

    # --------------------------------------------------------
    # Basic dynamic planning result
    # --------------------------------------------------------

    assert result["success"] is True
    assert result["method"] == "dynamic"

    assert result["steps"] >= 2

    assert (
        len(result["plan"]["tasks"])
        == result["steps"]
    )

    # --------------------------------------------------------
    # First task ID is generated dynamically.
    # Do NOT assume it is "d1".
    # --------------------------------------------------------

    first_task_id = result["plan"]["tasks"][0]["id"]

    assert first_task_id in result["outputs"]

    first_output = result["outputs"][first_task_id]

    # --------------------------------------------------------
    # Verify that the first task actually obtained
    # MCP ticket evidence.
    # --------------------------------------------------------

    assert "tickets" in first_output
    assert "High" in first_output

    # --------------------------------------------------------
    # Verify the first task has no dependencies.
    # --------------------------------------------------------

    first_task = result["plan"]["tasks"][0]

    assert first_task["depends_on"] == []

    # --------------------------------------------------------
    # Verify that later tasks depend on previously
    # executed tasks.
    # --------------------------------------------------------

    for task in result["plan"]["tasks"][1:]:
        for dependency in task["depends_on"]:
            assert dependency in result["outputs"]


@pytest.mark.asyncio
async def test_dynamic_decomposition_reacts_to_observation():
    decomposer = DynamicDecomposer()

    generated_tasks = []

    def fake_next_task(goal, previous_outputs):
        from planning.algorithms.dynamic_decomposition import (
            DynamicTask,
        )

        # ----------------------------------------------------
        # First task: collect evidence
        # ----------------------------------------------------

        if not previous_outputs:

            task = DynamicTask(
                task_id="t1",
                instruction="Retrieve all open tickets",
                depends_on=[],
                is_final=False,
            )

        # ----------------------------------------------------
        # Second task changes according to the observation
        # ----------------------------------------------------

        else:

            observation = str(
                previous_outputs[
                    list(previous_outputs.keys())[-1]
                ]
            )

            if "urgent" in observation.lower():

                task = DynamicTask(
                    task_id="t2",
                    instruction="Analyze urgent tickets first",
                    depends_on=[
                        list(previous_outputs.keys())[-1]
                    ],
                    is_final=False,
                )

            else:

                task = DynamicTask(
                    task_id="t2",
                    instruction="Analyze highest priority tickets",
                    depends_on=[
                        list(previous_outputs.keys())[-1]
                    ],
                    is_final=False,
                )

        generated_tasks.append(task)

        return task

    # Replace the LLM-generated next-task function with a
    # deterministic test version.
    decomposer.next_task = fake_next_task

    async def execute_task(
        instruction,
        previous_outputs,
    ):

        if instruction == "Retrieve all open tickets":

            return "Ticket 7 is marked URGENT."

        return "Urgent ticket detected and prioritized."

    result = await decomposer.run(
        goal="Determine which ticket should be handled first.",
        execute_task=execute_task,
        max_steps=2,
    )

    # --------------------------------------------------------
    # Verify that dynamic planning actually reacted to the
    # first observation.
    # --------------------------------------------------------

    assert result["steps"] == 2

    assert (
        result["plan"]["tasks"][0]["instruction"]
        == "Retrieve all open tickets"
    )

    assert (
        result["plan"]["tasks"][1]["instruction"]
        == "Analyze urgent tickets first"
    )

    # --------------------------------------------------------
    # Verify dependency chain.
    # --------------------------------------------------------

    assert (
        result["plan"]["tasks"][1]["depends_on"]
        == ["t1"]
    )

    # --------------------------------------------------------
    # Verify the observation caused the change of course.
    # --------------------------------------------------------

    assert "URGENT" in result["outputs"]["t1"]
