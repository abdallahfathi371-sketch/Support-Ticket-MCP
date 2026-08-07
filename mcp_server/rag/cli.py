import argparse
import json

from .agentic import AgenticRAG
from .knowledge import get_knowledge_base
from .self_rag import SelfRAG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--mode", choices=["naive", "hybrid", "agentic", "self-rag"], default="self-rag")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    kb = get_knowledge_base()

    if args.mode == "naive":
        result = kb.naive_search(args.query, args.top_k)
        print(json.dumps(result, indent=2))
        return

    if args.mode == "hybrid":
        result = kb.hybrid_search(args.query, args.top_k)
        print(json.dumps(result, indent=2))
        return

    if args.mode == "agentic":
        result = AgenticRAG(kb).answer(args.query, args.top_k)
    else:
        result = SelfRAG(kb).answer(args.query, top_k=args.top_k)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
