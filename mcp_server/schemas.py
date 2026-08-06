TOOL_SCHEMAS = {

    "get_ticket": {

        "type": "object",

        "properties": {

            "employee_id": {
                "type": "integer",
                "description": "ID of employee requesting ticket information"
            },

            "ticket_id": {
                "type": "integer",
                "description": "ID of support ticket"
            }

        },

        "required": [
            "employee_id",
            "ticket_id"
        ],

        "additionalProperties": False
    },



    "search_open_tickets": {

        "type": "object",

        "properties": {

            "employee_id": {
                "type": "integer",
                "description": "Employee requesting open tickets"
            }

        },

        "required": [
            "employee_id"
        ],

        "additionalProperties": False
    },



    "search_by_team": {

        "type": "object",

        "properties": {

            "employee_id": {
                "type": "integer",
                "description": "Employee requesting team tickets"
            },

            "team_name": {
                "type": "string",
                "description": "Support team name"
            }

        },

        "required": [
            "employee_id",
            "team_name"
        ],

        "additionalProperties": False
    },



    "update_ticket_status": {

        "type": "object",

        "properties": {

            "employee_id": {
                "type": "integer",
                "description": "Employee performing update"
            },

            "ticket_id": {
                "type": "integer",
                "description": "Ticket to update"
            },

            "status": {
                "type": "string",
                "enum": [
                    "Open",
                    "Pending",
                    "Closed"
                ],
                "description": "New ticket status"
            }

        },

        "required": [
            "employee_id",
            "ticket_id",
            "status"
        ],

        "additionalProperties": False
    },



    "generate_report": {

        "type": "object",

        "properties": {

            "employee_id": {
                "type": "integer",
                "description": "Employee requesting report"
            }

        },

        "required": [
            "employee_id"
        ],

        "additionalProperties": False
    }

}