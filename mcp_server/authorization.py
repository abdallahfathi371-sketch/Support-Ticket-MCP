from .database import get_employee


PERMISSIONS = {
    "admin": [
        "get_ticket",
        "search_open_tickets",
        "search_by_team",
        "update_ticket_status",
        "generate_report",
        "dashboard_tool",
        "search_knowledge",
    ],
    "support": [
        "get_ticket",
        "search_open_tickets",
        "search_by_team",
        "update_ticket_status",
        "search_knowledge",
    ],
    "viewer": [
        "get_ticket",
        "search_open_tickets",
        "search_by_team",
        # Intentionally no search_knowledge unless your policy permits it.
    ],
}


def authorize(employee_id: int, action: str):
    employee = get_employee(employee_id)

    if employee is None:
        raise Exception("Employee not found.")

    role = employee["role"]

    if action not in PERMISSIONS.get(role, []):
        raise Exception(
            f"Employee role '{role}' is not allowed to perform {action}"
        )

    return True
