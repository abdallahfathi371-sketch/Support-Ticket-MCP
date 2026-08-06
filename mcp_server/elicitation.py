def create_elicitation_request(
    action: str,
    details: dict
):
    """
    Create a human confirmation request
    before executing a sensitive action.
    """

    return {

        "type": "elicitation/create",

        "status": "waiting_for_confirmation",

        "action": action,

        "details": details,

        "message":
            "Human approval is required before continuing."

    }



def input_required(
    message: str,
    fields: list
):

    return {

        "type": "elicitation/create",

        "status": "missing_information",

        "message": message,

        "required_fields": fields

    }