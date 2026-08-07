# RAG + Retrieval Evaluation + Self-RAG Extension

This is a drop-in extension for `Support-Ticket-MCP`.

The existing repository already contains:
- FastMCP server
- SQLite ticket database
- policy files under `mcp_server/policies/`
- a basic keyword-only RAG implementation

The original RAG code only chunks policy text and uses BM25-style keyword search. The extension upgrades it to a real retrieval layer with an ANN vector index, metadata filtering, hybrid retrieval, agentic retrieval, evaluation, and Self-RAG verification.

## 1. Architecture

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

Chroma provides the persistent local vector database and HNSW ANN index. Metadata is stored alongside each chunk and passed as a query filter when filtering is requested.

## 2. Install

Add these packages to your existing `requirements.txt`:

```text
chromadb
sentence-transformers
rank-bm25
groq
python-dotenv
```

Do not remove the packages already required by the MCP server.

Then:

```bash
pip install -r requirements.txt
```

Set:

```env
GROQ_API_KEY=your_key
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
GROQ_MODEL=llama-3.3-70b-versatile
```

Never commit `.env`.

## 3. Build the index

From the repository root:

```bash
python -m mcp_server.rag.ingest
```

This creates:

```text
db/chroma_rag/
```

The first run downloads the sentence-transformer model.

## 4. Test retrieval

```bash
python -m mcp_server.rag.cli "What is the response target for high priority tickets?" --mode naive
python -m mcp_server.rag.cli "What is the response target for high priority tickets?" --mode hybrid
```

## 5. Self-RAG

```bash
python -m mcp_server.rag.cli "Can customers directly update ticket status?" --mode self-rag
```

Self-RAG performs:
1. retrieval
2. retrieval relevance grading
3. grounded generation
4. answer support grading
5. refusal when either check fails

The important point is that the model is not trusted merely because a nearest-neighbor result exists.

## 6. Agentic RAG

```bash
python -m mcp_server.rag.cli \
  "Compare low and medium priority service targets." \
  --mode agentic
```

Agentic RAG can perform another retrieval round when the first evidence is insufficient.

## 7. Retrieval evaluation

The fixed test set is:

```text
retrieval_eval/questions.json
```

Run:

```bash
python -m retrieval_eval.evaluate
```

This produces `retrieval_eval/results.json`.

Run Self-RAG evaluation:

```bash
python -m retrieval_eval.self_rag_eval
```

This produces `retrieval_eval/self_rag_results.json`.

The scripts intentionally calculate real numbers at runtime. Do not put fabricated benchmark numbers in the README.

## 8. MCP integration

Add this import near the existing tool imports in `mcp_server/server.py`:

```python
from . import tools_rag
```

The new MCP tools are:

- `search_knowledge`
- `answer_from_knowledge`
- `answer_agentic_rag`

They reuse the existing employee authorization system.

Add the new action to `mcp_server/authorization.py`:

```python
"search_knowledge",
```

for the roles that should be allowed to read policies. The supplied patch assumes `support` and `admin` should have it; keep `viewer` restricted if that matches your security model.

## 9. Agent integration

The easiest integration is to let the existing Groq agent call the new MCP tools just like its current ticket tools.

Add the import:

```python
from mcp_server import tools_rag
```

or, preferably, load the tools dynamically through the existing MCP client as the current agent already does.

The current repository already discovers MCP tools dynamically, so once `tools_rag` is imported by `mcp_server/server.py`, the agent can discover them without duplicating the RAG implementation.

## 10. Why this fixes the existing RAG implementation

The original `mcp_server/rag/keyword_store.py` is a BM25-only in-memory store. It is useful as a keyword baseline but it is not a vector database or ANN architecture.

This extension adds:

- persistent Chroma vector database
- HNSW ANN index
- sentence-transformer embeddings
- metadata payloads
- metadata filtering during retrieval
- BM25 keyword retrieval
- reciprocal-rank fusion
- naive RAG
- hybrid RAG
- agentic RAG
- fixed retrieval evaluation set
- latency/token metrics
- explicit Self-RAG relevance grading
- explicit Self-RAG support grading
- safe refusal when verification fails

## 11. Important grading note

The assignment asks for actual comparison numbers and says the test set must remain fixed. Run the evaluation scripts after the implementation is installed, then paste the generated numbers into the project's main README.

Do not claim numbers before running the scripts.
