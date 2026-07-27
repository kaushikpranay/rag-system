# RAG Query Resolution System

An intelligent Retrieval-Augmented Generation (RAG) system built for customer support automation. It uses a LangGraph state machine to retrieve relevant documents, answer user queries, and escalate unanswered questions to human agents when needed.

## Key Features

*   **Intelligent Retrieval Loop:** Automatically retries document searches up to 3 times with wider parameters (`top_k` and `min_similarity`) if an initial answer has low confidence.
*   **Deduplicated Vector Ingestion:** Uses SHA-256 content hashing with PostgreSQL `ON CONFLICT DO NOTHING` rules to prevent duplicate chunk insertions in the vector database.
*   **Resilient API Handling:** Implements exponential backoff retries (1s, 2s, 4s) for Amazon Bedrock Titan v2 calls, with singleton client reuse to avoid connection overhead.
*   **Data Cleaning & Connection Auto-Detection:** Automatically removes null bytes (`\x00`) from PDF text and detects active local database connections (port 15432 SSH tunnel or 5432 PostgreSQL).
*   **Retrieval Evaluation Suite:** Includes an 18-query golden-set benchmark measuring retrieval precision and verifying stored vector integrity via fresh Bedrock cosine similarity comparisons.
*   **Human-in-the-Loop Escalation:** Unanswered queries are sent to human support agents using Amazon SQS queues.
*   **Cross-User Knowledge Sharing:** Answers verified by human agents are stored back in the vector database as new embeddings, making them available for future user queries.
*   **Session History:** Tracks chat history in Amazon DynamoDB so users can ask natural follow-up questions.
*   **Deployment & Security:** FastAPI backend with strict CORS configuration, input sanitization, and automated deployments to AWS EC2 via GitHub Actions.

## Architecture & Stack

*   **State Machine:** LangGraph
*   **LLM Inference:** Llama-3.1-8b-instant (via Groq API)
*   **Embeddings:** Amazon Bedrock (Titan Text Embeddings v2, 1024 dimensions)
*   **Vector Database:** Amazon RDS PostgreSQL with pgvector
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
├── tests/             # Pytest test cases and evaluation scripts
│   └── RETRIEVAL TESTS/
│       ├── golden_set.json                # Ground-truth test queries
│       ├── measure_thresholds.py          # Precision and recall evaluation
│       ├── verify_embedding_integrity.py  # Stored vector integrity check
│       ├── diagnose_regression.py         # DB audit and vector dimension verification
│       ├── run_ingestion.py               # Ingestion runner script
│       └── truncate_documents.py          # Reset helper script
├── .github/workflows/ # GitHub Actions CI/CD pipelines
└── requirements.txt   # Python package dependencies
```

## Retrieval Benchmarking & Verification

To verify database integrity and test retrieval accuracy, run the scripts in `tests/RETRIEVAL TESTS/`:

```bash
# Verify vector integrity (compares stored vs fresh Bedrock embeddings)
.venv\Scripts\python.exe "tests/RETRIEVAL TESTS/verify_embedding_integrity.py"

# Run retrieval accuracy benchmark (18 golden-set queries)
.venv\Scripts\python.exe "tests/RETRIEVAL TESTS/measure_thresholds.py"

# Audit document count and embedding metadata
.venv\Scripts\python.exe "tests/RETRIEVAL TESTS/diagnose_regression.py"
```

### Measured Performance
- **Retrieval Hit Rate:** 17 out of 18 queries (94.4%)
- **Embedding Match Score:** 1.000000 cosine similarity between stored and fresh vectors
- **Invalid Vectors:** 0 zero vectors or NaN/Inf values out of 820 stored chunks

## Setup & Installation

### 1. Prerequisites
* Python 3.11+
* Node.js (for frontend applications)
* PostgreSQL with pgvector extension enabled
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
