from .config import SELF_RAG_MIN_RELEVANCE, SELF_RAG_MIN_SUPPORT, TOP_K
from .knowledge import get_knowledge_base
from .llm import chat, json_chat
from .prompts import (
    RAG_SYSTEM,
    RELEVANCE_PROMPT,
    SUPPORT_PROMPT,
    ANSWER_PROMPT,
)


def format_evidence(rows):
    if not rows:
        return "NO EVIDENCE RETRIEVED."

    blocks = []
    for i, row in enumerate(rows, 1):
        source = row["metadata"].get("document", "unknown")
        blocks.append(f"[{i}] Source: {source}\n{row['text']}")
    return "\n\n".join(blocks)


class SelfRAG:
    """
    Self-RAG-style pipeline:
      1. retrieve
      2. verify retrieval relevance
      3. generate grounded answer
      4. verify answer support
      5. refuse/retrieve again when checks fail
    """

    def __init__(self, knowledge_base=None):
        self.kb = knowledge_base or get_knowledge_base()

    def check_relevance(self, query, rows):
        if not rows:
            return {
                "relevant": False,
                "score": 0.0,
                "reason": "No passages retrieved.",
            }

        result = json_chat(
            RELEVANCE_PROMPT,
            f"QUESTION:\n{query}\n\nPASSAGES:\n{format_evidence(rows)}",
        )
        return result

    def generate(self, query, rows):
        return chat(
            RAG_SYSTEM + "\n" + ANSWER_PROMPT,
            f"QUESTION:\n{query}\n\nEVIDENCE:\n{format_evidence(rows)}",
        )

    def check_support(self, query, answer, rows):
        return json_chat(
            SUPPORT_PROMPT,
            f"QUESTION:\n{query}\n\nANSWER:\n{answer}\n\nEVIDENCE:\n{format_evidence(rows)}",
        )

    def answer(self, query, mode="hybrid", top_k=TOP_K):
        rows = (
            self.kb.naive_search(query, top_k)
            if mode == "naive"
            else self.kb.hybrid_search(query, top_k)
        )

        relevance = self.check_relevance(query, rows)
        if float(relevance.get("score", 0)) < SELF_RAG_MIN_RELEVANCE:
            return {
                "answer": "I could not find sufficiently relevant policy evidence to answer this safely.",
                "passed": False,
                "retrieval_check": relevance,
                "support_check": None,
                "sources": rows,
            }

        answer = self.generate(query, rows)
        support = self.check_support(query, answer, rows)

        if (
            not support.get("supported", False)
            or float(support.get("score", 0)) < SELF_RAG_MIN_SUPPORT
        ):
            return {
                "answer": "I found relevant policy material, but it did not sufficiently support a safe answer.",
                "passed": False,
                "retrieval_check": relevance,
                "support_check": support,
                "sources": rows,
            }

        return {
            "answer": answer,
            "passed": True,
            "retrieval_check": relevance,
            "support_check": support,
            "sources": rows,
        }
