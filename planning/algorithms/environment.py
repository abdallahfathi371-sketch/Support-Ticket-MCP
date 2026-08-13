from __future__ import annotations

import re

from planning.models import EnvironmentFeedback
from mcp_server.database import get_connection


class Environment:
    """
    Grounded environment for LATS.

    Validates candidate solutions against the real support-ticket database.
    """

    def evaluate(self, state: str) -> EnvironmentFeedback:
        details: list[str] = []

        if not state or not state.strip():
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["Candidate state is empty."],
            )

        state = state.strip()

        conn = get_connection()
        cursor = conn.cursor()

        try:
            ticket_ids = [
                int(value)
                for value in re.findall(
                    r"\bticket(?:\s+id)?\s*[:#]?\s*(\d+)\b",
                    state,
                    flags=re.IGNORECASE,
                )
            ]

            if not ticket_ids:
                ticket_ids = [
                    int(value)
                    for value in re.findall(
                        r"#(\d+)\b",
                        state,
                    )
                ]

            ticket_ids = list(dict.fromkeys(ticket_ids))

            if ticket_ids:
                for ticket_id in ticket_ids:
                    cursor.execute(
                        """
                        SELECT
                            ticket_id,
                            status,
                            priority,
                            category
                        FROM tickets
                        WHERE ticket_id = ?
                        """,
                        (ticket_id,),
                    )

                    ticket = cursor.fetchone()

                    if ticket is None:
                        return EnvironmentFeedback(
                            success=False,
                            score=0.0,
                            details=[
                                f"Ticket {ticket_id} does not exist "
                                "in the database."
                            ],
                        )

                    details.append(
                        f"Ticket {ticket_id}: "
                        f"status={ticket['status']}, "
                        f"priority={ticket['priority']}, "
                        f"category={ticket['category']}."
                    )

            closing_requested = bool(
                re.search(
                    r"\b(close|closing|closed)\b",
                    state,
                    flags=re.IGNORECASE,
                )
            )

            if closing_requested and ticket_ids:
                for ticket_id in ticket_ids:
                    cursor.execute(
                        """
                        SELECT priority, status
                        FROM tickets
                        WHERE ticket_id = ?
                        """,
                        (ticket_id,),
                    )

                    ticket = cursor.fetchone()

                    if (
                        ticket
                        and ticket["priority"] == "High"
                        and ticket["status"] != "Closed"
                    ):
                        details.append(
                            f"Ticket {ticket_id} is High priority; "
                            "closing it requires human approval."
                        )

                        return EnvironmentFeedback(
                            success=False,
                            score=0.25,
                            details=details,
                        )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM tickets
                """
            )

            total_tickets = cursor.fetchone()[0]

            if total_tickets == 0:
                return EnvironmentFeedback(
                    success=False,
                    score=0.0,
                    details=[
                        "The ticket database contains no tickets."
                    ],
                )

            details.append(
                f"Grounded database check passed: "
                f"{total_tickets} tickets are available."
            )

            score = 0.85 if ticket_ids else 0.70

            return EnvironmentFeedback(
                success=True,
                score=score,
                details=details,
            )

        finally:
            conn.close()