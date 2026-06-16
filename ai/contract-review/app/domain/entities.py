from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Contract:
    id: UUID
    filename: str
    mime_type: str
    storage_path: str
    status: str
    uploaded_at: datetime
    file_size: int = 0


@dataclass
class DocumentChunk:
    id: UUID | None
    contract_id: UUID
    chunk_index: int
    text: str
    page_number: int | None = None
    embedding_id: str | None = None


@dataclass
class Clause:
    id: UUID | None
    contract_id: UUID
    title: str
    text: str
    category: str
    confidence: float = 0.0
    page_number: int | None = None


@dataclass
class RiskFinding:
    id: UUID | None
    contract_id: UUID
    clause_ref: str
    severity: str
    description: str
    recommendation: str = ""


@dataclass
class ComplianceFinding:
    id: UUID | None
    contract_id: UUID
    regulation: str
    status: str
    details: str = ""


@dataclass
class Summary:
    id: UUID | None
    contract_id: UUID
    executive_summary: str
    key_terms: dict = field(default_factory=dict)


@dataclass
class AnalysisRun:
    id: UUID | None
    contract_id: UUID
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class QAResult:
    question: str
    answer: str
    sources: list[dict] = field(default_factory=list)
