-- ==============================================================================
-- Production Database Schema Initialization for RAG System (pgvector)
-- ------------------------------------------------------------------------------
-- NOTE: This SQL script must be run ONCE against a fresh Amazon RDS (or PostgreSQL)
-- instance before using the application for the first time.
-- ==============================================================================

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Table definition for storing chunks, metadata, and embeddings (1024-dim for Amazon Titan Text Embeddings v2)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Expression indexes on JSONB metadata fields for fast lookup & filtering
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash ON documents ((metadata->>'content_hash'));
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents ((metadata->>'source'));
CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents ((metadata->>'session_id'));

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_documents_embedding_hnsw ON documents USING hnsw (embedding vector_cosine_ops);
