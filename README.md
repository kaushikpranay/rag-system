# RAG Query Resolution System

An intelligent Retrieval-Augmented Generation (RAG) system built for customer support automation. It uses a LangGraph state machine to retrieve relevant documents, answer user queries, and escalate unanswered questions to human agents when needed.

## Key Features

*   **Two-Stage Retrieval & Cross-Encoder Reranking:** Combines PostgreSQL `pgvector` HNSW vector similarity search with a local cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`). Overfetches candidate chunks (`fetch_k = min(top_k * 4, 30)`) before reranking, using deterministic tiebreaker sorting (`ORDER BY embedding <=> %s::vector, id ASC`).
*   **Intelligent Self-Correction Loop:** Automatically retries document searches up to 3 times with wider parameters (`top_k` and `min_similarity`) if an initial answer has low confidence.
*   **Deduplicated Vector Ingestion:** Uses SHA-256 content hashing with PostgreSQL `ON CONFLICT DO NOTHING` rules to prevent duplicate chunk insertions in the vector database.
*   **Isolated Benchmark Environment:** Synthetic benchmark datasets (54k+ rows) are isolated in a separate `documents_benchmark` table, maintaining a clean production corpus (820 chunks).
*   **Resilient API Handling:** Implements exponential backoff retries (1s, 2s, 4s) for Amazon Bedrock Titan v2 calls, with singleton client reuse to avoid connection overhead.
*   **Comprehensive Test & Evaluation Suite:** Includes an 18-query golden-set retrieval precision benchmark alongside automated vector database tests (ANN Recall@K, HNSW index scan usage, connection pooling, and threshold calibration).
*   **Human-in-the-Loop Escalation:** Unanswered queries are sent to human support agents using Amazon SQS queues.
*   **Cross-User Knowledge Sharing:** Answers verified by human agents are stored back in the vector database as new embeddings, making them available for future user queries.
*   **Session History:** Tracks chat history in Amazon DynamoDB so users can ask natural follow-up questions.
*   **Deployment & Security:** FastAPI backend with strict CORS configuration, input sanitization, and automated deployments to AWS EC2 via GitHub Actions.

## Architecture & Stack

*   **State Machine:** LangGraph
*   **LLM Inference:** Llama-3.1-8b-instant (via Groq API)
*   **Embeddings:** Amazon Bedrock (Titan Text Embeddings v2, 1024 dimensions)
*   **Vector Reranker:** Cross-Encoder `ms-marco-MiniLM-L-6-v2` (`sentence-transformers`)
*   **Vector Database:** Amazon RDS PostgreSQL with `pgvector` (HNSW index)
*   **Session Memory:** Amazon DynamoDB
*   **Message Queue:** Amazon SQS
*   **File Storage:** Amazon S3
*   **Backend:** FastAPI
*   **Frontends:** React + Vite (Chat interface & Support Agent Dashboard, hosted on Vercel)

## Directory Structure

```text
rag-system/
├── app/
│   ├── agent/         # LangGraph state machine and node handlers
│   ├── api/           # FastAPI application and dashboard routers
│   ├── archive/       # S3 storage integration
│   ├── escalation/    # SQS queue producer and worker logic
│   ├── ingestion/     # PDF parsing, text splitting, and embedding logic
│   ├── memory/        # DynamoDB session persistence
│   ├── retrieval/     # pgvector query execution and similarity search
│   ├── summarizer/    # Summarization utilities
│   └── utils/         # Config loaders, PII masking, and helpers
├── frontend/
│   ├── chat/          # End-user chat interface (React)
│   └── dashboard/     # Agent dashboard interface (React)
├── tests/             # Pytest test cases and evaluation suites
│   ├── RETRIEVAL TESTS/
│   │   ├── golden_set.json                # Ground-truth test queries
│   │   ├── measure_thresholds.py          # Precision and recall evaluation
│   │   ├── verify_embedding_integrity.py  # Stored vector integrity check
│   │   ├── diagnose_regression.py         # DB audit and vector dimension verification
│   │   ├── run_ingestion.py               # Ingestion runner script
│   │   └── truncate_documents.py          # Reset helper script
│   └── VECTOR DATABASE TESTS/
│       ├── test_ann_recall.py             # Recall@1, Recall@3, Recall@5 accuracy tests
│       ├── test_hnsw_index.py             # EXPLAIN query plan index verification
│       ├── test_connection_pool.py        # Pool health & concurrency tests
│       ├── test_threshold_calibration.py # Precision-Recall-F1 grid calibration
│       ├── test_large_db_benchmark.py     # Isolated benchmark suite (documents_benchmark)
│       └── benchmark_reporter.py          # Automated benchmark report generator
├── .github/workflows/ # GitHub Actions CI/CD pipelines
└── requirements.txt   # Python package dependencies
```

## Retrieval Benchmarking & Verification

To verify database integrity, test retrieval accuracy, and run vector database benchmarks:

```bash
# Run 18 golden-set retrieval accuracy benchmark (with cross-encoder reranking)
.venv\Scripts\python.exe "tests/RETRIEVAL TESTS/measure_thresholds.py"

# Verify vector integrity (compares stored vs fresh Bedrock embeddings)
.venv\Scripts\python.exe "tests/RETRIEVAL TESTS/verify_embedding_integrity.py"

# Run full Vector Database & pgvector benchmark suite
.venv\Scripts\python.exe -m pytest "tests/VECTOR DATABASE TESTS/"
```

### Measured Performance
- **Retrieval Hit Rate:** **18 out of 18 queries (100.0%)** on golden-set benchmark.
- **Top Rank Correct Chunk Accuracy:** Average correct-chunk similarity (0.5156) > average top wrong-chunk similarity (0.4740)..
- **ANN Recall@1:** **86.67%** (SLA Target: &ge; 70.0%)
- **HNSW Index Scan:** Active and verified via PostgreSQL query plan analysis.
- **Latency Distribution:** P50 Latency = **6.97 ms**, P90 Latency = **11.39 ms**, Average Latency = **6.78 ms**.
- **Embedding Match Score:** **1.000000** cosine similarity between stored and fresh vectors.
- **Invalid Vectors:** 0 zero vectors or NaN/Inf values out of stored chunks.

## Setup & Installation

### 1. Prerequisites
* Python 3.11+
* Node.js (for frontend applications)
* PostgreSQL with `pgvector` extension enabled
* AWS Account (Bedrock, RDS, DynamoDB, SQS, S3)
* Groq API Key

### 2. Environment Configuration
Copy `.env.example` to `.env` and set your credentials:
```bash
cp .env.example .env
```
Ensure `GROQ_API_KEY`, AWS credentials, `RDS_*` connection details, and `FRONTEND_ORIGINS` are configured.

Each frontend application also has a local `.env` configuration for `VITE_API_BASE_URL`.

### 3. Dependencies
```bash
pip install -r requirements.txt
cd frontend/chat && npm install
cd ../dashboard && npm install
```

### 4. Database Setup
`pgvector_client.py` initializes the `vector` extension and creates the `documents` table automatically upon connecting.

## Running the Application

### Start Backend
```bash
uvicorn app.api.main:app --reload
```
API runs locally at `http://localhost:8000/`.

### Start Frontends
```bash
# Chat interface
cd frontend/chat
npm run dev

# Agent dashboard
cd frontend/dashboard
npm run dev
```

## Deployment Details

*   **Backend:** Pushing to `main` triggers GitHub Actions. CI runs pytest; CD connects to an AWS EC2 instance over SSH, updates the code, reinstalls requirements, and restarts uvicorn under supervisorctl behind Nginx.
*   **Frontends:** Both frontends are connected to Vercel and deploy automatically on commits to `main`.
