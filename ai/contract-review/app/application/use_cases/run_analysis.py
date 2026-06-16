import uuid
from datetime import datetime, timezone

from app.core.exceptions import AnalysisError, NotFoundError
from app.core.logging import get_logger
from app.domain.entities import (
    AnalysisRun,
    Clause,
    ComplianceFinding,
    RiskFinding,
    Summary,
)
from app.domain.enums import AnalysisStatus, ContractStatus
from app.domain.ports import (
    AnalysisGraph,
    AnalysisRepository,
    ChunkRepository,
    ContractRepository,
    DocumentParser,
)

logger = get_logger(__name__)


class RunAnalysisUseCase:
    def __init__(
        self,
        contract_repo: ContractRepository,
        chunk_repo: ChunkRepository,
        analysis_repo: AnalysisRepository,
        analysis_graph: AnalysisGraph,
        parser: DocumentParser,
    ):
        self._contract_repo = contract_repo
        self._chunk_repo = chunk_repo
        self._analysis_repo = analysis_repo
        self._analysis_graph = analysis_graph
        self._parser = parser

    async def execute(self, contract_id: uuid.UUID, force: bool = False) -> AnalysisRun:
        contract = await self._contract_repo.get_by_id(contract_id)
        if not contract:
            raise NotFoundError(f"Contract {contract_id} not found")

        if contract.status == ContractStatus.READY and not force:
            existing = await self._analysis_repo.get_latest_run(contract_id)
            if existing:
                return existing

        run = AnalysisRun(
            id=None,
            contract_id=contract_id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        run = await self._analysis_repo.create_run(run)
        await self._contract_repo.update_status(contract_id, ContractStatus.ANALYZING)

        try:
            full_text, _ = self._parser.parse(contract.storage_path, contract.mime_type)
            chunks = await self._chunk_repo.get_by_contract(contract_id)
            chunk_dicts = [
                {"chunk_index": c.chunk_index, "text": c.text, "page_number": c.page_number}
                for c in chunks
            ]

            result = await self._analysis_graph.run(contract_id, full_text, chunk_dicts)

            clauses = [
                Clause(
                    id=None,
                    contract_id=contract_id,
                    title=c.get("title", "Untitled"),
                    text=c.get("text", ""),
                    category=c.get("category", "general"),
                    confidence=float(c.get("confidence", 0.0)),
                    page_number=c.get("page_number"),
                )
                for c in result.get("clauses", [])
            ]
            risks = [
                RiskFinding(
                    id=None,
                    contract_id=contract_id,
                    clause_ref=r.get("clause_ref", ""),
                    severity=r.get("severity", "medium"),
                    description=r.get("description", ""),
                    recommendation=r.get("recommendation", ""),
                )
                for r in result.get("risks", [])
            ]
            compliance = [
                ComplianceFinding(
                    id=None,
                    contract_id=contract_id,
                    regulation=f.get("regulation", ""),
                    status=f.get("status", "partial"),
                    details=f.get("details", ""),
                )
                for f in result.get("compliance", [])
            ]
            summary_data = result.get("summary", {})
            summary = Summary(
                id=None,
                contract_id=contract_id,
                executive_summary=summary_data.get("executive_summary", ""),
                key_terms=summary_data.get("key_terms", {}),
            )

            await self._analysis_repo.save_clauses(clauses)
            await self._analysis_repo.save_risks(risks)
            await self._analysis_repo.save_compliance(compliance)
            await self._analysis_repo.save_summary(summary)

            run.status = AnalysisStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            await self._analysis_repo.update_run(run)
            await self._contract_repo.update_status(contract_id, ContractStatus.READY)
            logger.info("analysis_completed", contract_id=str(contract_id))
            return run

        except Exception as e:
            run.status = AnalysisStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await self._analysis_repo.update_run(run)
            await self._contract_repo.update_status(contract_id, ContractStatus.FAILED)
            logger.error("analysis_failed", contract_id=str(contract_id), error=str(e))
            raise AnalysisError(f"Analysis failed: {e}") from e


class GetAnalysisUseCase:
    def __init__(self, contract_repo: ContractRepository, analysis_repo: AnalysisRepository):
        self._contract_repo = contract_repo
        self._analysis_repo = analysis_repo

    async def execute(self, contract_id: uuid.UUID) -> dict:
        contract = await self._contract_repo.get_by_id(contract_id)
        if not contract:
            raise NotFoundError(f"Contract {contract_id} not found")

        run = await self._analysis_repo.get_latest_run(contract_id)
        return {
            "contract_id": str(contract_id),
            "status": contract.status,
            "analysis_run": {
                "id": str(run.id) if run else None,
                "status": run.status if run else None,
                "started_at": run.started_at.isoformat() if run and run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run and run.completed_at else None,
                "error": run.error if run else None,
            },
            "clauses": [
                {
                    "title": c.title,
                    "text": c.text,
                    "category": c.category,
                    "confidence": c.confidence,
                    "page_number": c.page_number,
                }
                for c in await self._analysis_repo.get_clauses(contract_id)
            ],
            "risks": [
                {
                    "clause_ref": r.clause_ref,
                    "severity": r.severity,
                    "description": r.description,
                    "recommendation": r.recommendation,
                }
                for r in await self._analysis_repo.get_risks(contract_id)
            ],
            "compliance": [
                {
                    "regulation": f.regulation,
                    "status": f.status,
                    "details": f.details,
                }
                for f in await self._analysis_repo.get_compliance(contract_id)
            ],
            "summary": await self._get_summary_dict(contract_id),
        }

    async def _get_summary_dict(self, contract_id: uuid.UUID) -> dict | None:
        summary = await self._analysis_repo.get_summary(contract_id)
        if not summary:
            return None
        return {
            "executive_summary": summary.executive_summary,
            "key_terms": summary.key_terms,
        }
