from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from planning.algorithms.decomposition import decompose_goal
from planning.models import Plan


load_dotenv()


from groq_settings import GROQ_MODEL

MODEL_NAME = GROQ_MODEL


def get_planner_llm() -> ChatGroq:
    """
    Create the Groq-backed LangChain chat model used by the
    reference decomposition implementation.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set in the environment."
        )

    return ChatGroq(
        api_key=api_key,
        model=MODEL_NAME,
        temperature=0,
    )


def create_plan(goal: str) -> Plan:
    """
    Create a validated decomposition DAG.

    The actual decomposition logic lives in:
        planning.algorithms.decomposition

    This function only provides the existing Groq model.
    """

    if not goal or not goal.strip():
        raise ValueError(
            "Planning goal cannot be empty."
        )

    llm = get_planner_llm()

    return decompose_goal(
        goal=goal.strip(),
        llm=llm,
    )