import asyncio
import sys
import os

from dotenv import load_dotenv

load_dotenv()

# Make the existing agent package importable.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

AGENT_DIR = os.path.join(
    PROJECT_ROOT,
    "agent",
)

if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)


from client import MCPClient

from .executor import run_planning


async def main():

    goal = (
        "Analyze open high-priority support tickets "
        "and determine which should be handled first."
    )

    mcp_client = MCPClient()

    await mcp_client.connect()

    result = await run_planning(
        goal,
        mcp_client,
    )

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)

    print(result["final_answer"])


if __name__ == "__main__":
    asyncio.run(main())
