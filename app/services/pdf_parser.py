import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz
from fastapi import UploadFile

from app.config import get_settings
from app.models.schemas import BookUploadResponse


class PDFParser:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def save_and_parse(self, file: UploadFile) -> BookUploadResponse:
        raw_bytes = await file.read()
        book_id = self._make_book_id(file.filename or "book.pdf")
        raw_path = self.settings.raw_dir / f"{book_id}.pdf"
        parsed_path = self.settings.parsed_dir / f"{book_id}.json"

        raw_path.write_bytes(raw_bytes)

        document = fitz.open(stream=raw_bytes, filetype="pdf")
        pages: list[dict[str, str | int]] = []
        for page_number, page in enumerate(document, start=1):
            text = self._normalize(page.get_text("text"))
            pages.append({"page": page_number, "text": text})
        document.close()

        payload = {
            "book_id": book_id,
            "title": Path(file.filename or book_id).stem,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "raw_path": str(raw_path),
            "parsed_path": str(parsed_path),
            "pages": pages,
        }
        parsed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return BookUploadResponse(
            book_id=book_id,
            title=payload["title"],
            pages=len(pages),
            raw_path=str(raw_path),
            parsed_path=str(parsed_path),
        )

    def _make_book_id(self, filename: str) -> str:
        stem = Path(filename).stem.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
        return f"{slug or 'book'}-{uuid.uuid4().hex[:8]}"

    def _normalize(self, text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
