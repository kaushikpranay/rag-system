# RAG Query Resolution System

An intelligent, multi-agent Retrieval-Augmented Generation (RAG) system built for customer care and automated support. The system uses a LangGraph-powered state machine to intelligently retrieve documents, answer user queries, and seamlessly escalate complex issues to human agents when confidence is low.

## 🚀 Features

*   **Intelligent Retrieval Loop:** LangGraph agent automatically retries searches up to 3 times with progressively wider parameters (`top_k`, `min_sim`) if the initial answer is low-confidence.
*   **Human-in-the-loop Escalation:** Queries the LLM can't answer are automatically escalated to a human agent via Amazon SQS.
*   **Cross-User Knowledge Sharing:** Human-verified answers are embedded and stored in the vector database, instantly becoming available to *all* future users asking similar questions.
*   **Dynamic Chat Memory:** Session context is stored in DynamoDB, allowing natural follow-up questions without needing to explicitly reference previous context.
*   **Real-time Polling:** The chat interface actively polls for human-agent responses and updates the UI without requiring page reloads.
*   **Secure Infrastructure:** FastAPI backend with strict CSP headers, SQL injection protection, XSS sanitization, and automated deployments to AWS EC2 via GitHub Actions.

## 🏗️ Architecture

*   **State Machine:** [LangGraph](https://python.langchain.com/docs/langgraph)
*   **LLM Inference:** [Llama-3.1-8b-instant](https://groq.com/) (via Groq)
*   **Embeddings:** Amazon Bedrock (`amazon.titan-embed-text-v2:0`)
*   **Vector Database:** Amazon RDS (PostgreSQL with `pgvector`)
*   **Session Memory:** Amazon DynamoDB
*   **Message Queue:** Amazon SQS (Escalations)
*   **Archival:** Amazon S3
*   **Backend:** FastAPI
*   **Chat Frontend:** React + Vite (`frontend/chat`), hosted on Vercel
*   **Agent Dashboard:** React + Vite (`frontend/dashboard`), hosted on Vercel — backed by the FastAPI `dashboard` router (password-protected)

## 📂 Directory Structure

```text
rag-system/
├── app/
│   ├── agent/         # LangGraph state machine and node definitions
│   ├── api/           # FastAPI app, routes (main.py), dashboard router (dashboard.py)
│   ├── archive/        # S3 archival client
│   ├── escalation/    # SQS queue producer/consumer logic
│   ├── ingestion/     # PDF parsing and embedding pipeline
│   ├── memory/        # DynamoDB session state management
│   ├── retrieval/     # pgvector queries and semantic similarity
│   ├── summarizer/    # Query/escalation summarization helpers
│   └── utils/         # Config loaders and environment helpers
├── frontend/
│   ├── chat/          # React/Vite end-user chat UI (deployed to Vercel)
│   └── dashboard/     # React/Vite human-agent dashboard UI (deployed to Vercel)
├── tests/             # Pytest test suites
├── .github/workflows/ # ci.yml (tests), cd.yml (deploy backend to AWS EC2)
└── requirements.txt   # Python dependencies
```

## 🛠️ Setup & Installation

### 1. Prerequisites
*   Python 3.11+
*   Node.js (for the `frontend/chat` and `frontend/dashboard` apps)
*   PostgreSQL with the `pgvector` extension installed
*   AWS Account (for Bedrock, RDS, DynamoDB, SQS, S3)
*   Groq API Key

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in the required credentials:
```bash
cp .env.example .env
```
Ensure you provide your `GROQ_API_KEY`, AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), `RDS_*` connection details, and `FRONTEND_ORIGINS` (comma-separated list of allowed frontend origins for CORS).

Each frontend also has its own `.env.example` (`frontend/chat/.env.example`, `frontend/dashboard/.env.example`) — copy it to `.env` and set `VITE_API_BASE_URL` to your backend URL.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
cd frontend/chat && npm install
cd ../dashboard && npm install
```

### 4. Database Setup
The application uses PostgreSQL with `pgvector`. The `pgvector_client.py` will automatically attempt to create the `vector` extension and the necessary `documents` table upon its first connection.

## 🚀 Running the System

### Start the FastAPI Backend
```bash
uvicorn app.api.main:app --reload
```
*The API will be available at `http://localhost:8000/`*

### Start the Chat Frontend
```bash
cd frontend/chat
npm run dev
```

### Start the Agent Dashboard
```bash
cd frontend/dashboard
npm run dev
```
Both dev servers point at `VITE_API_BASE_URL` (default `http://localhost:8000`) from their respective `.env`.

## 🔄 Deployment

*   **Backend:** `.github/workflows/ci.yml` runs `pytest` on every push/PR. On success on `main`, `.github/workflows/cd.yml` SSHs into an AWS EC2 instance, `git pull`s, reinstalls dependencies, and restarts the FastAPI service via `supervisorctl`. Nginx reverse-proxies port 80/443 to uvicorn on port 8000.
*   **Frontends:** `frontend/chat` and `frontend/dashboard` are each deployed as separate Vercel projects, connected to this GitHub repo — pushing to `main` triggers an automatic Vercel rebuild/redeploy. Set `VITE_API_BASE_URL` in each Vercel project's environment variables to the backend's public HTTPS URL.
*   **CORS:** the backend's `FRONTEND_ORIGINS` env var must list the exact Vercel URLs (e.g. `https://your-chat.vercel.app,https://your-dashboard.vercel.app`) or the frontends will be blocked by CORS.
