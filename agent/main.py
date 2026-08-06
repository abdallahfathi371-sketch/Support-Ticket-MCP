import asyncio
import sys
import os
import json

from dotenv import load_dotenv
from groq import Groq


sys.path.append(
    os.path.dirname(os.path.dirname(__file__))
)


from client import MCPClient
from prompt import SYSTEM_PROMPT
from memory.memory_manager import MemoryManager

from context_eval.strategies import sliding_window



load_dotenv()



mcp_client = MCPClient()


memory = MemoryManager(
    buffer_size=10
)



groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)





async def get_available_tools():

    tools = await mcp_client.list_tools()


    return [

        {
            "name": tool.name,
            "description": tool.description
        }

        for tool in tools

    ]







async def ask_groq(messages):


    response = groq_client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        messages=messages,

        temperature=0

    )


    return response.choices[0].message.content







async def process_user_query(user_input):


    tools = await get_available_tools()



    # ==============================
    # Apply Context Strategy
    # ==============================


    raw_memory = memory.get_short_memory()


    memory_context = sliding_window(

        raw_memory,

        window_size=6

    )




    messages = [


        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },



        {
            "role": "system",

            "content": f"""

Previous Conversation Context:


{json.dumps(memory_context, indent=2)}



Available MCP Tools:


{json.dumps(tools, indent=2)}

"""
        },



        {
            "role": "user",

            "content": user_input
        }


    ]





    response = await ask_groq(messages)





    try:


        tool_request = json.loads(response)



        if "tool" in tool_request:



            tool_name = tool_request["tool"]



            arguments = tool_request.get(

                "arguments",

                {}

            )



            arguments["employee_id"] = 1





            result = await mcp_client.execute_tool(

                tool_name,

                arguments

            )





            # Save tool observation

            memory.remember(

                "tool",

                f"{tool_name}: {result}"

            )



            memory.episodic.add_episode(

                content=f"{tool_name}: {result}",

                reason="Tool observation from MCP call",

                importance=0.8

            )






            final_messages = messages + [



                {
                    "role": "assistant",

                    "content": response
                },



                {
                    "role": "tool",

                    "content": str(result),

                    "tool_call_id": tool_name

                }



            ]






            final_answer = await ask_groq(

                final_messages

            )



            return final_answer






    except json.JSONDecodeError:


        pass





    return response











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

            tool["name"]

        )








    while True:



        user = input("\nYou: ")





        if user.lower() == "exit":



            memory.consolidate()



            print(

                "Memory Saved."

            )



            break





        memory.remember(

            "user",

            user

        )





        answer = await process_user_query(

            user

        )





        print(

            "\nAssistant:"

        )



        print(answer)






        memory.remember(

            "assistant",

            answer

        )





        memory.episodic.add_episode(

            content=answer,

            reason="Assistant response",

            importance=0.5

        )









if __name__ == "__main__":


    asyncio.run(main())