from .questions import load_questions
from mcp_server.rag.knowledge import get_knowledge_base
from mcp_server.rag.llm import chat
from mcp_server.rag.prompts import RAG_SYSTEM, ANSWER_PROMPT


def evidence_text(rows):
    blocks = []
    for i, row in enumerate(rows, 1):
        blocks.append(
            f"[{i}] {row['metadata'].get('document', 'unknown')}\n{row['text']}"
        )
    return "\n\n".join(blocks)


def generate_answer(question, rows):
    return chat(
        RAG_SYSTEM + "\n" + ANSWER_PROMPT,
        f"QUESTION:\n{question}\n\nEVIDENCE:\n{evidence_text(rows)}",
    )


def run_architecture(question, architecture, top_k=5):
    kb = get_knowledge_base()

    if architecture == "naive":
        rows = kb.naive_search(question, top_k)
    elif architecture == "hybrid":
        rows = kb.hybrid_search(question, top_k)
    else:
        from mcp_server.rag.agentic import AgenticRAG
        result = AgenticRAG(kb).answer(question, top_k)
        return result.get("answer", ""), result.get("sources", [])

    return generate_answer(question, rows), rows
