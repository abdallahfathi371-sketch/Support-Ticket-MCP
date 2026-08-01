from mcp_server.rag.knowledge import search_knowledge_base

results = search_knowledge_base(
    "refund",
    3
)

print(results)