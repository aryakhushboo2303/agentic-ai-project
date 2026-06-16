import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from app.application.services.document_processor import chunk_text
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.entities import Contract, DocumentChunk
from app.domain.enums import ContractStatus
from app.domain.ports import (
    ChunkRepository,
    ContractRepository,
    DocumentParser,
    VectorStore,
)

logger = get_logger(__name__)

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class UploadContractUseCase:
    def __init__(
        self,
        contract_repo: ContractRepository,
        chunk_repo: ChunkRepository,
        vector_store: VectorStore,
        parser: DocumentParser,
    ):
        self._contract_repo = contract_repo
        self._chunk_repo = chunk_repo
        self._vector_store = vector_store
        self._parser = parser

    async def execute(self, filename: str, mime_type: str, content: bytes) -> Contract:
        if mime_type not in ALLOWED_MIME:
            raise ValidationError("Only PDF and DOCX files are supported")

        contract_id = uuid.uuid4()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path = upload_dir / f"{contract_id}_{filename}"

        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(content)

        contract = Contract(
            id=contract_id,
            filename=filename,
            mime_type=mime_type,
            storage_path=str(storage_path),
            status=ContractStatus.UPLOADED,
            uploaded_at=datetime.now(timezone.utc),
            file_size=len(content),
        )
        contract = await self._contract_repo.create(contract)
        logger.info("contract_uploaded", contract_id=str(contract_id), filename=filename)

        full_text, pages = self._parser.parse(str(storage_path), mime_type)
        chunk_dicts = chunk_text(full_text, pages)

        chunks = [
            DocumentChunk(
                id=None,
                contract_id=contract_id,
                chunk_index=c["chunk_index"],
                text=c["text"],
                page_number=c.get("page_number"),
            )
            for c in chunk_dicts
        ]
        saved_chunks = await self._chunk_repo.create_many(chunks)
        await self._vector_store.add_chunks(contract_id, saved_chunks)
        await self._contract_repo.update_status(contract_id, ContractStatus.INDEXED)

        contract.status = ContractStatus.INDEXED
        logger.info("contract_indexed", contract_id=str(contract_id), chunks=len(saved_chunks))
        return contract


class GetContractUseCase:
    def __init__(self, contract_repo: ContractRepository):
        self._contract_repo = contract_repo

    async def execute(self, contract_id: uuid.UUID) -> Contract:
        contract = await self._contract_repo.get_by_id(contract_id)
        if not contract:
            raise NotFoundError(f"Contract {contract_id} not found")
        return contract


class ListContractsUseCase:
    def __init__(self, contract_repo: ContractRepository):
        self._contract_repo = contract_repo

    async def execute(self, skip: int = 0, limit: int = 50) -> list[Contract]:
        return await self._contract_repo.list_all(skip=skip, limit=limit)
