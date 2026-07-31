import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "support.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_get_ticket(ticket_id):
    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ticket_id,
            customer_name,
            issue,
            category,
            status,
            priority,
            team_name
        FROM tickets
        JOIN teams
        ON tickets.team_id = teams.team_id
        WHERE ticket_id = ?
        """,
        (ticket_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)



def db_search_open_tickets():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ticket_id,
            customer_name,
            category,
            priority
        FROM tickets
        WHERE status='Open'
    """)

    rows = cursor.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def db_search_by_team(team_name):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ticket_id,
            customer_name,
            status,
            priority
        FROM tickets
        JOIN teams
        ON tickets.team_id=teams.team_id
        WHERE team_name=?
    """, (team_name,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(r) for r in rows]


def db_update_ticket_status(ticket_id, new_status):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tickets
        SET status=?
        WHERE ticket_id=?
    """, (new_status, ticket_id))

    conn.commit()

    affected = cursor.rowcount

    conn.close()

    return affected > 0