# Member 1 — Graph #2: SLA Breach Escalation + Prior-Lab Corrections

## Scope

Member 1 owns **State Graph #2** and prior-lab corrections.

This work **reuses** Member 2's durable infrastructure:

- `state_graph/common/store.py` — SQLite checkpoints, HITL tasks, failure tickets
- `state_graph/common/graph_base.py` — `DurableGraphRunner`
- `state_graph/common/react.py` / `mcp_adapter.py` — constrained MCP execution
- existing `db/support.db`, MCP server, and company policies

It does **not** duplicate Customer Follow-up or Failure Recovery.

---

## Graph #2 business problem

### SLA Breach Escalation & Goodwill Credit

When a Coderift support ticket stays open past the SLA resolution target
(`mcp_server/policies/sla_policy.txt`), the company must:

1. detect the breach against the real SLA hours
2. load ticket/SLA/security policy evidence
3. branch over remediation strategies (Tree of Thoughts)
4. pause for an admin when a goodwill credit or High-priority action
   is not allowed to be decided by the agent alone
5. wait for the customer to accept or reject the offer
6. recover from mid-node failures without restarting from scratch

A one-shot script cannot do this: the customer acknowledgement may arrive
hours later, the admin decision is an external event, and losing progress
while the SLA clock is already breached makes the situation worse.

```text
DETECT_BREACH
      |
GROUND_SLA_POLICY
      |
TREE_OF_THOUGHTS  <----------------------+
      |                                   |
HITL_GATE                                 |
      |                                   |
WAITING_FOR_ADMIN --reject----------------+
      |
   approve
      |
WAITING_FOR_CUSTOMER_ACK --reject---------+
      |
   accept
      |
   RESOLVED
```

---

## Two LLM-call additions (rubric)

| Addition | Where | Why this technique |
|---|---|---|
| **Tree of Thoughts** | `TREE_OF_THOUGHTS` node via `state_graph/common/tot_remediation.py` | Breach remediations are competing strategies (credit vs priority bump vs Pending). ToT branches and scores them; a single greedy pick would hide that search. |
| **Constrained ReAct** | `execute_remediation_with_mcp()` via `run_sla_remediation` | After authorization, only whitelisted MCP tools (`get_ticket`, `update_ticket_status`) may run. Prevents inventing write actions. |

Not used here on purpose:

- RAG-as-LLM-addition is owned by Member 2's Customer Follow-up grounding verdict.
- LATS is owned by Member 2's Failure Recovery selector.

---

## HITL conditions (explicit)

HITL fires when any of these is true:

1. goodwill credit ≥ **$50**
2. strategy is `request_goodwill_credit`
3. ticket priority is **High**
4. ToT score < **0.60**
5. SLA/policy grounding unsupported

The graph pauses, persists full state, creates a `hitl_tasks` row, and
resumes only after `resolve_sla_breach_hitl()` with the admin's real decision.

---

## Failure tickets vs HITL

| Path | Meaning | API |
|---|---|---|
| HITL | Expected pause for a decision the agent may not make alone | `pause_for_hitl` / `resolve_sla_breach_hitl` |
| Failure ticket | Unplanned mid-node error (tool/schema/model) | `fail_sla_breach_node` / `resume_sla_breach_after_failure` |

Statuses for failures: `OPEN` → `INVESTIGATING` (shared store) → `RESOLVED`.

Resume keeps `completed_steps` and does **not** restart at `DETECT_BREACH`.

---

## Locatable files

| Concern | Path |
|---|---|
| Graph + cycles + HITL + failure | `state_graph/graphs/sla_breach_escalation.py` |
| Tree of Thoughts | `state_graph/common/tot_remediation.py` |
| Constrained ReAct (SLA) | `state_graph/common/react.py` (`run_sla_remediation`) |
| Checkpoint store (shared) | `state_graph/common/store.py` |
| Tests | `state_graph/tests/test_sla_breach_escalation.py` |
| Demo | `demo_member1.py` |

---

## Prior-lab corrections (Member 1)

1. **MCP authorization gap** — ticket tools in `mcp_server/tools.py` now call `authorize()` on every tool (previously only RAG tools did).
2. **Permission name mismatch** — `authorization.py` now uses `dashboard_tool` to match the registered MCP tool name.

---

## How to run

```bash
# from repo root
python db/create_db.py
python -m pytest state_graph/tests/test_sla_breach_escalation.py -q
python demo_member1.py
```

Optional live LLM for ToT/ReAct:

```bash
set STATE_GRAPH_USE_REAL_LLM=true
```
