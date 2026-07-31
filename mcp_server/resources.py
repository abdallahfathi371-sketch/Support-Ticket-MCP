from pathlib import Path

POLICY_DIR = Path(__file__).parent / "policies"


def read_policy(file_name):
    path = POLICY_DIR / file_name

    if not path.exists():
        return "Policy not found."

    with open(path, "r", encoding="utf-8") as f:
        return f.read()