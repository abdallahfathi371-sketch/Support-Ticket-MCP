from __future__ import annotations

from dataclasses import dataclass

from ..common.llm_reasoning import (
    generate_lats_plan,
)


@dataclass(frozen=True)
class LATSRecoveryCandidate:
    strategy: str
    score: float
    reason: str
    llm_used: bool = False


RecoveryCandidate = LATSRecoveryCandidate


class LATSRecoverySelector:
    """
    LATS-style recovery strategy selector.

    In real mode:
        LLM generates multiple candidates -> highest safe score.

    In test/local mode:
        deterministic candidates are used.
    """

    def select(
        self,
        *,
        error_type: str,
        attempt: int,
        action_retryable: bool = False,
        alternative_available: bool = False,
    ) -> LATSRecoveryCandidate:

        context = (
            f"Error type: {error_type}\n"
            f"Attempt: {attempt}\n"
            f"Action retryable: {action_retryable}\n"
            f"Alternative available: {alternative_available}"
        )

        result = generate_lats_plan(
            context=context
        )

        candidates = result["plan"].candidates

        # Safety gate:
        # do not select retry unless the action is actually retryable.
        filtered = []

        for candidate in candidates:

            if (
                candidate.strategy == "retry"
                and not action_retryable
            ):
                continue

            if (
                candidate.strategy == "alternative_action"
                and not alternative_available
            ):
                continue

            filtered.append(
                candidate
            )

        # Human escalation is always a valid fallback.
        if not filtered:
            return LATSRecoveryCandidate(
                strategy="escalate_to_admin",
                score=0.90,
                reason=(
                    "No automatically safe recovery action was "
                    "available; administrator review is required."
                ),
                llm_used=result["llm_used"],
            )

        selected = max(
            filtered,
            key=lambda item: item.score,
        )

        return LATSRecoveryCandidate(
            strategy=selected.strategy,
            score=selected.score,
            reason=selected.rationale,
            llm_used=result["llm_used"],
        )