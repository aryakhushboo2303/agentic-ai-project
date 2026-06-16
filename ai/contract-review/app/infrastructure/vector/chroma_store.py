import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.entities import DocumentChunk
from app.domain.ports import LLMClient
from uuid import UUID

logger = get_logger(__name__)


class ChromaVectorStore:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    async def add_chunks(self, contract_id: UUID, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        texts = [c.text for c in chunks]
        embeddings = await self._llm.embed(texts)
        ids = [f"{contract_id}_{c.chunk_index}" for c in chunks]
        metadatas = [
            {
                "contract_id": str(contract_id),
                "chunk_index": c.chunk_index,
                "page_number": c.page_number or 0,
            }
            for c in chunks
        ]
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("chunks_indexed", contract_id=str(contract_id), count=len(chunks))

    async def search(self, contract_id: UUID, query: str, top_k: int) -> list[dict]:
        query_embedding = (await self._llm.embed([query]))[0]
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"contract_id": str(contract_id)},
        )
        sources = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0.0
                sources.append(
                    {
                        "text": doc,
                        "chunk_index": meta.get("chunk_index"),
                        "page_number": meta.get("page_number"),
                        "score": 1 - distance,
                    }
                )
        return sources

    async def delete_by_contract(self, contract_id: UUID) -> None:
        try:
            self._collection.delete(where={"contract_id": str(contract_id)})
        except Exception:
            logger.warning("chroma_delete_skipped", contract_id=str(contract_id))
