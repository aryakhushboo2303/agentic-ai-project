from app.core.config import settings


def chunk_text(text: str, pages: list[dict] | None = None) -> list[dict]:
    """Split text into overlapping chunks with optional page metadata."""
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap
    chunks: list[dict] = []

    if pages:
        global_index = 0
        for page_info in pages:
            page_text = page_info.get("text", "")
            page_num = page_info.get("page", 1)
            start = 0
            while start < len(page_text):
                end = start + chunk_size
                chunk = page_text[start:end]
                if chunk.strip():
                    chunks.append(
                        {"text": chunk.strip(), "page_number": page_num, "chunk_index": global_index}
                    )
                    global_index += 1
                start = end - overlap
        return chunks

    start = 0
    index = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({"text": chunk.strip(), "page_number": None, "chunk_index": index})
            index += 1
        start = end - overlap
    return chunks
