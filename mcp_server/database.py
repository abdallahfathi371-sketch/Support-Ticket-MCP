import sqlite3
from pathlib import Path


DB_PATH = (
    Path(__file__).parent.parent
    / "db"
    / "support.db"
)



def get_connection():

    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn



# ==================================================
# EMPLOYEE / AUTH SUPPORT
# ==================================================

def get_employee(
    employee_id: int
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            employee_id,
            employee_name,
            role
        FROM employees
        WHERE employee_id = ?
        """,
        (
            employee_id,
        )
    )


    row = cursor.fetchone()


    conn.close()


    if row is None:

        return None


    return dict(row)



# ==================================================
# TICKETS
# ==================================================

def db_get_ticket(
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
        (
            ticket_id,
        )
    )


    row = cursor.fetchone()


    conn.close()


    if row is None:

        return None


    return dict(row)




def db_search_open_tickets():

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

        ORDER BY priority DESC

        """
    )


    rows = cursor.fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]





def db_search_by_team(
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
        (
            team_name,
        )
    )


    rows = cursor.fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]





def db_update_ticket_status(
    ticket_id: int,
    new_status: str
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE tickets

        SET status = ?

        WHERE ticket_id = ?

        """,
        (
            new_status,
            ticket_id
        )
    )


    conn.commit()


    updated = cursor.rowcount > 0


    conn.close()


    return updated