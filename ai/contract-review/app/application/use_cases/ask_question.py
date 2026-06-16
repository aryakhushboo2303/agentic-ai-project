import uuid

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.domain.entities import QAResult
from app.domain.ports import AnalysisRepository, ContractRepository, LLMClient, VectorStore

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = """You are a contract Q&A assistant. Answer questions based ONLY on the provided context.
If the answer is not in the context, say "I could not find this information in the contract."
Always cite the page number when available. Be concise and accurate."""


class AskQuestionUseCase:
    def __init__(
        self,
        contract_repo: ContractRepository,
        analysis_repo: AnalysisRepository,
        vector_store: VectorStore,
        llm_client: LLMClient,
    ):
        self._contract_repo = contract_repo
        self._analysis_repo = analysis_repo
        self._vector_store = vector_store
        self._llm = llm_client

    async def execute(self, contract_id: uuid.UUID, question: str) -> QAResult:
        contract = await self._contract_repo.get_by_id(contract_id)
        if not contract:
            raise NotFoundError(f"Contract {contract_id} not found")

        sources = await self._vector_store.search(
            contract_id, question, top_k=settings.rag_top_k
        )

        if not sources:
            return QAResult(
                question=question,
                answer="No indexed content found for this contract. Please ensure it was uploaded successfully.",
                sources=[],
            )

        context_parts = []
        for i, src in enumerate(sources, 1):
            page = src.get("page_number", "N/A")
            context_parts.append(f"[Source {i}, Page {page}]: {src['text']}")

        context = "\n\n".join(context_parts)
        user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

        answer = await self._llm.chat(RAG_SYSTEM_PROMPT, user_prompt)
        await self._analysis_repo.save_qa(contract_id, question, answer, sources)

        logger.info("qa_completed", contract_id=str(contract_id))
        return QAResult(question=question, answer=answer, sources=sources)
