from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    AnalysisRun,
    Clause,
    ComplianceFinding,
    Contract,
    DocumentChunk,
    RiskFinding,
    Summary,
)
from app.infrastructure.db.models import (
    AnalysisRunModel,
    ClauseModel,
    ComplianceFindingModel,
    ContractModel,
    DocumentChunkModel,
    QAConversationModel,
    RiskFindingModel,
    SummaryModel,
)


def _to_contract(m: ContractModel) -> Contract:
    return Contract(
        id=m.id,
        filename=m.filename,
        mime_type=m.mime_type,
        storage_path=m.storage_path,
        status=m.status,
        uploaded_at=m.uploaded_at,
        file_size=m.file_size,
    )


class SQLContractRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, contract: Contract) -> Contract:
        model = ContractModel(
            id=contract.id,
            filename=contract.filename,
            mime_type=contract.mime_type,
            storage_path=contract.storage_path,
            status=contract.status,
            file_size=contract.file_size,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_contract(model)

    async def get_by_id(self, contract_id: UUID) -> Contract | None:
        result = await self._session.execute(select(ContractModel).where(ContractModel.id == contract_id))
        model = result.scalar_one_or_none()
        return _to_contract(model) if model else None

    async def list_all(self, skip: int = 0, limit: int = 50) -> list[Contract]:
        result = await self._session.execute(
            select(ContractModel).order_by(ContractModel.uploaded_at.desc()).offset(skip).limit(limit)
        )
        return [_to_contract(m) for m in result.scalars().all()]

    async def update_status(self, contract_id: UUID, status: str) -> None:
        result = await self._session.execute(select(ContractModel).where(ContractModel.id == contract_id))
        model = result.scalar_one()
        model.status = status
        await self._session.commit()


class SQLChunkRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        models = [
            DocumentChunkModel(
                contract_id=c.contract_id,
                chunk_index=c.chunk_index,
                text=c.text,
                page_number=c.page_number,
                embedding_id=c.embedding_id,
            )
            for c in chunks
        ]
        self._session.add_all(models)
        await self._session.commit()
        for m in models:
            await self._session.refresh(m)
        return [
            DocumentChunk(
                id=m.id,
                contract_id=m.contract_id,
                chunk_index=m.chunk_index,
                text=m.text,
                page_number=m.page_number,
                embedding_id=m.embedding_id,
            )
            for m in models
        ]

    async def get_by_contract(self, contract_id: UUID) -> list[DocumentChunk]:
        result = await self._session.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.contract_id == contract_id)
            .order_by(DocumentChunkModel.chunk_index)
        )
        return [
            DocumentChunk(
                id=m.id,
                contract_id=m.contract_id,
                chunk_index=m.chunk_index,
                text=m.text,
                page_number=m.page_number,
                embedding_id=m.embedding_id,
            )
            for m in result.scalars().all()
        ]


class SQLAnalysisRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_run(self, run: AnalysisRun) -> AnalysisRun:
        model = AnalysisRunModel(
            contract_id=run.contract_id,
            status=run.status,
            started_at=run.started_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return AnalysisRun(
            id=model.id,
            contract_id=model.contract_id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
        )

    async def update_run(self, run: AnalysisRun) -> AnalysisRun:
        result = await self._session.execute(
            select(AnalysisRunModel).where(AnalysisRunModel.id == run.id)
        )
        model = result.scalar_one()
        model.status = run.status
        model.completed_at = run.completed_at
        model.error = run.error
        await self._session.commit()
        await self._session.refresh(model)
        return AnalysisRun(
            id=model.id,
            contract_id=model.contract_id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
        )

    async def get_latest_run(self, contract_id: UUID) -> AnalysisRun | None:
        result = await self._session.execute(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.contract_id == contract_id)
            .order_by(AnalysisRunModel.started_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return AnalysisRun(
            id=model.id,
            contract_id=model.contract_id,
            status=model.status,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
        )

    async def save_clauses(self, clauses: list[Clause]) -> None:
        self._session.add_all(
            [
                ClauseModel(
                    contract_id=c.contract_id,
                    title=c.title,
                    text=c.text,
                    category=c.category,
                    confidence=c.confidence,
                    page_number=c.page_number,
                )
                for c in clauses
            ]
        )
        await self._session.commit()

    async def save_risks(self, risks: list[RiskFinding]) -> None:
        self._session.add_all(
            [
                RiskFindingModel(
                    contract_id=r.contract_id,
                    clause_ref=r.clause_ref,
                    severity=r.severity,
                    description=r.description,
                    recommendation=r.recommendation,
                )
                for r in risks
            ]
        )
        await self._session.commit()

    async def save_compliance(self, findings: list[ComplianceFinding]) -> None:
        self._session.add_all(
            [
                ComplianceFindingModel(
                    contract_id=f.contract_id,
                    regulation=f.regulation,
                    status=f.status,
                    details=f.details,
                )
                for f in findings
            ]
        )
        await self._session.commit()

    async def save_summary(self, summary: Summary) -> None:
        self._session.add(
            SummaryModel(
                contract_id=summary.contract_id,
                executive_summary=summary.executive_summary,
                key_terms=summary.key_terms,
            )
        )
        await self._session.commit()

    async def get_clauses(self, contract_id: UUID) -> list[Clause]:
        result = await self._session.execute(
            select(ClauseModel).where(ClauseModel.contract_id == contract_id)
        )
        return [
            Clause(
                id=m.id,
                contract_id=m.contract_id,
                title=m.title,
                text=m.text,
                category=m.category,
                confidence=m.confidence,
                page_number=m.page_number,
            )
            for m in result.scalars().all()
        ]

    async def get_risks(self, contract_id: UUID) -> list[RiskFinding]:
        result = await self._session.execute(
            select(RiskFindingModel).where(RiskFindingModel.contract_id == contract_id)
        )
        return [
            RiskFinding(
                id=m.id,
                contract_id=m.contract_id,
                clause_ref=m.clause_ref,
                severity=m.severity,
                description=m.description,
                recommendation=m.recommendation,
            )
            for m in result.scalars().all()
        ]

    async def get_compliance(self, contract_id: UUID) -> list[ComplianceFinding]:
        result = await self._session.execute(
            select(ComplianceFindingModel).where(ComplianceFindingModel.contract_id == contract_id)
        )
        return [
            ComplianceFinding(
                id=m.id,
                contract_id=m.contract_id,
                regulation=m.regulation,
                status=m.status,
                details=m.details,
            )
            for m in result.scalars().all()
        ]

    async def get_summary(self, contract_id: UUID) -> Summary | None:
        result = await self._session.execute(
            select(SummaryModel).where(SummaryModel.contract_id == contract_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Summary(
            id=model.id,
            contract_id=model.contract_id,
            executive_summary=model.executive_summary,
            key_terms=model.key_terms or {},
        )

    async def save_qa(self, contract_id: UUID, question: str, answer: str, sources: list) -> None:
        self._session.add(
            QAConversationModel(
                contract_id=contract_id,
                question=question,
                answer=answer,
                sources=sources,
            )
        )
        await self._session.commit()
