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

## Author

Abdallah Fathi