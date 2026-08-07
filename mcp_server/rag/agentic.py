from .config import MAX_AGENTIC_ROUNDS, TOP_K
from .knowledge import get_knowledge_base
from .llm import json_chat
from .prompts import AGENTIC_PLAN_PROMPT
from .self_rag import SelfRAG, format_evidence


class AgenticRAG:
    def __init__(self, knowledge_base=None):
        self.kb = knowledge_base or get_knowledge_base()
        self.self_rag = SelfRAG(self.kb)

    def answer(self, query, top_k=TOP_K):
        evidence = []
        current_query = query
        trace = []

        for round_no in range(MAX_AGENTIC_ROUNDS):
            rows = self.kb.hybrid_search(current_query, top_k=top_k)
            evidence.extend(rows)

            # De-duplicate by chunk id.
            unique = {}
            for row in evidence:
                unique[row["id"]] = row
            evidence = list(unique.values())

            relevance = self.self_rag.check_relevance(query, evidence)
            trace.append({
                "round": round_no + 1,
                "query": current_query,
                "relevance": relevance,
            })

            decision = json_chat(
                AGENTIC_PLAN_PROMPT,
                f"ORIGINAL QUESTION:\n{query}\n\nCURRENT EVIDENCE:\n"
                f"{format_evidence(evidence)}\n\n"
                f"RELEVANCE:\n{relevance}",
            )

            if decision.get("action") == "answer":
                break

            current_query = decision.get("query") or query

        # Final answer is verified by Self-RAG against all accumulated evidence.
        # Use the public checks directly so the agentic path retains its trace.
        final_relevance = self.self_rag.check_relevance(query, evidence)
        if float(final_relevance.get("score", 0)) < 0.55:
            return {
                "answer": "I could not find sufficiently relevant policy evidence to answer this safely.",
                "passed": False,
                "trace": trace,
                "sources": evidence,
            }

        answer = self.self_rag.generate(query, evidence)
        support = self.self_rag.check_support(query, answer, evidence)

        passed = bool(support.get("supported")) and float(support.get("score", 0)) >= 0.65
        return {
            "answer": answer if passed else "The retrieved policy evidence did not sufficiently support the generated answer.",
            "passed": passed,
            "trace": trace,
            "retrieval_check": final_relevance,
            "support_check": support,
            "sources": evidence,
        }
