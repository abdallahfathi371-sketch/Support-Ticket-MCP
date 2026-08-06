from .app import mcp
from .database import get_connection


# =========================
# Get single ticket
# =========================

@mcp.tool()
def get_ticket(
    employee_id: int,
    ticket_id: int
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 
            tickets.ticket_id,
            tickets.customer_name,
            tickets.issue,
            tickets.category,
            tickets.status,
            tickets.priority,
            teams.team_name
        FROM tickets
        JOIN teams 
        ON tickets.team_id = teams.team_id
        WHERE tickets.ticket_id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    conn.close()

    if ticket is None:
        return {
            "success": False,
            "message": "Ticket not found"
        }

    return {
        "success": True,
        "ticket": dict(ticket)
    }



# =========================
# Search open tickets
# =========================

@mcp.tool()
def search_open_tickets(
    employee_id: int
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ticket_id,
            customer_name,
            issue,
            category,
            priority
        FROM tickets
        WHERE status = 'Open'
        """
    )

    tickets = cursor.fetchall()

    conn.close()

    return {
        "success": True,
        "count": len(tickets),
        "tickets": [
            dict(ticket)
            for ticket in tickets
        ]
    }



# =========================
# Search by team
# =========================

@mcp.tool()
def search_by_team(
    employee_id: int,
    team_name: str
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            tickets.ticket_id,
            tickets.customer_name,
            tickets.issue,
            tickets.status,
            tickets.priority,
            teams.team_name
        FROM tickets
        JOIN teams
        ON tickets.team_id = teams.team_id
        WHERE teams.team_name = ?
        """,
        (team_name,)
    )

    tickets = cursor.fetchall()

    conn.close()

    return {
        "success": True,
        "team": team_name,
        "count": len(tickets),
        "tickets": [
            dict(ticket)
            for ticket in tickets
        ]
    }



# =========================
# Update ticket status
# =========================

@mcp.tool()
def update_ticket_status(
    employee_id: int,
    ticket_id: int,
    status: str
):

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT priority,status
        FROM tickets
        WHERE ticket_id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()


    if ticket is None:
        conn.close()

        return {
            "success": False,
            "message": "Ticket not found"
        }



    # Human approval for High priority closing
    if (
        status == "Closed"
        and ticket["priority"] == "High"
    ):

        conn.close()

        return {
            "success": False,
            "message": "Human approval required.",
            "elicitation": {
                "type": "elicitation/create",
                "status": "waiting_for_confirmation",
                "action": "close_high_priority_ticket",
                "details": {
                    "ticket_id": ticket_id,
                    "priority": ticket["priority"],
                    "old_status": ticket["status"]
                },
                "message":
                "Human approval is required before continuing."
            }
        }



    cursor.execute(
        """
        UPDATE tickets
        SET status = ?
        WHERE ticket_id = ?
        """,
        (
            status,
            ticket_id
        )
    )

    conn.commit()
    conn.close()


    return {
        "success": True,
        "message": "Ticket status updated",
        "ticket_id": ticket_id,
        "new_status": status
    }



# =========================
# Generate report
# =========================

@mcp.tool()
def generate_report(
    employee_id: int
):

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT COUNT(*) 
        FROM tickets
        WHERE status='Open'
        """
    )

    open_tickets = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE priority='High'
        """
    )

    high_priority = cursor.fetchone()[0]


    conn.close()


    return {
        "success": True,

        "progress": [
            {
                "progress":20,
                "message":"Loading tickets..."
            },
            {
                "progress":60,
                "message":"Analyzing ticket data..."
            },
            {
                "progress":100,
                "message":"Report completed."
            }
        ],

        "report": {
            "total_open_tickets": open_tickets,
            "high_priority": high_priority
        }
    }



# =========================
# Dashboard
# =========================

@mcp.tool()
def dashboard_tool(
    employee_id: int
):

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM tickets
        """
    )

    total = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE status='Open'
        """
    )

    opened = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE status='Pending'
        """
    )

    pending = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM tickets
        WHERE status='Closed'
        """
    )

    closed = cursor.fetchone()[0]


    conn.close()


    return {
        "success": True,
        "dashboard": {
            "total_tickets": total,
            "open_tickets": opened,
            "pending_tickets": pending,
            "closed_tickets": closed
        }
    }