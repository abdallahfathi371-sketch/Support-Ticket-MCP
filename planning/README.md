# Planning & Dynamic Decomposition

## Overview

The Support Ticket MCP system includes a planning layer that enables the agent to handle complex support-ticket requests by decomposing them into smaller executable tasks.

The planning system supports two complementary approaches:

1. **Decomposition-First Planning**
2. **Dynamic / Interleaved Decomposition**

Both approaches use the existing Support Ticket MCP tools to retrieve real company data instead of allowing the LLM to invent information.

---

## Architecture

```text
User Request
     |
     v
Complexity Detection
     |
     +----------------------+
     |                      |
 Simple Request       Complex Request
     |                      |
     v                      v
Direct Agent          Dynamic Planning
                           |
                           v
                    Generate Task
                           |
                           v
                    Execute Task
                           |
                           v
                     MCP Tool
                           |
                           v
                      Observation
                           |
                           v
                 Generate Next Task
                           |
                           v
                         ...
                           |
                           v
                    Final Synthesis
```

---

## Decomposition-First Planning

The decomposition-first planner converts a complex request into a validated Directed Acyclic Graph (DAG).

For example:

```text
User Goal
   |
   v
t1: Retrieve open tickets
   |
   v
t2: Analyze ticket priorities
   |
   v
t3: Synthesize final answer
```

Tasks can have dependencies, and independent tasks can be executed in parallel.

### Main Components

* `planning/models.py`

  * Defines and validates the planning models.
  * Validates task IDs and dependencies.
  * Provides DAG execution batches.

* `planning/algorithms/decomposition.py`

  * Generates the initial task decomposition.
  * Maps deterministic tasks to real MCP operations.
  * Executes tasks according to DAG dependencies.

* `planning/planner.py`

  * Creates validated plans from user goals.

* `planning/executor.py`

  * Executes the generated plan.

* `planning/runner.py`

  * Provides the main entry point for the planning workflow.

---

## Dynamic / Interleaved Decomposition

The dynamic planner does not generate the complete plan before execution.

Instead, it follows an observe-and-adapt loop:

```text
Goal
 |
 v
Generate Task
 |
 v
Execute Task
 |
 v
Observe Result
 |
 v
Generate Next Task
 |
 v
Execute Task
 |
 v
Observe Result
 |
 v
...
 |
 v
Final Synthesis
```

This allows the planner to react to unexpected results, failures, or insufficient evidence.

### Main Component

`planning/algorithms/dynamic_decomposition.py`

The dynamic planner:

* Generates one task at a time.
* Uses previous task outputs as observations.
* Validates task dependencies.
* Prevents forward dependencies and self-dependencies.
* Prevents duplicate task IDs.
* Executes tasks through the existing MCP layer.
* Builds a validated `Plan` from the dynamic execution trace.
* Produces a final synthesis task when enough evidence is available.

---

## MCP Integration

The planning layer uses the existing Support Ticket MCP tools rather than accessing the database directly.

Supported operations include:

* `get_ticket`
* `search_open_tickets`
* `search_by_team`
* `update_ticket_status`
* `generate_report`
* `dashboard_tool`
* `search_knowledge`
* `answer_from_knowledge`
* `answer_agentic_rag`

This keeps the planning layer separate from the underlying database and preserves the MCP server's authorization and validation boundaries.

---

## Safe Reasoning

The planner is explicitly instructed not to invent:

* Ticket IDs
* Ticket status
* Ticket priorities
* Customer information
* Team assignments
* Database results
* Company policies

If the available evidence is insufficient, the agent reports the limitation instead of making unsupported assumptions.

### Example

Suppose the MCP server returns:

```text
Ticket 1 - High
Ticket 4 - High
Ticket 10 - High
```

If no creation date, SLA, severity score, or other tie-breaking information is available, the planner should not arbitrarily select one ticket.

Instead, it should report that the available evidence does not support a unique choice.

---

## Example Dynamic Execution

For the request:

```text
Find the open tickets, identify the highest priority tickets,
and determine which ticket should be handled first.
```

The dynamic planner can produce:

```text
d1: Retrieve all open tickets
     |
     v
d2: Analyze the tickets and identify the highest priorities
     |
     v
d3: Synthesize the final answer
```

The first task is executed through the real MCP operation:

```text
search_open_tickets
```

The returned observation is then provided to the planner when generating the next task.

This demonstrates the key difference between static decomposition and dynamic planning: **the next task is generated after observing the previous task's result.**

---

## Validation and Testing

The planning implementation was validated using Python compilation checks:

```powershell
py -m py_compile planning\algorithms\decomposition.py
py -m py_compile planning\algorithms\dynamic_decomposition.py
py -m py_compile planning\models.py
py -m py_compile planning\planner.py
py -m py_compile planning\executor.py
py -m py_compile planning\runner.py
py -m py_compile agent\main.py
```

The agent was also tested end-to-end using a compound support-ticket request.

The final execution demonstrated:

* Complex request detection
* Dynamic task generation
* MCP tool execution
* Observation collection
* Dependency tracking
* Final synthesis
* Safe handling of insufficient evidence

---

## Error Handling

The planning layer validates:

* Empty planning goals
* Invalid task dependencies
* Unknown dependency IDs
* Self-dependencies
* Duplicate dynamic task IDs
* Invalid LLM JSON responses
* Missing required planning fields
* Empty LLM responses
* Missing MCP tools
* Missing execution outputs
* Invalid terminal task configuration

---

## Project Structure

```text
planning/
├── __init__.py
├── models.py
├── planner.py
├── executor.py
├── runner.py
└── algorithms/
    ├── __init__.py
    ├── decomposition.py
    └── dynamic_decomposition.py

agent/
├── main.py
├── client.py
└── prompt.py

mcp_server/
├── server.py
├── tools.py
├── authorization.py
└── rag/
    ├── knowledge.py
    ├── llm.py
    ├── self_rag.py
    └── agentic.py
```

---

## Running the System

Start the MCP server:

```powershell
py -m mcp_server.server
```

The server runs on:

```text
http://127.0.0.1:8000/mcp
```

Then start the agent in another terminal:

```powershell
py -m agent.main
```

Example:

```text
You: Find the open tickets, identify the highest priority tickets,
and determine which ticket should be handled first.
```

The agent detects the request as complex and routes it through the dynamic planning workflow.

---

## Key Design Principle

The planning system follows a simple principle:

> Plan what can be known, execute through trusted MCP tools, observe the results, and adapt the next step based on real evidence.

This prevents the planning agent from treating assumptions as facts and allows complex support-ticket requests to be handled through a controlled, observable workflow.
