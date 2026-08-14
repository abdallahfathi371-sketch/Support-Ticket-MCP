from __future__ import annotations

import time
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from .environment import Environment


def self_refine(
    draft: str,
    rubric: str,
    llm: BaseChatModel,
    validator: Optional[Environment] = None,
    max_revisions: int = 1,
) -> str:
    """
    Self-Refine loop: one draft -> explicit critique against rubric (grounded when possible) -> one revision.

    - draft: initial output to improve
    - rubric: explicit checklist-style rubric the critique should follow
    - llm: LangChain-compatible chat model (Groq wrapper)
    - validator: optional Environment evaluator for grounding (will be called and its output included in critique)
    - max_revisions: number of revision attempts (1 per the lab requirement)
    """

    if not draft or not draft.strip():
        raise ValueError("Draft cannot be empty")

    # Step 1: generate critique
    critique_prompt = (
        "You are a focused critic. Evaluate the provided DRAFT against the following RUBRIC. "
        "If a grounded validator is available, consult it and include any concrete failures.\n\n"
        f"RUBRIC:\n{rubric}\n\n"
        f"DRAFT:\n{draft}\n\n"
        "Produce a JSON object with fields: 'passed' (bool), 'issues' (list of strings), and 'advice' (short actionable guidance). "
        "If everything passes, set 'passed' to true and provide an empty issues list and concise advice."
    )

    critique_response = llm.invoke([
        ("system", "You are a structured critic for Self-Refine."),
        ("human", critique_prompt),
    ])

    # Accept string response; try to find issues in the response text.
    critique_text = None
    try:
        critique_text = (
            critique_response.content
            if hasattr(critique_response, "content")
            else str(critique_response)
        )
    except Exception:
        critique_text = str(critique_response)

    # Grounded check using validator if available: call validator.evaluate on the draft
    grounded_details = []
    grounded_score = None
    if validator is not None:
        try:
            feedback = validator.evaluate(draft)
            grounded_score = feedback.score
            grounded_details = feedback.details or []
        except Exception as exc:
            grounded_details = [f"Validator error: {exc}"]

    # If grounded details show clear failures, fold them into the critique 'issues'
    # Compose revision prompt
    revision_prompt = (
        "You are producing a REVISED draft based on the original DRAFT and the CRITIQUE. "
        "Follow the ADVICE and fix listed ISSUES. If grounded validator details are provided, address them specifically. "
        "Return only the revised draft text (no JSON).\n\n"
        f"ORIGINAL DRAFT:\n{draft}\n\n"
        f"CRITIQUE:\n{critique_text}\n\n"
    )

    if grounded_details:
        revision_prompt += "GROUNDING_DETAILS:\n" + "\n".join(grounded_details) + "\n\n"

    revision_prompt += f"RUBRIC:\n{rubric}\n\n"

    # Perform revision(s)
    revised = draft
    for _ in range(max_revisions):
        revised_resp = llm.invoke([
            ("system", "You are a careful editor implementing the Self-Refine revision."),
            ("human", revision_prompt),
        ])

        try:
            revised_text = (
                revised_resp.content
                if hasattr(revised_resp, "content")
                else str(revised_resp)
            )
        except Exception:
            revised_text = str(revised_resp)

        if revised_text and revised_text.strip() and revised_text.strip() != revised.strip():
            revised = revised_text.strip()
            break

    # Final pass: if validator exists, ensure the revised output passes grounding when possible
    if validator is not None:
        try:
            final_feedback = validator.evaluate(revised)
            if not final_feedback.success:
                # Append an explicit note to the revised output summarizing validator feedback
                revised = revised + "\n\n[Grounding notes]: " + "; ".join(final_feedback.details)
        except Exception:
            pass

    return revised
