from .database import get_connection



def validate_exists(
    table,
    column,
    value
):

    conn = get_connection()

    cursor = conn.cursor()


    query = f"""
    SELECT 1
    FROM {table}
    WHERE {column}=?
    """


    cursor.execute(
        query,
        (value,)
    )


    result = cursor.fetchone()

    conn.close()


    if result is None:

        raise Exception(
            f"{table} with {column}={value} does not exist."
        )


    return True



def validate_choice(
    value,
    allowed,
    field
):

    if value not in allowed:

        raise Exception(
            f"Invalid {field}. Allowed values: {allowed}"
        )


    return True



def validate_positive_integer(
    value,
    field
):

    if not isinstance(value, int) or value <= 0:

        raise Exception(
            f"{field} must be positive integer."
        )


    return True