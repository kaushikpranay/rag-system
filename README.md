# RAG System for Customer Care

This project implements a Retrieval-Augmented Generation (RAG) system tailored for customer care applications.

## Project Structure

- `app/`: Core application logic.
  - `agent/`: LangChain/LangGraph agents.
  - `api/`: FastAPI backend.
  - `ingestion/`: Document processing and embedding pipeline.
  - `retrieval/`: Vector database interactions (ChromaDB).
  - `memory/`: Conversation history storage (DynamoDB).
  - `escalation/`: Human-in-the-loop escalation (SQS).
  - `dashboard/`: Streamlit monitoring dashboard.
  - `summarizer/`: Context summarization logic.
- `tests/`: Unit and integration tests.
- `.github/workflows/`: CI/CD pipelines.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment variables in `.env`.
3. Run the API:
   ```bash
   uvicorn app.api.main:app --reload
   ```
