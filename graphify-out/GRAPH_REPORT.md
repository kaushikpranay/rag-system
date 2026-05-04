# Graph Report - .  (2026-05-04)

## Corpus Check
- Corpus is ~5,051 words - fits in a single context window. You may not need a graph.

## Summary
- 82 nodes · 90 edges · 20 communities detected
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.8)
- Token cost: 500 input · 200 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Streamlit Dashboard & AWS Utilities|Streamlit Dashboard & AWS Utilities]]
- [[_COMMUNITY_LangGraph Agent Logic|LangGraph Agent Logic]]
- [[_COMMUNITY_FastAPI Backend & Security|FastAPI Backend & Security]]
- [[_COMMUNITY_Session Management & SQS Escalation|Session Management & SQS Escalation]]
- [[_COMMUNITY_Vector DB & pgvector Client|Vector DB & pgvector Client]]
- [[_COMMUNITY_Ingestion Pipeline|Ingestion Pipeline]]
- [[_COMMUNITY_Documentation & Setup|Documentation & Setup]]
- [[_COMMUNITY_Configuration Utils|Configuration Utils]]
- [[_COMMUNITY_Chat UI Frontend|Chat UI Frontend]]
- [[_COMMUNITY_Agent Package|Agent Package]]
- [[_COMMUNITY_API Package|API Package]]
- [[_COMMUNITY_Dashboard Package|Dashboard Package]]
- [[_COMMUNITY_Escalation Package|Escalation Package]]
- [[_COMMUNITY_Ingestion Package|Ingestion Package]]
- [[_COMMUNITY_Memory Package|Memory Package]]
- [[_COMMUNITY_Retrieval Package|Retrieval Package]]
- [[_COMMUNITY_Summarizer Logic|Summarizer Logic]]
- [[_COMMUNITY_Summarizer Package|Summarizer Package]]
- [[_COMMUNITY_Utils Package|Utils Package]]
- [[_COMMUNITY_Tests Package|Tests Package]]

## God Nodes (most connected - your core abstractions)
1. `get_aws_clients()` - 7 edges
2. `get_connection()` - 5 edges
3. `get_bedrock_embedding()` - 4 edges
4. `store_verified_answer_rds()` - 4 edges
5. `ingest()` - 4 edges
6. `get_bedrock_embedding()` - 4 edges
7. `store_chunks()` - 4 edges
8. `retrieve_similar()` - 4 edges
9. `search_human_verified()` - 4 edges
10. `AgentState` - 3 edges

## Surprising Connections (you probably didn't know these)
- `queue_status()` --calls--> `get_connection()`  [INFERRED]
  app\api\main.py → app\retrieval\pgvector_client.py
- `ingest()` --calls--> `store_chunks()`  [INFERRED]
  app\ingestion\pipeline.py → app\retrieval\pgvector_client.py
- `session_node()` --calls--> `get_session()`  [INFERRED]
  app\agent\graph.py → app\memory\dynamodb_client.py
- `retrieval_node()` --calls--> `search_human_verified()`  [INFERRED]
  app\agent\graph.py → app\retrieval\pgvector_client.py
- `retrieval_node()` --calls--> `retrieve_similar()`  [INFERRED]
  app\agent\graph.py → app\retrieval\pgvector_client.py

## Communities

### Community 0 - "Streamlit Dashboard & AWS Utilities"
Cohesion: 0.15
Nodes (17): delete_from_sqs(), get_aws_clients(), get_bedrock_embedding(), get_queue_depth(), get_rds_connection(), Phase 7 — Streamlit Human Agent Dashboard RAG Query Resolution System File: ap, Delete a resolved message from SQS., Return approximate number of messages in queue. (+9 more)

### Community 1 - "LangGraph Agent Logic"
Cohesion: 0.17
Nodes (6): AgentState, After evaluation: retry retrieval or proceed to output., route_after_evaluation(), run_agent(), resolve_query(), TypedDict

### Community 2 - "FastAPI Backend & Security"
Cohesion: 0.2
Nodes (7): BaseHTTPMiddleware, BaseModel, QueryRequest, QueryResponse, queue_status(), Check if a human-verified answer exists for a specific query.     1. First chec, SecurityHeadersMiddleware

### Community 3 - "Session Management & SQS Escalation"
Cohesion: 0.22
Nodes (6): get_session(), save_session(), output_node(), session_node(), manual_escalate(), send_to_sqs()

### Community 4 - "Vector DB & pgvector Client"
Cohesion: 0.62
Nodes (6): retrieval_node(), get_bedrock_embedding(), get_connection(), retrieve_similar(), search_human_verified(), store_chunks()

### Community 5 - "Ingestion Pipeline"
Cohesion: 0.83
Nodes (3): chunk_documents(), ingest(), load_document_from_s3()

### Community 6 - "Documentation & Setup"
Cohesion: 0.67
Nodes (3): RAG System for Customer Care, Setup Instructions, Project Dependencies

### Community 7 - "Configuration Utils"
Cohesion: 1.0
Nodes (0): 

### Community 8 - "Chat UI Frontend"
Cohesion: 1.0
Nodes (2): Chat Interface UI, Per-query Polling Logic

### Community 9 - "Agent Package"
Cohesion: 1.0
Nodes (0): 

### Community 10 - "API Package"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Dashboard Package"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Escalation Package"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Ingestion Package"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Memory Package"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Retrieval Package"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Summarizer Logic"
Cohesion: 1.0
Nodes (0): 

### Community 17 - "Summarizer Package"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "Utils Package"
Cohesion: 1.0
Nodes (0): 

### Community 19 - "Tests Package"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **14 isolated node(s):** `After evaluation: retry retrieval or proceed to output.`, `Check if a human-verified answer exists for a specific query.     1. First chec`, `Phase 7 — Streamlit Human Agent Dashboard RAG Query Resolution System File: ap`, `Delete a resolved message from SQS.`, `Return approximate number of messages in queue.` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Configuration Utils`** (2 nodes): `config.py`, `get_secret()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Chat UI Frontend`** (2 nodes): `Chat Interface UI`, `Per-query Polling Logic`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Agent Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Dashboard Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Escalation Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Ingestion Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Memory Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Retrieval Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Summarizer Logic`** (1 nodes): `summarize.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Summarizer Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Utils Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tests Package`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `retrieval_node()` connect `Vector DB & pgvector Client` to `LangGraph Agent Logic`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `get_connection()` connect `Vector DB & pgvector Client` to `FastAPI Backend & Security`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `queue_status()` connect `FastAPI Backend & Security` to `Vector DB & pgvector Client`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **What connects `After evaluation: retry retrieval or proceed to output.`, `Check if a human-verified answer exists for a specific query.     1. First chec`, `Phase 7 — Streamlit Human Agent Dashboard RAG Query Resolution System File: ap` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._