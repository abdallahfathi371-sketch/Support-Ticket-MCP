# Retrieval Evaluation

The fixed test set is `questions.json`.

Architectures compared:

- **Naive RAG**: embedding + Chroma/HNSW retrieval.
- **Hybrid RAG**: vector retrieval + BM25 with reciprocal-rank fusion.
- **Agentic RAG**: multi-round retrieval where the LLM can request another search.

For every architecture, the evaluation records:

- correctness
- source retrieval hit
- expected-answer keyword hit
- estimated input tokens
- estimated output tokens
- latency

Run:

```bash
python -m retrieval_eval.evaluate
```

Self-RAG verification is evaluated separately:

```bash
python -m retrieval_eval.self_rag_eval
```

The scripts generate the numbers. Do not write benchmark values into documentation until the fixed test set has actually been executed.
