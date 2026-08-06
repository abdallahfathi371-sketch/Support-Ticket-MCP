def ticket_created(ticket_id):

    return {

        "event": "ticket_created",

        "ticket_id": ticket_id,

        "message": 
            f"Ticket {ticket_id} was created."

    }



def ticket_status_changed(
    ticket_id,
    old_status,
    new_status
):

    return {

        "event": "ticket_status_changed",

        "ticket_id": ticket_id,

        "old_status": old_status,

        "new_status": new_status,

        "message":
            f"Ticket {ticket_id} changed from {old_status} to {new_status}"

    }



def tools_changed():

    return {

        "method":
            "notifications/tools/list_changed",

        "message":
            "Available tools changed because user permissions changed."

    }