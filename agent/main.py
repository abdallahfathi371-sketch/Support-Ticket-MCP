import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq

from client import MCPClient
from prompt import SYSTEM_PROMPT


load_dotenv()

groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

mcp = MCPClient()


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_ticket",
            "description": "Get a support ticket by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer"
                    }
                },
                "required": ["ticket_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_open_tickets",
            "description": "Return all open tickets",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_team",
            "description": "Search tickets assigned to a team",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string"
                    }
                },
                "required": ["team_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_ticket_status",
            "description": "Update ticket status",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer"
                    },
                    "status": {
                        "type": "string"
                    }
                },
                "required": ["ticket_id", "status"]
            }
        }
    }
]


async def execute_tool(name, args):

    if name == "get_ticket":
        result = await mcp.get_ticket(args["ticket_id"])

    elif name == "search_open_tickets":
        result = await mcp.search_open_tickets()

    elif name == "search_by_team":
        result = await mcp.search_by_team(args["team_name"])

    elif name == "update_ticket_status":
        result = await mcp.update_ticket_status(
            args["ticket_id"],
            args["status"]
        )

    else:
        result = {
            "error": "Unknown tool"
        }

    return result


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]


while True:

    user = input("\nYou: ")

    if user.lower() == "exit":
        break


    messages.append(
        {
            "role": "user",
            "content": user
        }
    )


    response = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )


    msg = response.choices[0].message


    if msg.tool_calls:

        messages.append(msg)


        for tool_call in msg.tool_calls:

            name = tool_call.function.name

            args = json.loads(
                tool_call.function.arguments
            )


            tool_result = asyncio.run(
                execute_tool(name, args)
            )


            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(tool_result)
                }
            )


        final = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )


        answer = final.choices[0].message.content


    else:

        answer = msg.content


    print("\nAssistant:\n")
    print(answer)


    messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )