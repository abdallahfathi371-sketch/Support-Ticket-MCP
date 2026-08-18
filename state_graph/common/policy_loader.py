from __future__ import annotations

from pathlib import Path


POLICY_DIR = (
    Path(__file__).resolve().parents[2]
    / "mcp_server"
    / "policies"
)


def load_policy(filename: str) -> dict[str, str | bool]:
    """
    Load one policy from the existing Support-Ticket policy directory.

    Returns:
        {
            "found": True,
            "name": "...",
            "content": "..."
        }

    If the policy does not exist:
        {
            "found": False,
            "name": "...",
            "content": ""
        }
    """

    # Only allow a plain filename.
    # This prevents path traversal such as ../secret.txt.
    requested_name = Path(filename).name

    if requested_name != filename:
        return {
            "found": False,
            "name": filename,
            "content": "",
        }

    path = POLICY_DIR / requested_name

    if not path.exists() or not path.is_file():
        return {
            "found": False,
            "name": requested_name,
            "content": "",
        }

    return {
        "found": True,
        "name": requested_name,
        "content": path.read_text(encoding="utf-8"),
    }


def load_required_policies() -> dict[str, dict[str, str | bool]]:
    """
    Load the policies relevant to Customer Follow-up validation.
    """

    return {
        "ticket_policy": load_policy("ticket_policy.txt"),
        "sla_policy": load_policy("sla_policy.txt"),
        "security_policy": load_policy("security_policy.txt"),
    }