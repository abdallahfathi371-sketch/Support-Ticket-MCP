# Member 3 — State Graph #3 + Platform + Admin + User Chat + Agent Switching

## Scope

This role adds the final state-graph workflow and the live platform surface used by both a real user and a real admin.

The implementation covers:

- Insurance claim appeal state graph (`state_graph/graphs/claim_appeal.py`)
- Platform server (`platform/server.py`)
- Admin controls for tool toggles and document management
- User chat with agent switching
- HITL resolution and failure-ticket handling from the UI

## State Graph #3 business problem

Claims often need a real external decision and a human check before a payout is approved.

The graph therefore:

1. opens the claim case
2. loads policy evidence
3. compares likely remediation strategies
4. pauses on HITL when the claim or policy risk is high
5. waits for admin approval
6. resumes when the insurer response arrives
7. persists through failures and resumes from the same checkpoint

This cannot be a single linear function because the external response is delayed and the system must not silently lose work.

## Platform responsibilities

The platform is intentionally simple but operational:

- `GET /api/agents` lists the available agents
- `POST /api/chat` routes a message to the selected agent
- `GET /api/admin/tools` and `POST /api/admin/tools` manage runtime tool availability
- `GET /api/admin/rag` and `POST /api/admin/rag` add or list documents for retrieval
- `GET /api/admin/hitl` and `POST /api/admin/hitl/<id>/resolve` manage admin decisions
- `GET /api/admin/failures` and `POST /api/admin/failures/<id>/resolve` handle failure tickets

## Agent switching

The UI exposes a selector for the active agent and stores user history in the shared SQLite state store. This allows the same interface to route queries between:

- the support-ticket MCP agent
- the memory/RAG agent
- the planning agent
- the state-graph agent

## Why this needs durable checkpoints

The claim graph, like the other two graphs, persists after each meaningful transition. That makes it possible to restart a process, recover the last checkpoint, and continue without replaying completed work.
