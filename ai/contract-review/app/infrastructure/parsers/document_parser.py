import pdfplumber
from docx import Document

from app.core.exceptions import ValidationError


class DocumentParserService:
    ALLOWED_MIME = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    }

    def parse(self, file_path: str, mime_type: str) -> tuple[str, list[dict]]:
        if mime_type not in self.ALLOWED_MIME:
            raise ValidationError(f"Unsupported file type: {mime_type}")

        fmt = self.ALLOWED_MIME[mime_type]
        if fmt == "pdf":
            return self._parse_pdf(file_path)
        return self._parse_docx(file_path)

    def _parse_pdf(self, file_path: str) -> tuple[str, list[dict]]:
        pages: list[dict] = []
        full_parts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append({"page": i, "text": text})
                full_parts.append(text)
        return "\n\n".join(full_parts), pages

    def _parse_docx(self, file_path: str) -> tuple[str, list[dict]]:
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        return full_text, [{"page": 1, "text": full_text}]
