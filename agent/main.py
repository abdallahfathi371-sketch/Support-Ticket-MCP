import asyncio

from client import MCPClient
from prompt import SYSTEM_PROMPT


client = MCPClient()



async def show_tools():

    tools = await client.list_tools()

    print("\nAvailable Tools:")

    for tool in tools:

        print(
            "-",
            tool.name
        )



async def main():

    await client.connect()


    capabilities = await client.check_capabilities()


    print(
        "\nServer Capabilities:"
    )


    print(
        capabilities
    )


    print(
        "\nCoderift Support Assistant Started"
    )


    await show_tools()


    while True:


        user = input(
            "\nYou: "
        )


        if user.lower() == "exit":

            break



        if user.startswith(
            "ticket "
        ):

            ticket_id = int(
                user.split()[1]
            )

            result = await client.get_ticket(
                ticket_id
            )


            print(
                "\nAssistant:"
            )

            print(result)



        elif user == "open tickets":


            result = await client.search_open_tickets()


            print(
                result
            )



        elif user.startswith(
            "team "
        ):


            team = user.replace(
                "team ",
                ""
            )


            result = await client.search_by_team(
                team
            )


            print(
                result
            )



        elif user.startswith(
            "close "
        ):


            ticket_id = int(
                user.replace(
                    "close ",
                    ""
                )
            )


            result = await client.update_ticket_status(

                ticket_id,

                "Closed"

            )


            print(
                result
            )



        elif user == "report":


            result = await client.generate_report()

            print(
                result
            )



        elif user == "dashboard":


            result = await client.get_dashboard()

            print(
                result
            )



        else:

            print(
                """
Commands:

ticket <id>
open tickets
team <name>
close <id>
report
dashboard
exit

"""
            )



if __name__ == "__main__":

    asyncio.run(
        main()
    )