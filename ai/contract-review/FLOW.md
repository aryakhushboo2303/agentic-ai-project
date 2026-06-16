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
# Contract Review System — Flows & API Guide

This document explains the two main system flows and what each API endpoint does, step by step.

---

## Flow 1: Contract Upload & Analysis (LangGraph Pipeline)

This flow turns a raw contract file into structured analysis results (clauses, risks, compliance findings, and a summary).

### Step-by-step

1. **User uploads a contract**
   - User sends a PDF or DOCX file through the upload API or the web page.
   - The system validates the file type and rejects unsupported formats.

2. **File is saved**
   - The original file is stored on disk.
   - A new contract record is created in PostgreSQL with status `uploaded`.

3. **Document is parsed**
   - PDF files are read page by page.
   - DOCX files are read paragraph by paragraph.
   - Full text is extracted for later use.

4. **Text is chunked**
   - The contract text is split into smaller overlapping pieces (chunks).
   - Each chunk keeps metadata such as page number and chunk index.

5. **Chunks are indexed for RAG**
   - Chunk text is converted into vector embeddings using Gemini.
   - Embeddings are stored in ChromaDB, tagged with the contract ID.
   - Chunk metadata is also saved in PostgreSQL.
   - Contract status moves to `indexed`.

6. **User triggers analysis**
   - User calls the analyze API for that contract.
   - The API returns immediately with status `running` — analysis runs in the background.

7. **LangGraph pipeline runs (4 agents in fixed order)**

   **Agent 1 — Clause Extractor**
   - Reads the full contract text.
   - Sends it to Gemini with a prompt to identify key clauses.
   - Returns structured clause data (title, text, category, confidence, page).

   **Agent 2 — Risk Assessor**
   - Reads the extracted clauses and contract text.
   - Sends them to Gemini to identify legal/business risks.
   - Returns risk findings (severity, description, recommendation).

   **Agent 3 — Compliance Checker**
   - Reads the contract text.
   - Sends it to Gemini to check against common compliance areas (data privacy, liability, IP, governing law, etc.).
   - Returns compliance findings (regulation, pass/fail/partial, details).

   **Agent 4 — Summarizer**
   - Reads clause count, risk count, and contract text.
   - Sends them to Gemini to produce an executive summary.
   - Returns summary with key terms (parties, term, payment, termination, governing law).

8. **Results are saved**
   - All outputs are stored in PostgreSQL (clauses, risks, compliance, summary tables).
   - Contract status moves to `ready` (or `failed` if something went wrong).

9. **User fetches results**
   - User polls the analysis API to get the full structured output.

### Status progression

```
uploaded → indexed → analyzing → ready (or failed)
```

---

## Flow 2: RAG Q&A (Question & Answer)

This flow lets users ask natural-language questions about a specific uploaded contract. It does **not** use the LangGraph pipeline — it uses Retrieval-Augmented Generation (RAG).

### Step-by-step

1. **User asks a question**
   - User sends a question about a specific contract (e.g. "What is the termination notice period?").

2. **Contract is verified**
   - System checks that the contract exists in the database.

3. **Question is embedded**
   - The question text is converted into a vector embedding using Gemini.

4. **Relevant chunks are retrieved**
   - ChromaDB is searched for the top matching chunks.
   - Search is filtered by contract ID so answers never mix content from different contracts.
   - Default: top 5 most similar chunks are returned.

5. **Context is built**
   - Retrieved chunks are formatted with page numbers and source labels.
   - They are combined into a context block for the LLM.

6. **LLM generates an answer**
   - Context + question are sent to Gemini.
   - The model is instructed to answer only from the provided context and cite page numbers.
   - If the answer is not in the context, the model says it could not find the information.

7. **Response is returned and saved**
   - User receives the answer along with source references (chunk text, page, relevance score).
   - The Q&A exchange is saved in PostgreSQL for history/audit.

---

## API Endpoints — Step by Step

### `GET /`

**Purpose:** Serves the minimal web UI.

**What it does:**
1. Returns an HTML upload page.
2. Page lets user upload a file, trigger analysis, and ask questions.
3. No backend processing — just renders the template.

---

### `GET /health`

**Purpose:** Health check for monitoring and debugging.

**What it does:**
1. Returns a simple JSON response confirming the service is running.
2. Includes the active LLM provider name (e.g. `gemini`) and chat model name.
3. Does not check database or ChromaDB connectivity — only confirms the API process is alive.

---

### `POST /api/v1/contracts`

**Purpose:** Upload a new contract and prepare it for analysis and Q&A.

**What it does:**
1. Accepts a file upload (PDF or DOCX) via multipart form data.
2. Validates the file MIME type — rejects unsupported types with a 400 error.
3. Generates a unique contract ID.
4. Saves the raw file to the uploads directory.
5. Creates a contract record in PostgreSQL (filename, mime type, file size, status `uploaded`).
6. Parses the document to extract full text and page structure.
7. Splits text into overlapping chunks.
8. Saves chunk metadata to PostgreSQL.
9. Embeds each chunk and stores vectors in ChromaDB.
10. Updates contract status to `indexed`.
11. Returns contract metadata: ID, filename, mime type, status, file size, upload timestamp.

**Response status:** `201 Created`

---

### `GET /api/v1/contracts`

**Purpose:** List all uploaded contracts.

**What it does:**
1. Accepts optional pagination parameters (`skip`, `limit`).
2. Queries PostgreSQL for contract records, ordered by most recent first.
3. Returns a list of contracts with ID, filename, mime type, status, file size, and upload date.
4. Also returns total count of contracts in the current page.

**Response status:** `200 OK`

---

### `GET /api/v1/contracts/{id}`

**Purpose:** Get metadata for a single contract.

**What it does:**
1. Accepts a contract UUID in the URL path.
2. Looks up the contract in PostgreSQL.
3. Returns 404 if the contract does not exist.
4. Returns contract details: ID, filename, mime type, current status, file size, upload timestamp.

**Response status:** `200 OK` or `404 Not Found`

---

### `POST /api/v1/contracts/{id}/analyze`

**Purpose:** Start multi-agent contract analysis in the background.

**What it does:**
1. Accepts a contract UUID in the URL path.
2. Accepts optional `force` query parameter to re-run analysis even if already completed.
3. Schedules the analysis as a background task — does not wait for completion.
4. Immediately returns `202 Accepted` with status `running`.
5. In the background:
   - Verifies the contract exists.
   - Skips if already analyzed (unless `force=true`).
   - Creates an analysis run record with status `running`.
   - Updates contract status to `analyzing`.
   - Re-parses the document to get full text.
   - Loads chunks from the database.
   - Runs the LangGraph pipeline (clause → risk → compliance → summary).
   - Saves all results to PostgreSQL.
   - Updates contract status to `ready` or `failed`.

**Response status:** `202 Accepted` (analysis runs asynchronously)

**Note:** Use `GET /api/v1/contracts/{id}/analysis` to check progress and fetch results.

---

### `GET /api/v1/contracts/{id}/analysis`

**Purpose:** Fetch analysis results and run status for a contract.

**What it does:**
1. Accepts a contract UUID in the URL path.
2. Looks up the contract — returns 404 if not found.
3. Fetches the latest analysis run record (status, start time, end time, error if any).
4. Fetches all saved clauses for this contract.
5. Fetches all saved risk findings.
6. Fetches all saved compliance findings.
7. Fetches the executive summary and key terms.
8. Returns everything in a single JSON response along with the contract's current status.

**Response status:** `200 OK` or `404 Not Found`

**Typical use:** Poll this endpoint after calling `/analyze` until status becomes `ready`.

---

### `POST /api/v1/contracts/{id}/qa`

**Purpose:** Ask a natural-language question about a specific contract using RAG.

**What it does:**
1. Accepts a contract UUID in the URL path.
2. Accepts a JSON body with a `question` field (3–2000 characters).
3. Verifies the contract exists — returns 404 if not.
4. Embeds the question using Gemini.
5. Searches ChromaDB for the top 5 most relevant chunks (filtered by contract ID).
6. If no chunks are found, returns a message saying no indexed content is available.
7. Builds a context prompt from retrieved chunks with page references.
8. Sends context + question to Gemini for answer generation.
9. Saves the Q&A exchange to PostgreSQL.
10. Returns the question, answer, and source references (chunk text, page number, relevance score).

**Response status:** `200 OK` or `404 Not Found`

---

## How the Two Flows Relate

| | Analysis Flow | Q&A Flow |
|---|---|---|
| **Trigger** | `POST .../analyze` | `POST .../qa` |
| **Uses LangGraph** | Yes (4 agents) | No |
| **Uses ChromaDB** | No (uses full text) | Yes (retrieves chunks) |
| **Uses Gemini** | Yes (4 separate calls) | Yes (embed + chat) |
| **Output** | Structured clauses, risks, compliance, summary | Natural-language answer with sources |
| **Runs in background** | Yes | No (synchronous) |
| **Requires upload first** | Yes | Yes |

Both flows depend on the upload step (`POST /api/v1/contracts`) which parses, chunks, and indexes the document.

---

## Typical User Journey

1. **Upload** → `POST /api/v1/contracts` → get contract ID, status `indexed`
2. **Analyze** → `POST /api/v1/contracts/{id}/analyze` → get `202 running`
3. **Poll** → `GET /api/v1/contracts/{id}/analysis` → wait until status is `ready`
4. **Review** → read clauses, risks, compliance, summary from the analysis response
5. **Ask questions** → `POST /api/v1/contracts/{id}/qa` → get answers with source citations

