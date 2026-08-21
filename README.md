# Support Ticket MCP

## Overview

Support Ticket MCP is an AI-powered support ticket management system built using FastMCP, Groq LLM, and SQLite.

The assistant can:

- Retrieve ticket details by ID.
- Search all open tickets.
- Search tickets assigned to a specific team.
- Update ticket status.
- Answer users using MCP tools instead of making up information.

---

## Project Structure

```
support-ticket-mcp/
│
├── agent/
│   ├── main.py
│   ├── client.py
│   └── prompt.py
│
├── mcp_server/
│   ├── server.py
│   ├── tools.py
│   ├── database.py
│   └── resources.py
│
├── db/
│   ├── schema.sql
│   ├── seed.sql
│   ├── create_db.py
│   └── support.db
│
├── requirements.txt
└── README.md
```

---

## Technologies

- Python
- FastMCP
- Groq API
- SQLite
- python-dotenv

---

## Installation

Clone the repository:

```bash
git clone <repository_url>
cd Support-Ticket-MCP
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```text
GROQ_API_KEY=your_api_key
```

---

## Create Database

```bash
python db/create_db.py
```

---

## Run the Assistant

```bash
cd agent
python main.py
```

---

## Available MCP Tools

### get_ticket(ticket_id)

Returns a ticket by its ID.

Example:

```
Get ticket 1
```

---

### search_open_tickets()

Returns all open tickets.

Example:

```
Search open tickets
```

---

### search_by_team(team_name)

Returns tickets assigned to a team.

Example:

```
Search Backend tickets
```

---

### update_ticket_status(ticket_id, status)

Updates a ticket status.

Example:

```
Update ticket 5 to Closed
```

---

## Database

The database contains:

- Teams
- Support Tickets

Each ticket includes:

- Customer Name
- Issue
- Category
- Status
- Priority
- Assigned Team

---

## Self-Refine, Reflexion, Grounding, Evaluation & Metrics

This repository now includes the Week 4 Decomposition & Planning lab implementations integrated with the existing planning toolkit. The additions (Self-Refine, Reflexion orchestration, grounding, evaluation harness, and metrics collection) extend the planning layer without replacing the toolkit algorithms already present.

How to run the evaluation harness

1. Ensure dependencies and GROQ_API_KEY are set in `.env`.
2. Create the database: `python db/create_db.py`.
3. Run the evaluation harness to execute Plan-and-Solve, Tree-of-Thoughts, and LATS on the fixed reasoning cases:

```bash
python -m planning.eval_runner
```

Artifacts and metrics are written to `planning/artifacts/`.

Demo and reproducible runs

- Run the MCP server: `py -m mcp_server.server` (or `python -m mcp_server.server`)
- Start the agent in another terminal: `py -m agent.main`
- Provide complex requests (examples in `planning/README.md`) and observe the integrated planning agent using dynamic decomposition, Self-Refine, Reflexion, and grounded LATS.

Credits

Abdallah Fathi

---

## Final Project — State Graphs

Shared durable state (Member 2 infrastructure): `state_graph/common/`

| Graph | Owner | Folder |
|---|---|---|
| Customer Follow-up | Member 2 | `state_graph/graphs/customer_followup.py` |
| Failure Recovery | Member 2 | `state_graph/graphs/failure_recovery.py` |
| **SLA Breach Escalation** | **Member 1** | `state_graph/graphs/sla_breach_escalation.py` |
| **Insurance Claim Appeal** | **Platform / State Graph #3** | `state_graph/graphs/claim_appeal.py` |

Member 1 details: `state_graph/README_MEMBER1.md`  
Member 2 details: `state_graph/README_MEMBER2.md`  
Member 3 / Platform details: `state_graph/README_MEMBER3.md` and `platform/server.py`

```bash
python demo_member1.py
python -m pytest state_graph/tests/test_sla_breach_escalation.py state_graph/tests/test_sla_breach_restart.py -q
python -m platform_app.server
```

### Platform and agent switching

The repository now includes a local platform server that exposes:

- a user chat surface with selectable agents
- a live admin view for tool toggles and RAG document management
- HITL task review and failure ticket resolution
- a durable state-graph chain for claim appeals and escalations

This adds the missing runtime product surface required for the final project role.
