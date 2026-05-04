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
*   **Backend:** FastAPI
*   **Frontend Chat:** Vanilla HTML/JS (served via FastAPI)
*   **Agent Dashboard:** Streamlit

## 📂 Directory Structure

```text
rag-system/
├── app/
│   ├── agent/         # LangGraph state machine and node definitions
│   ├── api/           # FastAPI backend routes and endpoints
│   ├── dashboard/     # Streamlit human agent UI and Chat HTML
│   ├── escalation/    # SQS queue producer/consumer logic
│   ├── ingestion/     # PDF parsing and embedding pipeline
│   ├── memory/        # DynamoDB session state management
│   ├── retrieval/     # pgvector queries and semantic similarity
│   └── utils/         # Config loaders and environment helpers
├── tests/             # Pytest test suites
├── .github/workflows/ # CI/CD deployment to AWS EC2
└── requirements.txt   # Python dependencies
```

## 🛠️ Setup & Installation

### 1. Prerequisites
*   Python 3.11+
*   PostgreSQL with the `pgvector` extension installed
*   AWS Account (for Bedrock, DynamoDB, SQS)
*   Groq API Key

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in the required credentials:
```bash
cp .env.example .env
```
Ensure you provide your `GROQ_API_KEY`, AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), and `RDS_*` connection details.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Setup
The application uses PostgreSQL with `pgvector`. The `pgvector_client.py` will automatically attempt to create the `vector` extension and the necessary `documents` table upon its first connection.

## 🚀 Running the System

### Start the FastAPI Backend (User Chat)
Serves the API and the end-user chat interface.
```bash
uvicorn app.api.main:app --reload
```
*The chat interface will be available at `http://localhost:8000/`*

### Start the Streamlit Dashboard (Human Agent UI)
Used by support agents to view escalated queries and provide verified answers.
```bash
streamlit run app/dashboard/streamlit_app.py
```
*The dashboard will be available at `http://localhost:8501/`*

## 🔄 Deployment

This project uses a GitHub Actions workflow (`deploy.yml`) to automatically test and deploy the `main` branch to an AWS EC2 instance. The pipeline runs `pytest` and, on success, pulls the latest code and restarts the FastAPI and Streamlit supervisor services via SSH.
