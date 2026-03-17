import json
from pathlib import Path

from app.config import get_settings
from app.models.schemas import BookSummary


class BookCatalog:
    def __init__(self) -> None:
        self.settings = get_settings()

    def list_books(self) -> list[BookSummary]:
        books: list[BookSummary] = []
        for parsed_path in sorted(self.settings.parsed_dir.glob("*.json"), reverse=True):
            payload = self._load_json(parsed_path)
            if payload is None:
                continue

            book_id = str(payload.get("book_id", parsed_path.stem))
            index_path = self.settings.index_dir / f"{book_id}.indexed.json"
            index_payload = self._load_json(index_path) if index_path.exists() else {}
            draft_status = self._draft_status(book_id)
            status = str(index_payload.get("status", draft_status or "uploaded"))

            books.append(
                BookSummary(
                    book_id=book_id,
                    title=str(payload.get("title", book_id)),
                    pages=len(payload.get("pages", [])),
                    status=status,
                    uploaded_at=payload.get("uploaded_at"),
                    indexed_at=index_payload.get("indexed_at"),
                    raw_path=str(payload.get("raw_path", self.settings.raw_dir / f"{book_id}.pdf")),
                    parsed_path=str(parsed_path),
                    index_path=str(index_path) if index_path.exists() else None,
                )
            )
        return books

    def _load_json(self, path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _draft_status(self, book_id: str) -> str | None:
        workdir = self.settings.lightrag_workdir / book_id
        if not workdir.exists():
            return None

        doc_status_path = workdir / "kv_store_doc_status.json"
        if not doc_status_path.exists():
            return "indexing"

        payload = self._load_json(doc_status_path)
        if not payload:
            return "indexing"

        processed = 0
        failed = 0
        for item in payload.values():
            status = str(item.get("status", ""))
            if status == "processed":
                processed += 1
            elif status == "failed":
                failed += 1

        if processed > 0 or failed > 0:
            return "draft"
        return "indexing"
