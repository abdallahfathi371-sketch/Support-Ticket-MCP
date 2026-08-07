# RAG + Retrieval Evaluation + Self-RAG Extension


##  Architecture

```text
                 ┌──────────────────────────┐
                 │ mcp_server/policies/*.txt│
                 └────────────┬─────────────┘
                              │
                         chunk + metadata
                              │
                 ┌────────────┴─────────────┐
                 │                          │
          SentenceTransformer            BM25Plus
                 │                          │
             Chroma/HNSW                keyword index
                 │                          │
                 └────────────┬─────────────┘
                              │
                    Naive / Hybrid RAG
                              │
                       Agentic RAG loop
                              │
                    Self-RAG verification
                    ┌─────────┴─────────┐
                    │                   │
               relevance check     support check
                    │                   │
                    └─────────┬─────────┘
                              │
                    grounded answer/refusal
```



