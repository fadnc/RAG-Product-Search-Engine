# RAG Product Search Engine — Architecture & Starter Blueprint

> End-to-end blueprint you can implement immediately. Includes architecture, folder layout, API routes, DB schemas, vector DB metadata model, chunking & embedding pipeline, evaluation plan, and starter commands.

---

## 1) Project overview

Build an end-to-end Retrieval-Augmented Generation (RAG) **Product Search Engine** tailored to e-commerce. The system takes user queries, performs semantic + keyword retrieval from a vector index of product documents, reranks results, and uses an LLM to generate explanations / comparisons. The project demonstrates engineering depth (pipelines, infra, monitoring) and product alignment (e-commerce search & recommendations).

**Core goals:**

* Semantic search over product catalog (title, description, specs)
* Hybrid search: semantic + keyword + metadata filters
* RAG layer that uses retrieved passages to produce concise answers and comparisons
* Full-stack delivery with React frontend, FastAPI backend, PostgreSQL for logs/metadata, Vector DB for embeddings
* Monitoring & evaluation: Recall@k, MRR, latency tracking

---

## 2) Tech stack (recommended)

* Backend: Python + FastAPI
* Frontend: React (Vite) + streaming LLM UI
* Embeddings: OpenAI text-embedding-3 / SentenceTransformers
* Vector DB: Pinecone or Chroma (abstracted via a small adapter)
* DB: PostgreSQL (for user/query logs, metadata, versioning)
* Orchestration: Prefect or simple cron (for scheduled ETL)
* Optional: Redis for caching

---

## 3) High-level architecture

1. **Data Ingestion**: Pull product data (CSV / API) -> Clean -> Chunk -> Create embeddings -> Upsert to Vector DB and product table in Postgres.
2. **Query Pipeline (FastAPI)**: Accept query -> Preprocess (spell-check, rewrite) -> Embed query -> Vector DB search (top-k) + keyword filter -> Re-rank using cross-encoder or reranker -> RAG: pass top passages to LLM to generate answer -> Log query & results in Postgres.
3. **Frontend**: React app that sends queries, streams LLM answers, shows product cards and comparison UI.
4. **Analytics**: Dashboard reading Postgres logs, showing Recall@k, latency, top queries.

*(You can implement the LLM calls server-side or via a backend-for-LLM proxy.)*

---

## 4) Folder structure (starter)

```
rag-product-search/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  ├─ routes.py
│  │  │  └─ embeddings.py
│  │  ├─ services/
│  │  │  ├─ vector_store.py
│  │  │  ├─ embedding_service.py
│  │  │  ├─ reranker.py
│  │  │  └─ rag.py
│  │  ├─ models/
│  │  │  └─ schemas.py
│  │  ├─ db/
│  │  │  └─ postgres.py
│  │  └─ utils/
│  │     └─ text_processing.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx
│  │  ├─ components/
│  │  │  ├─ SearchBar.jsx
│  │  │  ├─ ResultsList.jsx
│  │  │  └─ ProductCard.jsx
│  │  └─ services/
│  │     └─ api.js
│  └─ package.json
├─ data/
│  ├─ raw/
│  └─ processed/
├─ notebooks/
│  └─ eval_metrics.ipynb
├─ infra/
│  └─ docker-compose.yml
└─ README.md
```

---

## 5) Database schemas

### PostgreSQL — core tables

```sql
-- products: core product metadata
CREATE TABLE products (
  product_id TEXT PRIMARY KEY,
  title TEXT,
  description TEXT,
  specs JSONB,
  price NUMERIC,
  brand TEXT,
  category TEXT,
  source TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- embeddings metadata (versioning & pointer to vector DB)
CREATE TABLE embeddings (
  embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id TEXT REFERENCES products(product_id),
  chunk_id TEXT,
  text_chunk TEXT,
  embedding_model TEXT,
  vector_id TEXT, -- id in vector DB
  created_at TIMESTAMP DEFAULT now()
);

-- query logs
CREATE TABLE queries (
  query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NULL,
  query_text TEXT,
  rewritten_query TEXT,
  top_k_results JSONB,
  reranker_scores JSONB,
  latency_ms INT,
  created_at TIMESTAMP DEFAULT now()
);
```

Notes: you do not need to store raw vectors in Postgres; store vector IDs and metadata. Storing some chunk text helps with offline debugging.

---

## 6) Vector DB metadata model

When upserting a vector, include the following metadata fields:

```
{
  "product_id": "B0XXXX",
  "chunk_id": "B0XXXX_0",
  "title": "SuperPhone X",
  "brand": "BrandName",
  "category": "smartphones",
  "price": 19999,
  "source": "amazon",
  "language": "en"
}
```

This enables fast filtering by category/brand/price range in hybrid queries.

---

## 7) Chunking strategy (practical)

* Prefer semantic chunking by sentences or paragraphs; fallback to fixed-size tokens.
* Example: target ~200–350 tokens per chunk with 50-token overlap.
* Save chunk_id and chunk_text in `embeddings` table.

---

## 8) Embedding pipeline pseudocode

```python
# ingestion.py (simplified)
for product in products:
    docs = chunk_text(product['description'], target_tokens=300, overlap=50)
    for i, chunk in enumerate(docs):
        embedding = embed(chunk)
        vector_id = vector_db.upsert(embedding, metadata={...})
        postgres.insert('embeddings', {
            'product_id': product['id'],
            'chunk_id': f"{product['id']}_{i}",
            'text_chunk': chunk,
            'embedding_model': EMBEDDING_MODEL,
            'vector_id': vector_id
        })
```

**Notes:** Batch embeddings to reduce API calls. Use exponential backoff on failures.

---

## 9) Query pipeline (detailed)

1. Receive query.
2. Normalize & spell-correct.
3. Optionally rewrite query for intent (e.g., add constraints: "under 60k INR").
4. Embed query.
5. Vector DB search: top_k = 50 with metadata filter (category, price range).
6. Rerank top_k with a cross-encoder or a cheap coherence score; keep top 5–10.
7. Compose context prompt with top passages and call LLM to generate final answer.
8. Log query, latency, and returned product ids.

**FastAPI endpoint**: `/search` (POST) with body `{query, filters, k}` returns `{answer, products, citations}`.

---

## 10) FastAPI routes (starter)

```py
# routes.py
POST /search -> handle search (main pipeline)
POST /embed -> embed a single text (useful for debugging)
POST /upsert_products -> upload product csv/json and ingest
GET  /products/{product_id} -> return product metadata
GET  /analytics/top_queries -> return aggregated stats
```

---

## 11) Reranker & scoring

* Use a cross-encoder (small transformer) if you can afford it for accuracy.
* Heuristic rerank: TF-IDF score + cosine similarity + metadata match boost.
* Save reranker scores in `queries.reranker_scores` for offline analysis.

---

## 12) Frontend components

* `SearchBar` — typed query input, filters
* `ResultsList` — paginated product cards + relevance score
* `ProductCard` — image, price, short spec, link to full product
* `ChatAnswer` — LLM-generated summary with citations (product ids)
* `ComparisonModal` — compare 2–4 products side-by-side

API service layer: `services/api.js` with `search(query, filters)` returning streaming responses when available.

---

## 13) Evaluation

* Offline: use held-out queries with labeled relevant products. Compute Recall@k, Precision@k, MRR.
* Online: click-through rate from UI, re-query rate, average latency.

---

## 14) Logging & monitoring

* Log each query row in Postgres with timestamp, latency, top_k ids, user id(optional)
* Export metrics to Prometheus or simple CSV for dashboards
* Monitor vector DB latency and embedding API error rate

---

## 15) Environment variables (example)

```
OPENAI_API_KEY=...
VECTOR_DB_API_KEY=...
POSTGRES_URL=postgresql://user:pass@host:5432/db
EMBEDDING_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4o-mini
```

---

## 16) Dev run commands (starter)

**Backend (venv)**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend (Vite)**

```bash
cd frontend
npm install
npm run dev
```

---

## 17) README starter content (copy-paste)

Add a short README explaining how to run ingestion, start services, and where to put datasets. Include a small sample dataset in `/data/raw/sample_products.json` to let reviewers try the app quickly.

---

## 18) Quick MVP checklist (minimum to demo)

* [ ] Ingest 5k product records, create embeddings, upsert to vector DB
* [ ] Implement `/search` endpoint returning top-5 product cards
* [ ] React UI to query and show results
* [ ] Basic RAG answer generation for a single product explanation
* [ ] Logging of queries to Postgres

---

## 19) Nice-to-have (next-level polish)

* Streaming LLM responses in the UI
* Query rewriting model for intent normalization
* Automatic price normalization across sources
* A/B evaluation harness for different rerankers

---

## 20) Next steps I can do for you immediately

* Generate the **FastAPI backend starter code** (routes + embedding adapter + vector-store adapter + simple `search` pipeline) — ready to run locally.
* Generate the **React frontend skeleton** that calls the `/search` endpoint and displays streaming answers.
* Create a **data ingestion script** that takes a CSV/JSON and populates Postgres + Vector DB (mock adapter if you don’t have a real key).

Tell me which of the above you'd like first and I will generate the code now.

---

*End of blueprint.*
