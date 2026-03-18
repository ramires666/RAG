from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import BookIndexResponse, BookSummary, BookUploadResponse, GlobalGraphStatus, IndexJobStatus, RepairPlanResponse
from app.services.book_catalog import BookCatalog
from app.services.indexing_jobs import indexing_job_manager
from app.services.lightrag_service import LightRAGService
from app.services.pdf_parser import PDFParser


router = APIRouter(prefix="/books", tags=["books"])
pdf_parser = PDFParser()
lightrag_service = LightRAGService()
book_catalog = BookCatalog()


@router.get("", response_model=list[BookSummary])
async def list_books() -> list[BookSummary]:
    return book_catalog.list_books()


@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(file: UploadFile = File(...)) -> BookUploadResponse:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF files are supported in MVP.")

    suffix = Path(file.filename or "book.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Expected a .pdf file.")

    return await pdf_parser.save_and_parse(file)


@router.get("/graph/status", response_model=GlobalGraphStatus)
async def global_graph_status() -> GlobalGraphStatus:
    return lightrag_service.get_global_graph_status()


@router.post("/graph/rebuild", response_model=BookIndexResponse)
async def rebuild_global_graph() -> BookIndexResponse:
    if indexing_job_manager.is_running():
        raise HTTPException(status_code=409, detail="A book indexing job is running right now. Wait until it finishes.")
    return await lightrag_service.rebuild_global_graph()


@router.delete("/graph", response_model=BookIndexResponse)
async def delete_global_graph() -> BookIndexResponse:
    if indexing_job_manager.is_running():
        raise HTTPException(status_code=409, detail="A book indexing job is running right now. Wait until it finishes.")
    return await lightrag_service.delete_global_graph()


@router.post("/{book_id}/index", response_model=BookIndexResponse)
async def index_book(book_id: str) -> BookIndexResponse:
    return await lightrag_service.index_book(book_id)


@router.post("/{book_id}/reindex", response_model=BookIndexResponse)
async def reindex_book(book_id: str) -> BookIndexResponse:
    return await lightrag_service.reindex_book(book_id)


@router.post("/{book_id}/reindex/start", response_model=IndexJobStatus)
async def start_reindex_book(book_id: str) -> IndexJobStatus:
    return await indexing_job_manager.start_reindex(book_id)


@router.get("/{book_id}/repair/plan", response_model=RepairPlanResponse)
async def repair_plan(book_id: str) -> RepairPlanResponse:
    return lightrag_service.scan_repair_plan(book_id)


@router.post("/{book_id}/repair", response_model=BookIndexResponse)
async def repair_book(book_id: str) -> BookIndexResponse:
    return await lightrag_service.repair_index(book_id)


@router.post("/{book_id}/repair/start", response_model=IndexJobStatus)
async def start_repair_book(book_id: str) -> IndexJobStatus:
    return await indexing_job_manager.start_repair(book_id)


@router.get("/{book_id}/index/status", response_model=IndexJobStatus)
async def index_status(book_id: str) -> IndexJobStatus:
    return await indexing_job_manager.get_status(book_id)


@router.delete("/{book_id}/index", response_model=BookIndexResponse)
async def delete_index(book_id: str) -> BookIndexResponse:
    if indexing_job_manager.is_running(book_id):
        raise HTTPException(status_code=409, detail="This book is indexing right now. Wait until it finishes.")
    return await lightrag_service.delete_index(book_id)
