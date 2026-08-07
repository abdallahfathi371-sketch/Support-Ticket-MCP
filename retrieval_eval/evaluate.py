import json
import time
from pathlib import Path

from .questions import load_questions
from .rag_pipeline import run_architecture


ROOT = Path(__file__).resolve().parent


def estimate_tokens(text):
    # Stable local estimate for comparison. Replace with provider tokenizer
    # if you need exact billing-token counts.
    return max(1, len(text.split()))


def expected_sources_present(expected_sources, rows):
    sources = {r["metadata"].get("document") for r in rows}
    return all(source in sources for source in expected_sources)


def answer_matches(answer, expected_keywords):
    text = answer.lower()
    return all(k.lower() in text for k in expected_keywords)


def run():
    questions = load_questions()
    records = []

    for item in questions:
        for architecture in ("naive", "hybrid", "agentic"):
            start = time.perf_counter()
            answer, rows = run_architecture(
                item["question"],
                architecture,
                top_k=5,
            )
            latency_ms = (time.perf_counter() - start) * 1000

            source_hit = expected_sources_present(
                item["expected_sources"],
                rows,
            )
            answer_hit = answer_matches(
                answer,
                item["expected_keywords"],
            )

            context = "\n".join(r["text"] for r in rows)

            records.append({
                "question_id": item["id"],
                "architecture": architecture,
                "correct": bool(source_hit and answer_hit),
                "source_hit": bool(source_hit),
                "answer_keyword_hit": bool(answer_hit),
                "retrieved_chunks": len(rows),
                "estimated_input_tokens": estimate_tokens(
                    item["question"] + "\n" + context
                ),
                "estimated_output_tokens": estimate_tokens(answer),
                "latency_ms": round(latency_ms, 2),
                "answer": answer,
            })

    out = ROOT / "results.json"
    out.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print("\nRetrieval Architecture Evaluation")
    print("=" * 90)

    for architecture in ("naive", "hybrid", "agentic"):
        subset = [r for r in records if r["architecture"] == architecture]
        accuracy = sum(r["correct"] for r in subset) / len(subset)
        avg_input = sum(r["estimated_input_tokens"] for r in subset) / len(subset)
        avg_output = sum(r["estimated_output_tokens"] for r in subset) / len(subset)
        avg_latency = sum(r["latency_ms"] for r in subset) / len(subset)

        print(
            f"{architecture:10s} | "
            f"accuracy={accuracy:.2%} | "
            f"input_tokens={avg_input:.1f} | "
            f"output_tokens={avg_output:.1f} | "
            f"latency_ms={avg_latency:.1f}"
        )

    print(f"\nDetailed results: {out}")


if __name__ == "__main__":
    run()
