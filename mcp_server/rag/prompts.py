RAG_SYSTEM = """You are the Coderift Support knowledge assistant.
Answer only from the supplied retrieved evidence.
If the evidence is insufficient, say that the policy corpus does not contain
enough information and do not invent a policy.
Cite evidence using [1], [2], etc. matching the supplied source list.
"""

RELEVANCE_PROMPT = """Grade whether each retrieved passage is relevant to the question.
Return ONLY JSON:
{"relevant": true/false, "score": 0.0, "reason": "..."}
Score 1 means directly answers or materially supports the question.
Score 0 means unrelated.
"""

SUPPORT_PROMPT = """Check whether the proposed answer is supported by the supplied evidence.
Return ONLY JSON:
{"supported": true/false, "score": 0.0, "unsupported_claims": ["..."], "reason": "..."}
Do not reward outside knowledge. Every factual policy claim must be grounded in the evidence.
"""

ANSWER_PROMPT = """Answer the user's question using only the evidence below.
Keep the answer concise and cite factual claims as [1], [2], etc.
If evidence is insufficient, explicitly say so.
"""

AGENTIC_PLAN_PROMPT = """You are deciding whether another retrieval round is necessary.
Return ONLY JSON:
{"action":"retrieve"|"answer", "query":"...", "reason":"..."}
Choose retrieve when the current evidence is insufficient, ambiguous, or needs decomposition.
"""
