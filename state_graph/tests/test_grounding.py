from state_graph.common.grounding import (
    PolicyGrounder,
    ground_customer_followup,
)


def test_policy_grounder_loads_company_policies():
    grounder = PolicyGrounder(
        "mcp_server/policies"
    )

    result = grounder.ground(
        "High priority ticket must be handled before other tickets"
    )

    assert "ticket_policy.txt" in result.policies_checked
    assert result.supported is True
    assert len(result.evidence) > 0


def test_grounding_returns_policy_evidence():
    result = ground_customer_followup(
        "Customer reports an error and needs ticket validation"
    )

    assert result.policies_checked
    assert isinstance(result.evidence, list)
    assert result.supported is True


def test_grounding_is_deterministic():
    query = (
        "Customer reports a ticket status problem "
        "and requests validation"
    )

    first = ground_customer_followup(query)
    second = ground_customer_followup(query)

    assert first.to_dict() == second.to_dict()


def test_missing_policy_is_reported(tmp_path):
    grounder = PolicyGrounder(
        tmp_path
    )

    result = grounder.ground(
        "ticket status",
        policy_files=("missing_policy.txt",),
    )

    assert result.supported is False
    assert (
        "Policy not found: missing_policy.txt"
        in result.warnings
    )