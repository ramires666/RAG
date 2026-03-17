from typing import Literal

from pydantic import BaseModel, Field


Mode = Literal["naive", "local", "global", "hybrid", "mix", "auto"]


class BookUploadResponse(BaseModel):
    book_id: str
    title: str
    pages: int
    raw_path: str
    parsed_path: str


class BookIndexResponse(BaseModel):
    book_id: str
    status: str
    detail: str


class BookSummary(BaseModel):
    book_id: str
    title: str
    pages: int
    status: str
    uploaded_at: str | None = None
    indexed_at: str | None = None
    raw_path: str
    parsed_path: str
    index_path: str | None = None


class RepairPlanResponse(BaseModel):
    book_id: str
    status: str
    detail: str
    total_docs: int = 0
    processed_docs: int = 0
    failed_docs: int = 0
    pending_docs: int = 0
    processing_docs: int = 0
    inconsistent_docs: int = 0
    missing_docs: int = 0
    repairable_docs: int = 0


class SettingsStatus(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    embedding_backend: str
    embedding_model: str | None = None
    ready_for_query: bool
    ready_for_indexing: bool


class GpuStatus(BaseModel):
    name: str | None = None
    utilization_gpu: int | None = None
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None


class IndexJobStatus(BaseModel):
    book_id: str
    status: str
    detail: str
    total_docs: int = 0
    processed_docs: int = 0
    failed_docs: int = 0
    remaining_docs: int = 0
    progress_percent: float = 0
    chunk_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    format_error_count: int = 0
    relation_format_error_count: int = 0
    entity_format_error_count: int = 0
    warning_chunk_count: int = 0
    last_warning: str | None = None
    elapsed_seconds: int | None = None
    pages_per_minute: float | None = None
    eta_seconds: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    gpu: GpuStatus | None = None


class Citation(BaseModel):
    book_id: str
    page: int | None = None
    snippet: str = ""


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    mode: Mode = "auto"
    book_id: str | None = None


class AskResponse(BaseModel):
    mode_requested: Mode
    mode_used: Literal["naive", "local", "global", "hybrid", "mix"]
    answer: str
    citations: list[Citation] = Field(default_factory=list)
