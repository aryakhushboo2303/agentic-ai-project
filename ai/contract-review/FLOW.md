# Contract Review System — Flow Guide

This document explains how data moves through the system from upload to Q&A.

---

## System Overview

```
User → FastAPI → Use Cases → [PostgreSQL | ChromaDB | Gemini LLM]
                              ↑
                         LangGraph Agents
```

| Component | Role |
|-----------|------|
| **FastAPI** | REST API + minimal upload UI |
| **PostgreSQL** | Contract metadata, analysis results, Q&A history |
| **ChromaDB** | Vector embeddings for RAG retrieval |
| **Gemini** | Google LLM (chat + embeddings) via Google AI Studio |
| **LangGraph** | Multi-agent orchestration pipeline |

---

## Flow 1: Contract Upload & Indexing

```
┌──────┐    POST /api/v1/contracts     ┌─────────────┐
│ User │ ─────────────────────────────►│   FastAPI   │
└──────┘    (PDF or DOCX file)          └──────┬──────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
             Save file to              Parse document               Chunk text
             ./uploads/                  (pdfplumber /               (1000 chars,
                                        python-docx)                 150 overlap)
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                ▼
                                    ┌───────────────────────┐
                                    │  Embed via Gemini     │
                                    │  (text-embedding-004) │
                                    └───────────┬───────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼                                           ▼
                   PostgreSQL                                    ChromaDB
              (contract + chunks                          (vector embeddings
               metadata)                                   with contract_id filter)
```

**Status progression:** `uploaded` → `indexed`

---

## Flow 2: Multi-Agent Analysis (LangGraph)

Triggered by: `POST /api/v1/contracts/{id}/analyze` (runs in background)

```
START
  │
  ▼
┌─────────────────┐
│ Clause Extractor│  → Identifies key clauses (title, category, text)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Risk Assessor  │  → Flags risks (severity, description, recommendation)
└────────┬────────┘
         ▼
┌─────────────────┐
│   Compliance    │  → Checks data privacy, liability, IP, governing law
│    Checker      │
└────────┬────────┘
         ▼
┌─────────────────┐
│   Summarizer    │  → Executive summary + key terms
└────────┬────────┘
         ▼
        END
```

Each agent node:
1. Sends a focused system prompt + contract text to **Gemini (gemini-2.0-flash)**
2. Expects structured JSON output
3. Writes results to shared LangGraph state
4. Passes state to the next node

Results are persisted to PostgreSQL:
- `clauses`, `risk_findings`, `compliance_findings`, `summaries`

**Status progression:** `indexed` → `analyzing` → `ready` (or `failed`)

Fetch results: `GET /api/v1/contracts/{id}/analysis`

---

## Flow 3: RAG Q&A

Triggered by: `POST /api/v1/contracts/{id}/qa`

```
Question: "What is the termination notice period?"
                    │
                    ▼
         Embed question (Gemini)
                    │
                    ▼
    Search ChromaDB (filtered by contract_id, top-5 chunks)
                    │
                    ▼
    Build prompt: context chunks + question
                    │
                    ▼
         Gemini generates answer with citations
                    │
                    ▼
    Save to qa_conversations + return answer + sources
```

The contract_id metadata filter ensures answers never leak across documents.

---

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Upload page (minimal UI) |
| GET | `/health` | Health check |
| POST | `/api/v1/contracts` | Upload contract |
| GET | `/api/v1/contracts` | List contracts |
| GET | `/api/v1/contracts/{id}` | Get contract metadata |
| POST | `/api/v1/contracts/{id}/analyze` | Start analysis (async) |
| GET | `/api/v1/contracts/{id}/analysis` | Get full analysis results |
| POST | `/api/v1/contracts/{id}/qa` | Ask a question (RAG) |

---

## Architecture Layers

```
Presentation     app/api/          Routes, schemas, DI
Application      app/application/  Use cases (business logic)
Domain           app/domain/       Entities, ports (interfaces)
Infrastructure   app/infrastructure/  DB, Chroma, Gemini, LangGraph, parsers
```

Dependencies point inward: infrastructure implements domain ports; use cases depend on ports, not concrete classes.

---

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Set your Google API key
cp .env.example .env
# Edit .env: GOOGLE_API_KEY=your_key_here

# 3. Install & run
pip install -e ".[dev]"
uvicorn app.main:app --reload

# 4. Open http://localhost:8000
```

Get a free API key at: https://aistudio.google.com/apikey
