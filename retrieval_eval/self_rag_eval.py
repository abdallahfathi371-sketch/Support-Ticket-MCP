import json
import time
from pathlib import Path

from mcp_server.rag.self_rag import SelfRAG
from .questions import load_questions


ROOT = Path(__file__).resolve().parent


def run():
    rag = SelfRAG()
    records = []

    for item in load_questions():
        start = time.perf_counter()
        result = rag.answer(item["question"], mode="hybrid", top_k=5)
        latency_ms = (time.perf_counter() - start) * 1000

        records.append({
            "question_id": item["id"],
            "passed": result["passed"],
            "retrieval_score": result.get("retrieval_check", {}).get("score", 0),
            "support_score": (
                result.get("support_check", {}).get("score", 0)
                if result.get("support_check")
                else 0
            ),
            "latency_ms": round(latency_ms, 2),
            "answer": result["answer"],
            "sources": [
                r["metadata"].get("document")
                for r in result.get("sources", [])
            ],
        })

    out = ROOT / "self_rag_results.json"
    out.write_text(json.dumps(records, indent=2), encoding="utf-8")

    passed = sum(r["passed"] for r in records)
    print(f"Self-RAG passed: {passed}/{len(records)}")
    print(f"Detailed results: {out}")


if __name__ == "__main__":
    run()
