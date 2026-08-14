from __future__ import annotations

import json
import os
import time
from typing import Any

from planning.tests.reasoning_cases import REASONING_CASES
from planning.groq_model import GroqChatModel
from planning.metrics import start_metrics, end_metrics, get_collector, export_summary
from planning.algorithms.plan_and_solve import plan_and_solve
from planning.algorithms.tree_of_thoughts import tree_of_thoughts
from planning.algorithms.lats import lats
from planning.algorithms.environment import Environment


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_case_with_method(case: dict[str, Any], method: str) -> dict[str, Any]:
    llm = GroqChatModel()
    env = Environment()

    start_metrics()
    t0 = time.perf_counter()

    if method == "PS":
        output = plan_and_solve(case["prompt"], llm)
        success = bool(output and output.strip())

    elif method == "ToT":
        thoughts = tree_of_thoughts(case["prompt"], llm, depth=2, beam_width=2)
        output = "\n\n".join([t.state for t in thoughts])
        success = bool(thoughts)

    elif method == "LATS":
        res = lats(case["prompt"], llm, environment=env, iterations=2, n_actions=2)
        output = res.output
        success = bool(res.success)

    else:
        raise ValueError(f"Unsupported method: {method}")

    t1 = time.perf_counter()
    end_metrics()

    metrics = export_summary()
    record = {
        "case_id": case["id"],
        "case_name": case["name"],
        "method": method,
        "success": success,
        "elapsed_sec": t1 - t0,
        "llm_calls": metrics["llm_calls"],
        "total_tokens": metrics["total_tokens"],
        "total_latency_sec": metrics["total_latency_sec"],
        "output": output,
    }

    return record


def main():
    methods = ["PS", "ToT", "LATS"]
    results = []

    for case in REASONING_CASES:
        for method in methods:
            print(f"Running case {case['id']} with {method}...")
            try:
                rec = run_case_with_method(case, method)
                results.append(rec)
                # write artifact
                fname = f"case_{case['id']}_{method}.json"
                with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as fh:
                    json.dump(rec, fh, indent=2)
            except Exception as exc:
                print(f"Error running {case['id']} {method}: {exc}")

    # Save overall JSON
    out_path = os.path.join(OUTPUT_DIR, "evaluation_results.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print(f"Evaluation complete. Artifacts written to {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
