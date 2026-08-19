RAG Service — PDF / DOC / DOCX / TXT Retrieval-Augmented Generation API
A production-structured Retrieval-Augmented Generation backend. Upload PDF, DOC, DOCX, or TXT files (or submit raw text directly), and ask questions answered from their content, with source citations back to the originating document and page.

1. Project Overview
The service implements the full RAG flow end-to-end:

Upload PDF/DOC/DOCX/TXT/raw text
        │
        ▼
  File validation
        │
        ▼
Text extraction (per-format loader)
        │
        ▼
Text cleaning / normalization
        │
        ▼
   Chunking (paragraph → sentence → hard limit)
        │
        ▼
  Embedding generation (local or OpenAI)
        │
        ▼
 PostgreSQL + pgvector (vector storage)
       User question
            │
            ▼
     Query validation
            │
            ▼
     Query embedding
            │
            ▼
   pgvector similarity search
            │
            ▼
  Similarity threshold filter
            │
            ▼
   Optional reranking
            │
            ▼
   Context construction
            │
            ▼
      LLM (Ollama / OpenAI)
            │
            ▼
   Answer + source citations
Every provider (embedding model, LLM, vector store, storage backend, document loader, reranker) sits behind an abstract interface, so swapping e.g. OpenAI → Ollama, or PostgreSQL → another vector database, does not require touching the pipeline logic.

2. Architecture
backend/app/
├── main.py                 FastAPI app, routers, startup checks
├── api/
│   ├── routes/              documents.py, search.py, chat.py, health.py
│   └── dependencies.py      wires concrete providers into the abstractions
├── core/                    config.py, logging.py, exceptions.py
├── ingestion/                pdf_loader.py, doc_loader.py, docx_loader.py,
│                             txt_loader.py, text_loader.py, base.py, registry.py,
│                             ingestion_service.py (orchestrates the full flow)
├── processing/               cleaner.py, chunker.py, metadata.py
├── embeddings/                embedding_service.py (local + OpenAI)
├── vectorstore/               base.py, pgvector_store.py
├── retrieval/                 retriever.py, reranker.py
├── llm/                        llm_service.py (Ollama + OpenAI-compatible), prompt.py
├── rag/                        pipeline.py (central orchestrator), context_builder.py
├── database/                   connection.py, models.py
├── schemas/                    documents.py, chat.py, search.py
└── storage/                    base.py, local_storage.py
Key design decisions

DocumentLoader is a single interface (load(path) -> list[DocumentPage]) implemented by every file-type loader, keeping extraction logic fully decoupled from embedding/chunking logic.
.doc (legacy binary Word) cannot be parsed reliably in pure Python. The loader shells out to LibreOffice (soffice --headless --convert-to docx) as a clear, swappable fallback, and raises an actionable error if LibreOffice isn't available rather than failing silently.
Chunking prefers paragraph boundaries, then sentence boundaries, and only falls back to a hard character split for a single sentence that exceeds MAX_CHUNK_SIZE.
Embeddings and LLM calls are both provider-agnostic; EMBEDDING_PROVIDER / LLM_PROVIDER env vars pick the implementation. Embedding dimension is validated on every batch against EMBEDDING_DIMENSION — a mismatch raises immediately instead of silently corrupting the vector index.
The RAG pipeline (app/rag/pipeline.py) is the only place that sequences retrieve → rerank → build context → call LLM → extract citations. API routes never contain this logic directly.
Frontend
frontend/ is a plain HTML/CSS/JS static site — no build tooling, no framework, no bundler — served by nginx in its own container. It talks to the backend only through the public REST API (upload, list, delete, reindex, search, chat), exactly as any other API consumer would; it holds no RAG logic of its own. See frontend/index.html, frontend/app.js, and frontend/style.css.

3. Database Schema
documents

column	type
id	uuid PK
filename	string
original_filename	string
file_type	string
file_size	bigint
content_hash	string (unique, SHA-256, used for dedup)
status	uploaded / processing / completed / failed
error_message	text, nullable
chunk_count	integer
doc_metadata	json
created_at / updated_at	timestamps
document_chunks

column	type
id	uuid PK
document_id	uuid FK → documents (cascade delete)
chunk_index	integer
content	text
embedding	vector(EMBEDDING_DIMENSION)
page_number	integer, nullable
section	string, nullable
chunk_metadata	json
created_at	timestamp
An ivfflat cosine-distance index is created on document_chunks.embedding for fast approximate nearest-neighbor search.

4. Docker Architecture
docker-compose.yml
├── postgres   (pgvector/pgvector:pg16, persistent named volume)
├── backend    (FastAPI, built from backend/Dockerfile)
├── frontend   (static UI, served by nginx, built from frontend/Dockerfile, port 3000)
└── ollama     (optional, profile "ollama" — only starts if requested)
The backend always talks to Postgres via the Docker service name (postgres), never localhost. Uploaded files persist in a named volume (rag_uploads_data) so they survive container restarts.

5. Environment Variables
See .env.example for the full annotated list. The important ones:

Variable	Purpose
DATABASE_URL / DATABASE_URL_SYNC	async / sync Postgres connection strings
EMBEDDING_PROVIDER	ollama (Ollama nomic-embed-text), local (sentence-transformers), or openai
EMBEDDING_DIMENSION	must match the model output and the DB schema
LLM_PROVIDER	ollama, openai, or openai_compatible
TOP_K, SIMILARITY_THRESHOLD	retrieval tuning
CHUNK_SIZE, CHUNK_OVERLAP	chunking tuning
RERANKING_ENABLED	true/false
Never commit a real .env file with live API keys.

6. Requirements
Docker & Docker Compose
If LLM_PROVIDER=ollama (the default): either run the optional ollama compose profile, or point LLM_BASE_URL at an existing Ollama instance, and pull a model (e.g. docker exec -it rag-ollama ollama pull llama3.1).
If LLM_PROVIDER=openai or EMBEDDING_PROVIDER=openai: a valid LLM_API_KEY / EMBEDDING_API_KEY.
7. Setup
Quickest path: one command
git clone <this-repo>
cd rag-project
chmod +x setup.sh
./setup.sh
This creates .env from the template, builds and starts Postgres + backend + frontend, waits for the backend to become healthy, and runs database migrations for you.

If you want to use the default LLM_PROVIDER=ollama, run this instead so it also starts Ollama and pulls the configured model:

./setup.sh --with-ollama
(Or, with make available: make start / make start-ollama. See other shortcuts with make status, make logs, make stop, make reset.)

When it finishes you'll see:

Web UI:       http://localhost:3000
API docs:     http://localhost:8000/docs
Health check: http://localhost:8000/api/v1/health/ready
If you're instead using LLM_PROVIDER=openai (or any OpenAI-compatible remote endpoint), skip --with-ollama and put a valid LLM_API_KEY in .env before running ./setup.sh.

Manual path (equivalent, step by step)
git clone <this-repo>
cd rag-project

cp .env.example .env
# edit .env if you want to change providers, models, or ports

docker compose build

# start Postgres + backend + frontend
docker compose up -d

# (optional) also start a local Ollama runtime
docker compose --profile ollama up -d

# run database migrations
docker compose exec backend alembic upgrade head
If using Ollama, pull the model referenced by LLM_MODEL in .env:

docker compose exec ollama ollama pull llama3.1
8. Verify
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health/ready
Open the interactive API docs:

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
Open the web UI ("The Reading Room"):

http://localhost:3000
It's a static frontend (no build step, no separate backend of its own) that talks directly to the API at http://localhost:8000/api/v1 from your browser. From there you can drag-and-drop a file or paste raw text into the catalog on the left, watch its status move from uploaded → processing → completed, then ask questions in the reading desk on the right. Each answer shows its source documents, pages, and similarity scores. You can optionally scope a question to a single document via the "Search within" dropdown.

If you deploy the backend somewhere other than localhost:8000, edit frontend/config.js (window.RAG_CONFIG.API_BASE) before building the frontend image.

9. Upload a Document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/path/to/report.pdf"
Submit raw text instead of a file:

curl -X POST http://localhost:8000/api/v1/documents/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Our refund policy allows returns within 30 days.", "filename": "policy-note.txt"}'
List documents / check processing status:

curl http://localhost:8000/api/v1/documents
curl http://localhost:8000/api/v1/documents/<document_id>
10. Search
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the refund policy?", "top_k": 5}'
11. Chat (full RAG)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the refund policy?"}'
Response:

{
  "success": true,
  "data": {
    "answer": "Refunds are accepted within 30 days of purchase.",
    "sources": [
      {"document_id": "...", "filename": "policy.pdf", "page": 2, "chunk_id": "...", "score": 0.91}
    ]
  }
}
12. Switching Providers
Edit .env, then docker compose restart backend (embedding provider changes also require re-running ingestion/reindexing since vectors from different models are not interchangeable):

Ollama (nomic-embed-text):
EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=nomic-embed-text EMBEDDING_DIMENSION=768

Local sentence-transformers:
EMBEDDING_PROVIDER=local EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 EMBEDDING_DIMENSION=384

OpenAI:
EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-small EMBEDDING_DIMENSION=1536 EMBEDDING_API_KEY=sk-...


```env
# Local Ollama:
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://ollama:11434

# OpenAI:
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
If you change EMBEDDING_DIMENSION, update the Alembic migration's vector column size (or add a new migration) and re-run alembic upgrade head before ingesting any documents — pgvector will reject mismatched vector dimensions.

13. Logs
docker compose logs -f backend
14. Stop
docker compose down
15. Reset the Database
docker compose down -v   # removes named volumes, including postgres data and uploads
docker compose up -d
docker compose exec backend alembic upgrade head
16. Testing
cd backend
pip install -r requirements.txt
pytest -q
The test suite covers text cleaning, chunking (including overlap and edge cases), content-hash deduplication, PDF/DOCX/TXT extraction (generated fixtures, no external files needed), reranking behavior, and the API layer (via dependency overrides, no live database required for these tests). Tests that exercise real similarity ranking against Postgres/pgvector require a live database — run them against the docker compose stack described above.

17. Reindexing a Document
curl -X POST http://localhost:8000/api/v1/documents/<document_id>/reindex
18. Deleting a Document
curl -X DELETE http://localhost:8000/api/v1/documents/<document_id>
Deleting a document cascades to its chunks and embeddings automatically (ON DELETE CASCADE at the database level).

Notes & Known Limitations
Scanned/image-only PDFs are detected (a clear no_extractable_text error is returned) but OCR is not implemented; the loader interface is structured so an OCR-backed loader could be added without changing any other code.
.doc support depends on LibreOffice being present in the backend image (installed by default in the provided Dockerfile). If you build a slimmer custom image without it, .doc uploads will fail with a clear, actionable error rather than corrupting data.
The default reranker is a lightweight lexical-overlap re-scorer (no extra model download) — swap in a cross-encoder model behind the same Reranker interface for higher-quality reranking if needed.
Background ingestion uses FastAPI BackgroundTasks (in-process), which is sufficient for moderate load. For heavier throughput, swap in a real task queue (Celery/RQ) behind the same IngestionService.process_document() call.