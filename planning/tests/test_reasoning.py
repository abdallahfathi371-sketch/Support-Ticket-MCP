"""
Reasoning tests for the Coderift Support Ticket planning agent.

These tests execute the fixed reasoning cases against:

- Plan-and-Solve
- Tree of Thoughts
- LATS

LATS uses the grounded Environment connected to the real ticket database.
"""

import pytest

from planning.groq_model import GroqChatModel

from planning.algorithms.plan_and_solve import plan_and_solve
from planning.algorithms.tree_of_thoughts import tree_of_thoughts
from planning.algorithms.lats import lats
from planning.algorithms.environment import Environment

from planning.tests.reasoning_cases import REASONING_CASES


@pytest.fixture(scope="module")
def llm():
    return GroqChatModel()


@pytest.fixture(scope="module")
def environment():
    return Environment()


# ============================================================
# PLAN-AND-SOLVE
# ============================================================

@pytest.mark.parametrize("case", REASONING_CASES)
def test_plan_and_solve(case, llm):
    """Run every fixed reasoning case through Plan-and-Solve."""

    result = plan_and_solve(
        case["prompt"],
        llm,
    )

    assert isinstance(result, str)
    assert result.strip()

    print("\n" + "=" * 70)
    print(f"CASE: {case['id']} - {case['name']}")
    print("METHOD: Plan-and-Solve")
    print("=" * 70)
    print(result)


# ============================================================
# TREE OF THOUGHTS
# ============================================================

@pytest.mark.parametrize("case", REASONING_CASES)
def test_tree_of_thoughts(case, llm):
    """Run every fixed reasoning case through Tree of Thoughts."""

    result = tree_of_thoughts(
        problem=case["prompt"],
        llm=llm,
        depth=2,
        beam_width=2,
    )

    assert isinstance(result, list)
    assert result
    assert len(result) <= 2

    for thought in result:
        assert thought.state
        assert 0.0 <= thought.score <= 1.0
        assert thought.rationale

    print("\n" + "=" * 70)
    print(f"CASE: {case['id']} - {case['name']}")
    print("METHOD: Tree of Thoughts")
    print("=" * 70)

    for index, thought in enumerate(result, start=1):
        print(f"\nCandidate {index}")
        print(f"State: {thought.state}")
        print(f"Score: {thought.score}")
        print(f"Rationale: {thought.rationale}")


# ============================================================
# LATS
# ============================================================

@pytest.mark.parametrize("case", REASONING_CASES)
def test_lats(case, llm, environment):
    """Run every fixed reasoning case through grounded LATS."""

    result = lats(
        task=case["prompt"],
        llm=llm,
        environment=environment,
        iterations=2,
        n_actions=2,
    )

    assert result is not None
    assert isinstance(result.success, bool)
    assert isinstance(result.output, str)
    assert result.output.strip()

    assert 0.0 <= result.best_score <= 1.0
    assert result.iterations >= 1
    assert result.root is not None

    print("\n" + "=" * 70)
    print(f"CASE: {case['id']} - {case['name']}")
    print("METHOD: LATS")
    print("=" * 70)

    print(f"Success: {result.success}")
    print(f"Best score: {result.best_score}")
    print(f"Iterations: {result.iterations}")
    print(f"Best output: {result.output}")

    print("\nLATS TREE")

    for child in result.root.children:
        print(f"\nAction: {child.action}")
        print(f"State: {child.state}")
        print(f"Visits: {child.visits}")
        print(f"Environment score: {child.environment_score}")
        print(f"Model score: {child.model_score}")
        print(f"Feedback: {child.feedback}")
        print(f"Reflections: {child.reflections}")