import sqlite3
import subprocess
import sys
from pathlib import Path


DB_PATH = (
    Path(__file__).parent.parent
    / "db"
    / "support.db"
)


def ensure_support_db() -> None:
    if not DB_PATH.exists():
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "db" / "create_db.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        return

    with sqlite3.connect(DB_PATH) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    if not {"employees", "teams", "tickets"}.issubset(tables):
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "db" / "create_db.py")],
            check=False,
            capture_output=True,
            text=True,
        )


ensure_support_db()


def get_connection():
    ensure_support_db()

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


def ensure_ticket_status_logs_table() -> None:
    """
    Idempotent prior-lab schema fix for existing databases.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_status_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(ticket_id)
                REFERENCES tickets(ticket_id),
            FOREIGN KEY(employee_id)
                REFERENCES employees(employee_id)
        )
        """
    )

    conn.commit()
    conn.close()


def log_ticket_status_change(
    *,
    ticket_id: int,
    employee_id: int,
    old_status: str,
    new_status: str,
) -> None:
    """
    Persist an audit row for every ticket status update.
    """

    from datetime import datetime, timezone

    ensure_ticket_status_logs_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO ticket_status_logs
        (
            ticket_id,
            employee_id,
            old_status,
            new_status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            ticket_id,
            employee_id,
            old_status,
            new_status,
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    conn.commit()
    conn.close()
