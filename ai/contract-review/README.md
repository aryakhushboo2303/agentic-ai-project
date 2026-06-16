# Contract Review System

Agentic AI Contract Review System built with **FastAPI**, **LangGraph**, **PostgreSQL**, **ChromaDB**, and **Google Gemini** (free tier via Google AI Studio).

## Features

- Upload contracts (PDF/DOCX)
- Multi-agent analysis via LangGraph:
  - Clause extraction
  - Risk assessment
  - Compliance checking
  - Executive summarization
- RAG-based Q&A with source citations
- Clean architecture (domain / application / infrastructure layers)
- Structured JSON logging
- Minimal upload UI at `/`

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Agents | LangGraph |
| LLM | Google Gemini (`gemini-2.0-flash`) |
| Embeddings | Google Gemini (`text-embedding-004`) |
| Database | PostgreSQL + SQLAlchemy async |
| Vector Store | ChromaDB |
| Parsing | pdfplumber, python-docx |

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Google AI Studio API key ([get one free](https://aistudio.google.com/apikey))

## Setup

```bash
# Clone / enter project
cd contract-review

# Start Postgres and ChromaDB
docker compose up -d

# Configure environment
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_key_here

# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** for the upload page, or **http://localhost:8000/docs** for Swagger UI.

## API Usage

```bash
# Upload a contract
curl -X POST http://localhost:8000/api/v1/contracts \
  -F "file=@contract.pdf"

# Trigger analysis (async)
curl -X POST http://localhost:8000/api/v1/contracts/{id}/analyze

# Get analysis results
curl http://localhost:8000/api/v1/contracts/{id}/analysis

# Ask a question
curl -X POST http://localhost:8000/api/v1/contracts/{id}/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the termination clause?"}'
```

## Project Structure

```
app/
├── api/              # REST routes, schemas, dependency injection
├── application/      # Use cases and document processing
├── domain/           # Entities, enums, port interfaces
├── infrastructure/   # DB, Chroma, Gemini, LangGraph, parsers
├── core/             # Config, logging, exceptions
├── templates/        # Minimal upload UI
└── main.py           # FastAPI app entry point
tests/                # Unit tests
FLOW.md               # System flow documentation
```

## Testing

```bash
pytest tests/ -v
```

## Flow Documentation

See [FLOW.md](FLOW.md) for a detailed walkthrough of upload, analysis, and Q&A flows.

## Configuration

All settings are in `.env` (see `.env.example`). Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google AI Studio API key (required) |
| `GEMINI_CHAT_MODEL` | `gemini-2.0-flash` | Chat model for agents |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Embedding model for RAG |
| `CHUNK_SIZE` | `1000` | Text chunk size |
| `RAG_TOP_K` | `5` | Retrieved chunks for Q&A |

## License

MIT
