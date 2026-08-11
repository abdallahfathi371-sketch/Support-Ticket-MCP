import pytest

from planning.models import Plan, Task


def test_valid_dag_is_accepted():
    plan = Plan(
        goal="Prioritize open support tickets",
        tasks=[
            Task(
                id="t1",
                instruction="Find open high-priority tickets",
            ),
            Task(
                id="t2",
                instruction="Inspect ticket details",
                depends_on=["t1"],
            ),
            Task(
                id="t3",
                instruction="Check relevant support policies",
                depends_on=["t1"],
            ),
            Task(
                id="t4",
                instruction="Produce the final priority order",
                depends_on=["t2", "t3"],
            ),
        ],
    )

    assert plan.topological_order() == [
        "t1",
        "t2",
        "t3",
        "t4",
    ]


def test_parallel_batches_are_dependency_safe():
    plan = Plan(
        goal="Prioritize open support tickets",
        tasks=[
            Task(
                id="t1",
                instruction="Find open high-priority tickets",
            ),
            Task(
                id="t2",
                instruction="Inspect ticket details",
                depends_on=["t1"],
            ),
            Task(
                id="t3",
                instruction="Check support policies",
                depends_on=["t1"],
            ),
            Task(
                id="t4",
                instruction="Produce final priority order",
                depends_on=["t2", "t3"],
            ),
        ],
    )

    assert plan.execution_batches() == [
        ["t1"],
        ["t2", "t3"],
        ["t4"],
    ]


def test_unknown_dependency_is_rejected():
    with pytest.raises(ValueError, match="unknown dependencies"):
        Plan(
            goal="Prioritize open support tickets",
            tasks=[
                Task(
                    id="t1",
                    instruction="Find open tickets",
                    depends_on=["missing_task"],
                )
            ],
        )


def test_self_dependency_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot depend on itself",
    ):
        Plan(
            goal="Prioritize open support tickets",
            tasks=[
                Task(
                    id="t1",
                    instruction="Find open tickets",
                    depends_on=["t1"],
                )
            ],
        )


def test_cycle_is_rejected_before_execution():
    with pytest.raises(
        ValueError,
        match="Cycle detected",
    ):
        Plan(
            goal="Prioritize open support tickets",
            tasks=[
                Task(
                    id="t1",
                    instruction="Find open tickets",
                    depends_on=["t3"],
                ),
                Task(
                    id="t2",
                    instruction="Inspect ticket details",
                    depends_on=["t1"],
                ),
                Task(
                    id="t3",
                    instruction="Check support policies",
                    depends_on=["t2"],
                ),
            ],
        )


def test_terminal_task_is_final_synthesis():
    plan = Plan(
        goal="Prioritize open support tickets",
        tasks=[
            Task(
                id="t1",
                instruction="Find open tickets",
            ),
            Task(
                id="t2",
                instruction="Analyze ticket details",
                depends_on=["t1"],
            ),
            Task(
                id="t3",
                instruction="Produce final priority order",
                depends_on=["t2"],
            ),
        ],
    )

    assert plan.terminal_tasks() == ["t3"]