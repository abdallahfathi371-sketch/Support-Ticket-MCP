from .app import mcp
from .rag.knowledge import get_knowledge_base
from .rag.self_rag import SelfRAG
from .rag.agentic import AgenticRAG
from .authorization import authorize


@mcp.tool()
def search_knowledge(
    employee_id: int,
    query: str,
    mode: str = "hybrid",
    top_k: int = 5,
):
    """Search the support policy corpus using naive vector or hybrid retrieval."""
    authorize(employee_id, "search_knowledge")

    if mode not in {"naive", "hybrid"}:
        raise ValueError("mode must be 'naive' or 'hybrid'")

    kb = get_knowledge_base()
    rows = (
        kb.naive_search(query, top_k)
        if mode == "naive"
        else kb.hybrid_search(query, top_k)
    )

    return {
        "success": True,
        "mode": mode,
        "query": query,
        "results": rows,
    }


@mcp.tool()
def answer_from_knowledge(
    employee_id: int,
    query: str,
    mode: str = "hybrid",
    top_k: int = 5,
):
    """Answer from retrieved policy evidence with Self-RAG verification."""
    authorize(employee_id, "search_knowledge")
    result = SelfRAG(get_knowledge_base()).answer(query, mode=mode, top_k=top_k)
    return {
        "success": True,
        **result,
    }


@mcp.tool()
def answer_agentic_rag(
    employee_id: int,
    query: str,
    top_k: int = 5,
):
    """Use multi-round agentic retrieval followed by Self-RAG verification."""
    authorize(employee_id, "search_knowledge")
    result = AgenticRAG(get_knowledge_base()).answer(query, top_k=top_k)
    return {
        "success": True,
        **result,
    }
