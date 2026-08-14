from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from langchain_core.language_models.chat_models import BaseChatModel

from .environment import Environment


class ReflexionResult:
    def __init__(self, success: bool, output: str, reflections: List[str]):
        self.success = success
        self.output = output
        self.reflections = reflections


def reflexion(
    trial_fn: Callable[[Optional[List[str]]], Tuple[bool, str]],
    llm: BaseChatModel,
    validator: Environment | None = None,
    trials: int = 3,
    buffer_size: int = 5,
) -> ReflexionResult:
    """
    Reflexion orchestration.

    - trial_fn(reflections) -> (success: bool, output: str)
      trial_fn runs a single attempt given previous reflections (list of strings) and returns success bool and its output.
    - llm: model to generate reflections
    - validator: environment evaluator to produce grounded feedback
    - trials: max number of trials
    - buffer_size: capped episodic buffer length of reflections passed to subsequent trials

    Returns best output and the collected reflections.
    """

    reflections: List[str] = []
    best_output = ""
    best_success = False

    for i in range(1, trials + 1):
        # Call trial function with the current reflections
        success, output = trial_fn(list(reflections))

        # If validator provided, evaluate output
        feedback = None
        if validator is not None:
            try:
                feedback = validator.evaluate(output)
            except Exception:
                feedback = None

        if success and (feedback is None or feedback.success):
            # success
            best_output = output
            best_success = True
            reflections.append(f"Trial {i}: success")
            break

        # Otherwise create a verbal reflection using the llm that references the failure
        lesson_prompt = (
            "You are a reflective critic. The previous attempt failed or was insufficient.\n\n"
            f"Attempt output:\n{output}\n\n"
        )

        if feedback is not None:
            lesson_prompt += "Validator feedback:\n" + "\n".join(feedback.details or []) + "\n\n"

        if reflections:
            lesson_prompt += "Previous reflections:\n" + "\n".join(reflections[-buffer_size:]) + "\n\n"

        lesson_prompt += (
            "Provide a concise reflection that explains why the attempt failed and concrete changes to try next. "
            "Return the reflection as a single short paragraph."
        )

        resp = llm.invoke([
            ("system", "You are Reflexion's reflection generator."),
            ("human", lesson_prompt),
        ])

        reflection_text = None
        try:
            reflection_text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception:
            reflection_text = str(resp)

        reflection_text = (reflection_text or "").strip()

        if not reflection_text:
            reflection_text = "No useful reflection generated."

        # Append the reflection to the buffer (capped)
        reflections.append(f"Trial {i}: {reflection_text}")
        if len(reflections) > buffer_size:
            reflections = reflections[-buffer_size:]

        # Use reflection to influence next trial: trial_fn is expected to accept reflections and change behavior
        # Continue to next trial

    return ReflexionResult(best_success, best_output, reflections)
