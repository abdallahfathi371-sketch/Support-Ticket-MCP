import json
import os
import re

from groq import Groq

from .config import GROQ_MODEL


_client = None


def client():
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is required for RAG generation/evaluation.")
        _client = Groq(api_key=key)
    return _client


def chat(system, user, temperature=0):
    response = client().chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


def json_chat(system, user):
    raw = chat(system, user, temperature=0)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return JSON: {raw}")
    return json.loads(match.group(0))
