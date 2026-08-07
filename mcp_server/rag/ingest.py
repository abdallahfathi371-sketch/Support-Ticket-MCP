from .knowledge import get_knowledge_base


if __name__ == "__main__":
    kb = get_knowledge_base()
    print("RAG index built.")
    print("Indexed chunks:", kb.vector.collection.count())
