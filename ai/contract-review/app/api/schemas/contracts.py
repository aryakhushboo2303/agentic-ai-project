from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContractResponse(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    status: str
    file_size: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    contracts: list[ContractResponse]
    total: int


class AnalysisRunResponse(BaseModel):
    id: UUID | None
    status: str
    message: str = "Analysis started"


class QARequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]


class ErrorResponse(BaseModel):
    error: dict
