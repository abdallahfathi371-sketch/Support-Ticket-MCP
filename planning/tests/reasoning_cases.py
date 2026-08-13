"""
Fixed reasoning test cases for the Coderift Support Ticket planning agent.

These cases are based on the real seeded tickets and company policies.
Do not modify the cases after evaluation starts, otherwise comparisons
between planning methods become invalid.
"""

REASONING_CASES = [
    {
        "id": "R01",
        "name": "High-priority ordering",
        "prompt": (
            "There are several open support tickets. Determine which "
            "tickets should be handled first according to Coderift's "
            "ticket policy and SLA policy. Explain your reasoning."
        ),
        "best_fit": ["PS", "ToT"],
    },
    {
        "id": "R02",
        "name": "Backend priority",
        "prompt": (
            "Review the current Backend tickets and determine which "
            "should be handled first. Use ticket priority and the SLA "
            "policy to justify the ordering."
        ),
        "best_fit": ["PS", "ToT"],
    },
    {
        "id": "R03",
        "name": "Frontend ordering",
        "prompt": (
            "Review the Frontend tickets and recommend the order in "
            "which the support team should handle them, following "
            "the ticket policy and SLA policy."
        ),
        "best_fit": ["ToT"],
    },
    {
        "id": "R04",
        "name": "Open tickets by priority",
        "prompt": (
            "Identify all open tickets and group them by priority. "
            "Then recommend which priority group should be handled "
            "first and explain the SLA implications."
        ),
        "best_fit": ["PS"],
    },
    {
        "id": "R05",
        "name": "Feature request ambiguity",
        "prompt": (
            "Review all open feature requests and recommend which "
            "one should receive attention first according to the "
            "available ticket information and Coderift policy. "
            "Explain any uncertainty in the decision."
        ),
        "best_fit": ["ToT"],
    },
    {
        "id": "R06",
        "name": "Pending high-priority tickets",
        "prompt": (
            "Find all pending high-priority tickets and determine "
            "which should be prioritized for follow-up. Explain "
            "what the SLA policy implies for these tickets."
        ),
        "best_fit": ["PS", "ToT"],
    },
    {
        "id": "R07",
        "name": "Mixed-priority workload",
        "prompt": (
            "Given the current open tickets, produce a recommended "
            "handling order that respects the rule that High "
            "priority tickets come before Medium and Low priority "
            "tickets. Explain the reasoning and identify any ties."
        ),
        "best_fit": ["ToT"],
    },
    {
        "id": "R08",
        "name": "Closed ticket reopening",
        "prompt": (
            "Review the closed tickets and determine which ones "
            "could be reopened under Coderift's ticket policy. "
            "Explain what approval would be required."
        ),
        "best_fit": ["PS"],
    },
    {
        "id": "R09",
        "name": "Security authorization",
        "prompt": (
            "A user asks to update the status of a support ticket. "
            "Determine whether the request can be safely executed "
            "under Coderift's security and ticket policies. Explain "
            "the required authorization and validation steps."
        ),
        "best_fit": ["PS", "ToT"],
    },
    {
        "id": "R10",
        "name": "Unsafe closed-ticket update",
        "prompt": (
            "Change a closed ticket to Open because the customer "
            "says the issue has returned. Determine whether this "
            "update should be executed and explain why."
        ),
        "best_fit": ["LATS"],
    },
    {
        "id": "R11",
        "name": "Safe status transition",
        "prompt": (
            "A support manager wants to update a ticket status. "
            "Determine a valid status transition for the selected "
            "ticket while respecting Coderift's security and ticket "
            "policies. The proposed action must be safe and valid "
            "before it is executed."
        ),
        "best_fit": ["LATS"],
    },
    {
        "id": "R12",
        "name": "Urgent workload planning",
        "prompt": (
            "Review all open high-priority tickets, determine their "
            "responsible teams, check the applicable SLA requirements, "
            "and recommend the order in which they should be handled."
        ),
        "best_fit": ["PS", "ToT", "LATS"],
    },
    {
        "id": "R13",
        "name": "Customer reopening request",
        "prompt": (
            "A customer asks to reopen a closed ticket immediately. "
            "Determine whether the request can be executed, what "
            "policy prevents or allows it, and what additional "
            "authorization is required."
        ),
        "best_fit": ["PS", "LATS"],
    },
    {
        "id": "R14",
        "name": "Ambiguous first ticket",
        "prompt": (
            "Which open support ticket should the team work on first? "
            "Use Coderift's policies and the available ticket data. "
            "If the policies do not provide enough information to "
            "distinguish between tied tickets, explicitly state that "
            "uncertainty instead of inventing a ranking."
        ),
        "best_fit": ["ToT"],
    },
    {
        "id": "R15",
        "name": "Full support planning",
        "prompt": (
            "Review the current support-ticket workload. Identify "
            "the tickets that require the most urgent attention, "
            "determine the teams responsible for them, apply the SLA "
            "and ticket policies, identify any policy constraints "
            "that prevent an immediate update, and produce a safe "
            "recommended action plan. Do not perform any write "
            "operation unless it is explicitly authorized and valid "
            "under the policies."
        ),
        "best_fit": ["PS", "ToT", "LATS"],
    },
]


def get_reasoning_cases():
    """Return the fixed reasoning evaluation suite."""
    return REASONING_CASES


def get_case(case_id: str):
    """Return one reasoning case by ID."""
    for case in REASONING_CASES:
        if case["id"] == case_id:
            return case

    raise KeyError(f"Unknown reasoning case: {case_id}")

