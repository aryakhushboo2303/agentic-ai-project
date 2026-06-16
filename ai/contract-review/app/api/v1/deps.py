from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.ask_question import AskQuestionUseCase
from app.application.use_cases.run_analysis import GetAnalysisUseCase, RunAnalysisUseCase
from app.application.use_cases.upload_contract import (
    GetContractUseCase,
    ListContractsUseCase,
    UploadContractUseCase,
)
from app.infrastructure.agents.graph import ContractAnalysisGraph
from app.infrastructure.db.repositories import (
    SQLAnalysisRepository,
    SQLChunkRepository,
    SQLContractRepository,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.llm.gemini_client import GeminiLLMClient
from app.infrastructure.parsers.document_parser import DocumentParserService
from app.infrastructure.vector.chroma_store import ChromaVectorStore


@lru_cache
def get_llm_client() -> GeminiLLMClient:
    return GeminiLLMClient()


@lru_cache
def get_parser() -> DocumentParserService:
    return DocumentParserService()


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(get_llm_client())


@lru_cache
def get_analysis_graph() -> ContractAnalysisGraph:
    return ContractAnalysisGraph(get_llm_client())


async def get_upload_use_case(
    session: AsyncSession = Depends(get_session),
) -> UploadContractUseCase:
    return UploadContractUseCase(
        SQLContractRepository(session),
        SQLChunkRepository(session),
        get_vector_store(),
        get_parser(),
    )


async def get_contract_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetContractUseCase:
    return GetContractUseCase(SQLContractRepository(session))


async def get_list_use_case(
    session: AsyncSession = Depends(get_session),
) -> ListContractsUseCase:
    return ListContractsUseCase(SQLContractRepository(session))


async def get_run_analysis_use_case(
    session: AsyncSession = Depends(get_session),
) -> RunAnalysisUseCase:
    return RunAnalysisUseCase(
        SQLContractRepository(session),
        SQLChunkRepository(session),
        SQLAnalysisRepository(session),
        get_analysis_graph(),
        get_parser(),
    )


async def get_analysis_use_case(
    session: AsyncSession = Depends(get_session),
) -> GetAnalysisUseCase:
    return GetAnalysisUseCase(SQLContractRepository(session), SQLAnalysisRepository(session))


async def get_qa_use_case(
    session: AsyncSession = Depends(get_session),
) -> AskQuestionUseCase:
    return AskQuestionUseCase(
        SQLContractRepository(session),
        SQLAnalysisRepository(session),
        get_vector_store(),
        get_llm_client(),
    )
