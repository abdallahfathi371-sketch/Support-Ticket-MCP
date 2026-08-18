from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_POLICY_FILES = (
    "ticket_policy.txt",
    "sla_policy.txt",
    "security_policy.txt",
)


@dataclass
class GroundingResult:
    """
    Deterministic grounding result against company policies.
    """

    query: str
    policies_checked: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    supported: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "policies_checked": list(self.policies_checked),
            "evidence": list(self.evidence),
            "supported": self.supported,
            "warnings": list(self.warnings),
        }


class PolicyGrounder:
    """
    Deterministic policy grounding layer.

    It loads the existing company policy files and stores
    inspectable evidence in the graph state.
    """

    def __init__(
        self,
        policy_dir: str | Path | None = None,
    ):
        if policy_dir is None:
            policy_dir = (
                Path(__file__).resolve().parents[2]
                / "mcp_server"
                / "policies"
            )

        self.policy_dir = Path(policy_dir)

    def load_policy(
        self,
        filename: str,
    ) -> dict[str, Any]:
        path = self.policy_dir / filename

        if not path.exists() or not path.is_file():
            return {
                "name": filename,
                "found": False,
                "content": "",
            }

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            return {
                "name": filename,
                "found": False,
                "content": "",
                "error": str(exc),
            }

        return {
            "name": filename,
            "found": True,
            "content": content,
        }

    def load_policies(
        self,
        policy_files: tuple[str, ...] = DEFAULT_POLICY_FILES,
    ) -> dict[str, dict[str, Any]]:
        return {
            filename: self.load_policy(filename)
            for filename in policy_files
        }

    @staticmethod
    def _extract_evidence(
        content: str,
        query: str,
    ) -> list[str]:
        """
        Deterministic evidence selection.

        We prefer lines containing terms related to the query.
        When no direct match exists, a small deterministic sample
        is retained so the grounding remains inspectable.
        """

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]

        query_words = {
            word.strip(".,:;!?()[]{}\"'").lower()
            for word in query.split()
            if len(
                word.strip(".,:;!?()[]{}\"'")
            ) >= 3
        }

        matched: list[str] = []

        for line in lines:
            normalized = line.lower()

            if any(
                word in normalized
                for word in query_words
            ):
                matched.append(line)

        if not matched:
            matched = lines[:3]

        return matched[:8]

    def ground(
        self,
        query: str,
        *,
        policy_files: tuple[str, ...] = DEFAULT_POLICY_FILES,
    ) -> GroundingResult:
        """
        Ground text against the requested company policies.

        This function intentionally accepts `policy_files` because
        the existing Member 2 tests use that interface.
        """

        policies = self.load_policies(
            policy_files
        )

        policies_checked: list[str] = []
        evidence: list[dict[str, Any]] = []
        warnings: list[str] = []

        for filename in policy_files:
            policy = policies[filename]

            if not policy["found"]:
                warnings.append(
                    f"Policy not found: {filename}"
                )

                evidence.append(
                    {
                        "name": filename,
                        "found": False,
                        "evidence": [],
                    }
                )

                continue

            policies_checked.append(
                filename
            )

            relevant = self._extract_evidence(
                policy["content"],
                query,
            )

            evidence.append(
                {
                    "name": filename,
                    "found": True,
                    "evidence": relevant,
                }
            )

        supported = bool(
            policies_checked
            and evidence
        )

        return GroundingResult(
            query=query,
            policies_checked=policies_checked,
            evidence=evidence,
            supported=supported,
            warnings=warnings,
        )


def ground_customer_followup(
    customer_reply: str,
    *,
    policy_dir: str | Path | None = None,
) -> GroundingResult:
    """
    Ground a Customer Follow-up reply against all company policies.
    """

    grounder = PolicyGrounder(
        policy_dir=policy_dir
    )

    query = (
        "Customer follow-up validation. "
        f"Customer reply: {customer_reply}"
    )

    return grounder.ground(query)