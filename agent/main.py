import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq

from .client import MCPClient
from .prompt import SYSTEM_PROMPT

from memory.memory_manager import MemoryManager
from context_eval.strategies import sliding_window

from planning.algorithms.dynamic_decomposition import DynamicDecomposer


# ============================================================
# Environment
# ============================================================

load_dotenv()


# ============================================================
# Clients
# ============================================================

mcp_client = MCPClient()

memory = MemoryManager(
    buffer_size=10
)

groq_api_key = os.getenv(
    "GROQ_API_KEY"
)

if not groq_api_key:
    raise RuntimeError(
        "GROQ_API_KEY is not set in the environment."
    )

groq_client = Groq(
    api_key=groq_api_key
)


# ============================================================
# Current Dynamic Planning Goal
# ============================================================

CURRENT_GOAL = ""


# ============================================================
# Tool Discovery
# ============================================================

async def get_available_tools():
    """
    Discover the currently available MCP tools.
    """

    tools = await mcp_client.list_tools()

    return [
        {
            "name": tool.name,
            "description": tool.description,
        }
        for tool in tools
    ]


# ============================================================
# Groq
# ============================================================

async def ask_groq(messages):
    """
    Send a chat request to Groq.
    """
    import time
    try:
        from planning.metrics import record_llm_call
    except Exception:
        record_llm_call = None

    t0 = time.perf_counter()
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
    )
    t1 = time.perf_counter()

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    if record_llm_call is not None:
        try:
            approx_tokens = max(1, int((len(str(messages)) + len(str(content))) / 4))
            record_llm_call(latency=t1 - t0, approx_tokens=approx_tokens)
        except Exception:
            pass

    return content.strip()


# ============================================================
# Detect Complex Requests
# ============================================================

def is_complex_request(
    user_input: str,
) -> bool:
    """
    Detect requests that benefit from decomposition.
    """

    text = user_input.lower()

    indicators = [
        "and",
        "then",
        "compare",
        "analyze",
        "analyse",
        "identify",
        "determine",
        "recommend",
        "prioritize",
        "priority",
        "highest",
        "lowest",
        "which ticket",
        "why",
        "summarize",
        "summary",
        "multiple",
        "all tickets",
        "open tickets",
    ]

    matches = sum(
        1
        for indicator in indicators
        if indicator in text
    )

    return matches >= 2


# ============================================================
# Dynamic Task Executor
# ============================================================

async def execute_dynamic_task(
    instruction: str,
    previous_outputs: dict[str, str],
) -> str:
    """
    Execute one dynamic task.

    There are three possible paths:

    1. Final synthesis
       -> Groq uses all collected evidence.

    2. Direct MCP retrieval
       -> Existing MCP tool is called.

    3. Reasoning / analysis
       -> Groq analyzes previous observations.
    """

    text = instruction.lower()

    # ========================================================
    # FINAL SYNTHESIS
    # ========================================================

    synthesis_words = [
        "synthesize",
        "synthesis",
        "final answer",
        "final response",
        "combine the results",
        "summarize the findings",
        "determine which ticket should be handled first",
        "which ticket should be handled first",
    ]

    is_final_task = any(
        word in text
        for word in synthesis_words
    )

    if is_final_task:

        evidence = "\n\n".join(
            f"Task {task_id}:\n{output}"
            for task_id, output in previous_outputs.items()
        )

        if not evidence:
            evidence = "No previous evidence was collected."

        prompt = f"""
You are producing the FINAL answer for a support-ticket request.

Original user request:

{CURRENT_GOAL}

Evidence collected by the executed planning tasks:

{evidence}

Final synthesis instruction:

{instruction}

Rules:

1. Answer the original request directly.

2. Use ONLY the evidence above.

3. Never invent:
   - ticket IDs
   - customer names
   - priorities
   - creation dates
   - statuses
   - team assignments
   - policies

4. Clearly identify all tickets having the highest priority.

5. If multiple tickets have the same highest priority, report all
   of them.

6. Only choose one ticket to handle first if the evidence contains
   a valid tie-breaker.

7. Do NOT assume that ticket order means creation order.

8. Do NOT invent creation dates.

9. If the evidence is insufficient to select exactly one ticket,
   explicitly say that the available evidence does not support
   a unique choice.

10. Keep the final answer concise and useful.

11. Mention the relevant ticket IDs.
"""

        return await ask_groq(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a careful support-ticket "
                        "analysis assistant. "
                        "You must only use provided evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
        )

    # ========================================================
    # DIRECT MCP TASK
    # ========================================================

    if (
        "retrieve all open tickets" in text
        or "find all open tickets" in text
        or "search open tickets" in text
        or "get all open tickets" in text
        or "retrieve the open tickets" in text
    ):

        print(
            "[Dynamic Planning] Executing MCP: "
            "search_open_tickets"
        )

        result = await mcp_client.execute_tool(
            "search_open_tickets",
            {
                "employee_id": 1,
            },
        )

        return str(result)

    # ========================================================
    # ANALYSIS TASK
    # ========================================================

    evidence = "\n\n".join(
        f"Task {task_id}:\n{output}"
        for task_id, output in previous_outputs.items()
    )

    if not evidence:
        evidence = "No previous task outputs are available."

    prompt = f"""
You are executing ONE task inside a dynamic support-ticket
planning workflow.

Original user goal:

{CURRENT_GOAL}

Current task:

{instruction}

Previous task observations:

{evidence}

Rules:

1. Perform ONLY the current task.

2. Use previous observations as evidence.

3. Do NOT retrieve the same information again if it already exists
   in previous observations.

4. Analyze the previous observations when the current task is an
   analysis task.

5. Do not invent:
   - ticket IDs
   - customer names
   - priorities
   - creation dates
   - statuses
   - team assignments
   - database results
   - policies

6. If multiple tickets have the same highest priority, list all of them.

7. Do not assume ticket order represents creation order.

8. If the evidence is insufficient, explicitly say what is missing.

9. Return ONLY the result of the current task.

10. Do not write a final answer to the original user unless the
    current task is explicitly a final synthesis task.
"""

    return await ask_groq(
        [
            {
                "role": "system",
                "content": (
                    "You are executing a single validated task "
                    "inside a support-ticket DAG."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )


# ============================================================
# Dynamic Planning
# ============================================================

async def run_dynamic_planning(
    goal: str,
) -> dict:
    """
    Execute the dynamic/interleaved planning workflow.

    Flow:

        Goal
          ↓
        Generate task
          ↓
        Execute task
          ↓
        Observe result
          ↓
        Generate next task
          ↓
        ...
          ↓
        Final synthesis
    """

    global CURRENT_GOAL

    CURRENT_GOAL = goal

    print(
        "\n[Dynamic Planning] Starting..."
    )

    decomposer = DynamicDecomposer()

    async def execute_task(
        instruction: str,
        previous_outputs: dict[str, str],
    ):
        return await execute_dynamic_task(
            instruction,
            previous_outputs,
        )

    result = await decomposer.run(
        goal=goal,
        execute_task=execute_task,
        max_steps=8,
    )

    print(
        "\n[Dynamic Planning] Completed."
    )

    print(
        "\n[Dynamic Planning] Steps:",
        result["steps"],
    )

    print(
        "\n[Dynamic Planning] Execution plan:"
    )

    print(
        json.dumps(
            result["plan"],
            indent=2,
            ensure_ascii=False,
        )
    )

    return result


# ============================================================
# Normal Agent Flow
# ============================================================

async def process_normal_query(
    user_input: str,
):
    """
    Existing direct-agent flow for simple requests.
    """

    tools = await get_available_tools()

    # --------------------------------------------------------
    # Memory
    # --------------------------------------------------------

    raw_memory = memory.get_short_memory()

    memory_context = sliding_window(
        raw_memory,
        window_size=6,
    )

    # --------------------------------------------------------
    # LLM Messages
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "system",
            "content": f"""
Previous Conversation Context:

{json.dumps(memory_context, indent=2)}

Available MCP Tools:

{json.dumps(tools, indent=2)}
""",
        },
        {
            "role": "user",
            "content": user_input,
        },
    ]

    response = await ask_groq(
        messages
    )

    # --------------------------------------------------------
    # Tool Request
    # --------------------------------------------------------

    try:

        tool_request = json.loads(
            response
        )

        if "tool" in tool_request:

            tool_name = tool_request["tool"]

            arguments = tool_request.get(
                "arguments",
                {},
            )

            arguments["employee_id"] = 1

            result = await mcp_client.execute_tool(
                tool_name,
                arguments,
            )

            # ------------------------------------------------
            # Save tool observation
            # ------------------------------------------------

            memory.remember(
                "tool",
                f"{tool_name}: {result}",
            )

            memory.episodic.add_episode(
                content=f"{tool_name}: {result}",
                reason="Tool observation from MCP call",
                importance=0.8,
            )

            final_messages = messages + [
                {
                    "role": "assistant",
                    "content": response,
                },
                {
                    "role": "tool",
                    "content": str(result),
                    "tool_call_id": tool_name,
                },
            ]

            final_answer = await ask_groq(
                final_messages
            )

            return final_answer

    except json.JSONDecodeError:
        pass

    return response


# ============================================================
# Main Query Processor
# ============================================================

async def process_user_query(
    user_input: str,
):
    """
    Route the user request.

    Complex requests:

        Dynamic Decomposition
              ↓
             MCP
              ↓
         Observation
              ↓
          Analysis
              ↓
          Observation
              ↓
       Final Synthesis

    Simple requests:

        Existing direct agent flow
    """

    if is_complex_request(
        user_input
    ):

        print(
            "\n[Router] Complex request detected."
        )

        planning_result = await run_dynamic_planning(
            user_input
        )

        outputs = planning_result.get(
            "outputs",
            {},
        )

        if not outputs:
            raise RuntimeError(
                "Dynamic planning produced no outputs."
            )

        # ----------------------------------------------------
        # Get the terminal task from the generated plan
        # ----------------------------------------------------

        tasks = planning_result["plan"]["tasks"]

        final_task_id = None

        for task in tasks:
            if (
                task["id"] in outputs
                and task["id"] == tasks[-1]["id"]
            ):
                final_task_id = task["id"]

        if final_task_id is None:
            final_task_id = list(
                outputs.keys()
            )[-1]

        return outputs[
            final_task_id
        ]

    print(
        "\n[Router] Simple request detected."
    )

    return await process_normal_query(
        user_input
    )


# ============================================================
# Main
# ============================================================

async def main():

    await mcp_client.connect()

    print(
        "\nCoderift Support Assistant Started"
    )

    print(
        "\nDiscovered Tools:"
    )

    tools = await get_available_tools()

    for tool in tools:

        print(
            "-",
            tool["name"],
        )

    while True:

        user = input(
            "\nYou: "
        )

        if user.lower().strip() == "exit":

            memory.consolidate()

            print(
                "Memory Saved."
            )

            break

        if not user.strip():
            continue

        memory.remember(
            "user",
            user,
        )

        try:

            answer = await process_user_query(
                user
            )

            print(
                "\nAssistant:"
            )

            print(
                answer
            )

            memory.remember(
                "assistant",
                answer,
            )

            memory.episodic.add_episode(
                content=answer,
                reason="Assistant response",
                importance=0.5,
            )

        except Exception as exc:

            print(
                "\n[ERROR]"
            )

            print(
                f"{type(exc).__name__}: {exc}"
            )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())