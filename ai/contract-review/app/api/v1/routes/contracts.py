from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.api.schemas.contracts import (
    AnalysisRunResponse,
    ContractListResponse,
    ContractResponse,
    QARequest,
    QAResponse,
)
from app.api.v1.deps import (
    get_analysis_use_case,
    get_contract_use_case,
    get_list_use_case,
    get_qa_use_case,
    get_run_analysis_use_case,
    get_upload_use_case,
)
from app.application.use_cases.ask_question import AskQuestionUseCase
from app.application.use_cases.run_analysis import GetAnalysisUseCase, RunAnalysisUseCase
from app.application.use_cases.upload_contract import (
    GetContractUseCase,
    ListContractsUseCase,
    UploadContractUseCase,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", response_model=ContractResponse, status_code=201)
async def upload_contract(
    file: UploadFile = File(...),
    use_case: UploadContractUseCase = Depends(get_upload_use_case),
):
    content = await file.read()
    mime = file.content_type or "application/octet-stream"
    contract = await use_case.execute(file.filename or "contract", mime, content)
    return ContractResponse(
        id=contract.id,
        filename=contract.filename,
        mime_type=contract.mime_type,
        status=contract.status,
        file_size=contract.file_size,
        uploaded_at=contract.uploaded_at,
    )


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    skip: int = 0,
    limit: int = 50,
    use_case: ListContractsUseCase = Depends(get_list_use_case),
):
    contracts = await use_case.execute(skip=skip, limit=limit)
    return ContractListResponse(
        contracts=[
            ContractResponse(
                id=c.id,
                filename=c.filename,
                mime_type=c.mime_type,
                status=c.status,
                file_size=c.file_size,
                uploaded_at=c.uploaded_at,
            )
            for c in contracts
        ],
        total=len(contracts),
    )


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: UUID,
    use_case: GetContractUseCase = Depends(get_contract_use_case),
):
    contract = await use_case.execute(contract_id)
    return ContractResponse(
        id=contract.id,
        filename=contract.filename,
        mime_type=contract.mime_type,
        status=contract.status,
        file_size=contract.file_size,
        uploaded_at=contract.uploaded_at,
    )


async def _run_analysis_background(use_case: RunAnalysisUseCase, contract_id: UUID, force: bool):
    try:
        await use_case.execute(contract_id, force=force)
    except Exception as e:
        logger.error("background_analysis_failed", contract_id=str(contract_id), error=str(e))


@router.post("/{contract_id}/analyze", response_model=AnalysisRunResponse, status_code=202)
async def analyze_contract(
    contract_id: UUID,
    background_tasks: BackgroundTasks,
    force: bool = False,
    use_case: RunAnalysisUseCase = Depends(get_run_analysis_use_case),
):
    background_tasks.add_task(_run_analysis_background, use_case, contract_id, force)
    return AnalysisRunResponse(id=None, status="running", message="Analysis started in background")


@router.get("/{contract_id}/analysis")
async def get_analysis(
    contract_id: UUID,
    use_case: GetAnalysisUseCase = Depends(get_analysis_use_case),
):
    return await use_case.execute(contract_id)


@router.post("/{contract_id}/qa", response_model=QAResponse)
async def ask_question(
    contract_id: UUID,
    body: QARequest,
    use_case: AskQuestionUseCase = Depends(get_qa_use_case),
):
    result = await use_case.execute(contract_id, body.question)
    return QAResponse(question=result.question, answer=result.answer, sources=result.sources)
