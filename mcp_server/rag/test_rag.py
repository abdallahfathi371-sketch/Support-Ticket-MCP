from mcp_server.rag.knowledge import search_knowledge_base


def test_rag():
    results = search_knowledge_base("refund", 3)

    print("Search Results:\n")

    for result in results:
        print("Document:", result["metadata"]["document"])
        print(result["payload"])
        print("-" * 50)


if __name__ == "__main__":
    test_rag()