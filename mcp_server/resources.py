from pathlib import Path


POLICY_DIR = (
    Path(__file__).parent
    / "policies"
)



def read_policy(
    filename: str
):

    path = POLICY_DIR / filename


    if not path.exists():

        return {
            "error":
            "Policy not found."
        }


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return {

            "name": filename,

            "content":
                file.read()

        }



def list_policies():

    files = []


    for file in POLICY_DIR.glob("*.txt"):

        files.append(
            file.name
        )


    return files