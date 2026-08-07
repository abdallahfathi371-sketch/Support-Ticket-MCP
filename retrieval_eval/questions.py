import json
from pathlib import Path


def load_questions():
    path = Path(__file__).resolve().parent / "questions.json"
    return json.loads(path.read_text(encoding="utf-8"))
