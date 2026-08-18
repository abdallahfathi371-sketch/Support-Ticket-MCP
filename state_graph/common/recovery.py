from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RecoveryCandidate:
    strategy: str
    score: float
    reason: str


class LATSRecoverySelector:
    """
    Lightweight LATS-style recovery selector.

    Generates multiple recovery candidates, evaluates them, and
    selects the highest-scoring safe strategy.
    """

    STRATEGIES = (
        "retry_same_action",
        "refresh_checkpoint",
        "alternative_action",
        "escalate_to_admin",
    )

    def generate_candidates(
        self,
        *,
        error_type: str,
        attempt: int,
        action_retryable: bool,
        alternative_available: bool,
    ) -> list[RecoveryCandidate]:

        candidates: list[RecoveryCandidate] = []

        if action_retryable and attempt < 2:
            candidates.append(
                RecoveryCandidate(
                    strategy="retry_same_action",
                    score=0.70,
                    reason=(
                        "The action is retryable and the attempt "
                        "limit has not been reached."
                    ),
                )
            )

        candidates.append(
            RecoveryCandidate(
                strategy="refresh_checkpoint",
                score=0.80,
                reason=(
                    "Refreshing from the latest durable checkpoint "
                    "avoids relying on stale in-memory state."
                ),
            )
        )

        if alternative_available:
            candidates.append(
                RecoveryCandidate(
                    strategy="alternative_action",
                    score=0.85,
                    reason=(
                        "An alternative safe action is available "
                        "for the failed operation."
                    ),
                )
            )

        candidates.append(
            RecoveryCandidate(
                strategy="escalate_to_admin",
                score=0.90,
                reason=(
                    f"Failure type '{error_type}' may require "
                    "human investigation before continuing."
                ),
            )
        )

        return candidates

    def select(
        self,
        *,
        error_type: str,
        attempt: int,
        action_retryable: bool = False,
        alternative_available: bool = False,
    ) -> RecoveryCandidate:

        candidates = self.generate_candidates(
            error_type=error_type,
            attempt=attempt,
            action_retryable=action_retryable,
            alternative_available=alternative_available,
        )

        if not candidates:
            raise RuntimeError(
                "No recovery candidates were generated"
            )

        return max(
            candidates,
            key=lambda candidate: candidate.score,
        )