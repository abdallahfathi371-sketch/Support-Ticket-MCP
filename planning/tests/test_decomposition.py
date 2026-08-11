from planning.algorithms.decomposition import decompose_goal
from planning.models import Plan


class FakeStructuredModel:
    def __init__(self, generated):
        self.generated = generated

    def with_structured_output(self, *args, **kwargs):
        return self

    def invoke(self, *args, **kwargs):
        return self.generated


class FakeLLM:
    def __init__(self, generated):
        self.generated = generated

    def with_structured_output(self, *args, **kwargs):
        return FakeStructuredModel(self.generated)


def test_decompose_goal_returns_valid_plan():

    generated = type(
        "Generated",
        (),
        {
            "model_dump": lambda self: {
                "goal": "wrong goal",
                "tasks": [
                    {
                        "id": "t1",
                        "instruction": "Find open high-priority tickets",
                        "depends_on": [],
                    },
                    {
                        "id": "t2",
                        "instruction": "Inspect ticket details",
                        "depends_on": ["t1"],
                    },
                    {
                        "id": "t3",
                        "instruction": "Check support policies",
                        "depends_on": ["t1"],
                    },
                    {
                        "id": "t4",
                        "instruction": "Produce final priority order",
                        "depends_on": ["t2", "t3"],
                    },
                ],
            }
        },
    )()

    llm = FakeLLM(generated)

    goal = (
        "Analyze open high-priority support tickets "
        "and determine which should be handled first."
    )

    plan = decompose_goal(goal, llm)

    assert isinstance(plan, Plan)

    assert plan.goal == goal

    assert plan.execution_batches() == [
        ["t1"],
        ["t2", "t3"],
        ["t4"],
    ]

    assert plan.terminal_tasks() == ["t4"]
