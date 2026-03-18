import json
from pathlib import Path
import re

from app.config import get_settings
from app.models.schemas import BookSummary
from app.services.book_title import resolve_book_title, sanitize_pdf_metadata
from app.services.page_filter import is_indexable_page

import fitz


PAGE_RE = re.compile(r"#page=(\d+)")


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
            title = self._refresh_title(payload, parsed_path, book_id)
            index_path = self.settings.index_dir / f"{book_id}.indexed.json"
            index_payload = self._load_json(index_path) if index_path.exists() else {}
            progress = self._progress_stats(book_id, payload)
            draft_status = self._draft_status(progress)
            status = str(index_payload.get("status", draft_status or "uploaded"))

            books.append(
                BookSummary(
                    book_id=book_id,
                    title=title,
                    pages=len(payload.get("pages", [])),
                    indexable_pages=progress["total_docs"],
                    status=status,
                    uploaded_at=payload.get("uploaded_at"),
                    indexed_at=index_payload.get("indexed_at"),
                    raw_path=str(payload.get("raw_path", self.settings.raw_dir / f"{book_id}.pdf")),
                    parsed_path=str(parsed_path),
                    index_path=str(index_path) if index_path.exists() else None,
                    processed_docs=progress["processed_docs"],
                    failed_docs=progress["failed_docs"],
                    remaining_docs=progress["remaining_docs"],
                    progress_percent=progress["progress_percent"],
                    chunk_count=progress["chunk_count"],
                    latest_processed_page=progress["latest_processed_page"],
                )
            )
        return books

    def _refresh_title(self, payload: dict, parsed_path: Path, book_id: str) -> str:
        metadata = payload.get("pdf_metadata")
        if not isinstance(metadata, dict) or not metadata.get("title"):
            metadata = self._load_pdf_metadata(str(payload.get("raw_path", "")))
            if metadata and metadata != payload.get("pdf_metadata"):
                payload["pdf_metadata"] = metadata

        title = resolve_book_title(
            filename=str(payload.get("source_filename", "")),
            book_id=book_id,
            current_title=str(payload.get("title", "")),
            metadata_title=str((metadata or {}).get("title", "")),
            page_texts=[str(page.get("text", "")) for page in payload.get("pages", [])[:5]],
        )
        if title != str(payload.get("title", "")):
            payload["title"] = title
            self._save_json(parsed_path, payload)
        elif metadata and metadata != payload.get("pdf_metadata"):
            self._save_json(parsed_path, payload)
        return title

    def _load_json(self, path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _save_json(self, path: Path, payload: dict) -> None:
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return

    def _load_pdf_metadata(self, raw_path: str) -> dict[str, str]:
        path = Path(raw_path)
        if not path.exists():
            return {}
        try:
            with fitz.open(path) as document:
                return sanitize_pdf_metadata(document.metadata)
        except (RuntimeError, OSError, ValueError):
            return {}

    def _draft_status(self, progress: dict[str, int | float | None]) -> str | None:
        total_docs = int(progress["total_docs"])
        processed = int(progress["processed_docs"])
        failed = int(progress["failed_docs"])
        has_workdir = bool(progress["has_workdir"])
        if total_docs == 0:
            return None

        if processed == 0 and failed == 0 and int(progress["chunk_count"]) == 0:
            return "indexing" if has_workdir else "uploaded"

        if processed > 0 or failed > 0:
            return "draft"
        return "indexing"

    def _progress_stats(self, book_id: str, payload: dict) -> dict[str, int | float | None]:
        total_docs = sum(
            1
            for page in payload.get("pages", [])
            if is_indexable_page(str(page.get("text", "")).strip())
        )
        workdir = self.settings.lightrag_workdir / book_id
        doc_status_path = workdir / "kv_store_doc_status.json"
        chunk_store_path = workdir / "kv_store_text_chunks.json"

        processed_docs = 0
        failed_docs = 0
        latest_processed_page: int | None = None

        doc_status = self._load_json(doc_status_path) or {}
        for item in doc_status.values():
            status = str(item.get("status", "")).lower()
            file_path = str(item.get("file_path", ""))
            page = self._extract_page(file_path)
            if status == "processed":
                processed_docs += 1
                if page is not None:
                    latest_processed_page = max(latest_processed_page or page, page)
            elif status == "failed":
                failed_docs += 1

        chunk_count = 0
        chunk_store = self._load_json(chunk_store_path) or {}
        if isinstance(chunk_store, dict):
            chunk_count = len(chunk_store)

        completed_docs = processed_docs + failed_docs
        visible_total_docs = max(total_docs, completed_docs)
        remaining_docs = max(visible_total_docs - completed_docs, 0)
        progress_percent = round((completed_docs / visible_total_docs) * 100, 1) if visible_total_docs > 0 else 0.0

        return {
            "total_docs": visible_total_docs,
            "processed_docs": processed_docs,
            "failed_docs": failed_docs,
            "remaining_docs": remaining_docs,
            "progress_percent": progress_percent,
            "chunk_count": chunk_count,
            "latest_processed_page": latest_processed_page,
            "has_workdir": workdir.exists(),
        }

    def _extract_page(self, file_path: str) -> int | None:
        match = PAGE_RE.search(file_path)
        if not match:
            return None
        return int(match.group(1))
