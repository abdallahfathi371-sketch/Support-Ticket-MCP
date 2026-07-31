from database import (
    db_get_ticket,
    db_search_open_tickets,
    db_search_by_team,
    db_update_ticket_status
)


def get_ticket(ticket_id: int):
    """
    Retrieve a ticket by its ID.
    """
    ticket = db_get_ticket(ticket_id)

    if ticket is None:
        return {
            "success": False,
            "message": f"Ticket {ticket_id} was not found."
        }

    return {
        "success": True,
        "ticket": ticket
    }


def search_open_tickets():
    """
    Return all open tickets.
    """

    tickets = db_search_open_tickets()

    return {
        "count": len(tickets),
        "tickets": tickets
    }


def search_by_team(team_name: str):
    """
    Return tickets assigned to a team.
    """

    tickets = db_search_by_team(team_name)

    return {
        "team": team_name,
        "count": len(tickets),
        "tickets": tickets
    }


def update_ticket_status(ticket_id: int, status: str):

    allowed = ["Open", "Pending", "Closed"]

    if status not in allowed:
        return {
            "success": False,
            "message": "Invalid status."
        }

    updated = db_update_ticket_status(ticket_id, status)

    if updated:
        return {
            "success": True,
            "message": f"Ticket {ticket_id} updated successfully."
        }

    return {
        "success": False,
        "message": f"Ticket {ticket_id} not found."
    }