# Member 2 — Persistent State, HITL, Failure Recovery, LATS, and Constrained ReAct

## 1. Member 2 Scope

This part of the project implements the state-graph infrastructure and the
Customer Follow-up workflow owned by Member 2.

The implementation extends the existing Support-Ticket-MCP repository and
reuses:

- the existing SQLite database
- the existing MCP server
- the existing MCP client
- the existing company policies
- the existing Memory/RAG work
- the existing planning/reasoning infrastructure

No parallel database or replacement MCP server was introduced.

---

# 2. Business Problem Owned by Member 2

## Customer Follow-up

Support tickets often cannot be resolved in a single interaction.

A customer may initially submit an incomplete issue and then reply later with
reproduction steps, error codes, or additional information.

The workflow therefore needs to:

1. open the ticket workflow
2. request missing information
3. wait for the customer
4. resume when the customer replies
5. validate the new information
6. use company policies as grounding evidence
7. inspect the real ticket through the MCP server
8. escalate to an administrator when autonomous resolution is not allowed
9. resume after the administrator's decision

A normal one-shot function is insufficient because the customer response can
arrive much later and the original process may no longer exist.

The state graph persists the workflow so another process can recover the same
run from its latest checkpoint.

---

# 3. Customer Follow-up State Graph

```text
COLLECT_TICKET
      |
      v
REQUEST_CUSTOMER_INFO
      |
      v
WAITING_FOR_CUSTOMER
      |
      v
VALIDATE_REPLY
      |
      v
GROUNDING
      |
      v
CONSTRAINED_REACT
      |
      v
HITL DECISION
      |
      v
WAITING_FOR_ADMIN
      |
      +----------------------+
      |                      |
      v                      v
   APPROVE                 REJECT
      |                      |
      v                      |
   RESOLVE                   |
                             |
                             v
                    WAITING_FOR_CUSTOMER

                    ---

# 4. Why This Workflow Requires a State Graph

The Customer Follow-up workflow cannot be implemented safely as a single
linear function.

The customer response is an external event that may arrive much later than
the original request. The original Python process may have terminated before
the response arrives.

The workflow therefore needs durable states such as:

- WAITING_FOR_CUSTOMER
- WAITING_FOR_ADMIN
- RESOLVE

The graph can also move backward when an administrator rejects the proposed
resolution and more customer information is required.

This creates a real cycle:

WAITING_FOR_CUSTOMER
        |
        v
VALIDATE_REPLY
        |
        v
WAITING_FOR_ADMIN
        |
        v
REJECT
        |
        v
WAITING_FOR_CUSTOMER

Because the graph can pause, branch, and resume later, losing the process
would otherwise lose the progress already collected.

---
# 5. Durable Checkpointing

The graph uses SQLite-backed durable checkpoints through:

- `state_graph/common/store.py`
- `state_graph/common/graph_base.py`

Each meaningful state transition is persisted before the next state executes.

The persisted state includes:

- run ID
- graph name
- ticket ID
- current state
- workflow status
- accumulated graph state
- timestamps

The latest checkpoint can be loaded after a process restart and used to resume
the workflow without starting again from the beginning.

---
# 6. Human-in-the-Loop

The Customer Follow-up graph contains an explicit HITL pause.

HITL is required when the agent is not allowed to resolve the ticket
autonomously.

For the live workflow, high-priority tickets are escalated to an administrator
before resolution.

The graph:

1. persists its full state
2. creates a persistent HITL task
3. enters `WAITING_FOR_ADMIN`
4. waits for an administrator decision
5. resumes using the actual decision

Approval moves the graph to:

`RESOLVE`

Rejection moves the graph back to:

`WAITING_FOR_CUSTOMER`

The HITL task is persisted in the shared SQLite database.