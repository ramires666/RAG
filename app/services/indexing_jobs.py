import asyncio
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.schemas import GpuStatus, IndexJobStatus
from app.services.lightrag_service import LightRAGService


FINAL_STATUSES = {"indexed", "error", "deleted", "idle"}
FORMAT_ERROR_MARKER = "LLM output format error"
RELATION_MARKERS = ("REALTION", "RELATION")
ENTITY_MARKER = "ENTITY"
CHUNK_ID_RE = re.compile(r"(chunk-[a-f0-9]+)")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _JobState:
    book_id: str
    operation: str
    status: str
    detail: str
    total_docs: int
    processed_docs: int = 0
    failed_docs: int = 0
    chunk_count: int = 0
    format_error_count: int = 0
    relation_format_error_count: int = 0
    entity_format_error_count: int = 0
    warning_chunks: set[str] = field(default_factory=set)
    last_warning: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    task: asyncio.Task | None = None
    progress_samples: list[tuple[float, int]] = field(default_factory=list)


class _LightRAGWarningHandler(logging.Handler):
    def __init__(self, manager: "IndexingJobManager") -> None:
        super().__init__(level=logging.WARNING)
        self._manager = manager

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._manager.consume_lightrag_warning(record.getMessage())
        except Exception:
            return


class IndexingJobManager:
    def __init__(self) -> None:
        self._service = LightRAGService()
        self._jobs: dict[str, _JobState] = {}
        self._lock = asyncio.Lock()
        self._lightrag_logger = logging.getLogger("lightrag")
        existing = next(
            (handler for handler in self._lightrag_logger.handlers if isinstance(handler, _LightRAGWarningHandler)),
            None,
        )
        if existing is not None:
            self._warning_handler = existing
            self._warning_handler._manager = self
        else:
            self._warning_handler = _LightRAGWarningHandler(self)
            self._warning_handler.setLevel(logging.WARNING)
            self._lightrag_logger.addHandler(self._warning_handler)

    async def start_reindex(self, book_id: str) -> IndexJobStatus:
        async with self._lock:
            running_book_id = self.active_book_id()
            if running_book_id and running_book_id != book_id:
                return IndexJobStatus(
                    book_id=book_id,
                    status="error",
                    detail=f"Another indexing job is already running for {running_book_id}. Wait until it finishes.",
                    total_docs=self._service.source_document_count(book_id),
                    gpu=self._read_gpu_status(),
                )

            current = self._jobs.get(book_id)
            if current and current.task and not current.task.done():
                return await self.get_status(book_id)

            total_docs = self._service.source_document_count(book_id)
            now = _utc_now()
            state = _JobState(
                book_id=book_id,
                operation="reindex",
                status="queued",
                detail="Queued for reindex.",
                total_docs=total_docs,
                started_at=now,
                updated_at=now,
            )
            state.progress_samples.append((time.monotonic(), 0))
            state.task = asyncio.create_task(self._run_reindex(state))
            self._jobs[book_id] = state

        return await self.get_status(book_id)

    async def start_repair(self, book_id: str) -> IndexJobStatus:
        async with self._lock:
            running_book_id = self.active_book_id()
            if running_book_id and running_book_id != book_id:
                return IndexJobStatus(
                    book_id=book_id,
                    status="error",
                    detail=f"Another indexing job is already running for {running_book_id}. Wait until it finishes.",
                    total_docs=self._service.source_document_count(book_id),
                    gpu=self._read_gpu_status(),
                )

            current = self._jobs.get(book_id)
            if current and current.task and not current.task.done():
                return await self.get_status(book_id)

            total_docs = self._service.source_document_count(book_id)
            now = _utc_now()
            state = _JobState(
                book_id=book_id,
                operation="repair",
                status="queued",
                detail="Queued for repair scan and incremental reprocessing.",
                total_docs=total_docs,
                started_at=now,
                updated_at=now,
            )
            state.progress_samples.append((time.monotonic(), 0))
            state.task = asyncio.create_task(self._run_repair(state))
            self._jobs[book_id] = state

        return await self.get_status(book_id)

    async def get_status(self, book_id: str) -> IndexJobStatus:
        state = self._jobs.get(book_id)
        if state is None:
            stats = self._service.get_progress_stats(book_id)
            total_docs = self._service.source_document_count(book_id)
            if stats["chunk_count"] > 0 and stats["failed_docs"] == 0:
                status = "indexed"
                detail = "Indexed and ready."
            elif stats["processed_docs"] > 0 or stats["failed_docs"] > 0:
                status = "draft"
                detail = (
                    "Draft index is available. "
                    f"processed_docs={stats['processed_docs']}, failed_docs={stats['failed_docs']}, chunks={stats['chunk_count']}."
                )
            else:
                status = "idle"
                detail = "No active indexing job."
            metrics = self._build_timing_metrics(
                total_docs=total_docs,
                processed_docs=stats["processed_docs"],
                failed_docs=stats["failed_docs"],
                started_at=None,
            )
            return IndexJobStatus(
                book_id=book_id,
                status=status,
                detail=detail,
                total_docs=total_docs,
                processed_docs=stats["processed_docs"],
                failed_docs=stats["failed_docs"],
                remaining_docs=metrics["remaining_docs"],
                progress_percent=metrics["progress_percent"],
                chunk_count=stats["chunk_count"],
                entity_count=stats["entity_count"],
                relation_count=stats["relation_count"],
                format_error_count=0,
                relation_format_error_count=0,
                entity_format_error_count=0,
                warning_chunk_count=0,
                last_warning=None,
                elapsed_seconds=metrics["elapsed_seconds"],
                pages_per_minute=metrics["pages_per_minute"],
                eta_seconds=metrics["eta_seconds"],
                gpu=self._read_gpu_status(),
            )

        self._refresh_progress(state)
        if state.task and state.task.done() and state.finished_at is None:
            state.finished_at = _utc_now()
            state.updated_at = state.finished_at
        return self._to_response(state)

    def is_running(self, book_id: str | None = None) -> bool:
        if book_id is not None:
            state = self._jobs.get(book_id)
            return bool(state and state.task and not state.task.done())
        return self.active_book_id() is not None

    def active_book_id(self) -> str | None:
        for state in self._jobs.values():
            if state.task and not state.task.done():
                return state.book_id
        return None

    def consume_lightrag_warning(self, message: str) -> None:
        if FORMAT_ERROR_MARKER not in message:
            return

        active_book_id = self.active_book_id()
        if not active_book_id:
            return

        state = self._jobs.get(active_book_id)
        if state is None:
            return

        state.format_error_count += 1
        state.last_warning = message

        if any(marker in message for marker in RELATION_MARKERS):
            state.relation_format_error_count += 1
        elif ENTITY_MARKER in message:
            state.entity_format_error_count += 1

        match = CHUNK_ID_RE.search(message)
        if match:
            state.warning_chunks.add(match.group(1))
        state.updated_at = _utc_now()

    async def _run_reindex(self, state: _JobState) -> None:
        state.status = "running"
        state.detail = "Deleting old index and rebuilding it."
        state.updated_at = _utc_now()

        monitor_task = asyncio.create_task(self._monitor_progress(state))
        try:
            result = await self._service.reindex_book(state.book_id)
            self._refresh_progress(state)
            state.status = result.status
            state.detail = result.detail
        except Exception as exc:
            self._refresh_progress(state)
            state.status = "error"
            state.detail = f"Indexing failed: {exc}"
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            state.updated_at = _utc_now()
            state.finished_at = state.updated_at

    async def _run_repair(self, state: _JobState) -> None:
        state.status = "running"
        state.detail = "Scanning missing and failed pages, then reprocessing only them."
        state.updated_at = _utc_now()

        monitor_task = asyncio.create_task(self._monitor_progress(state))
        try:
            result = await self._service.repair_index(state.book_id)
            self._refresh_progress(state)
            state.status = result.status
            state.detail = result.detail
        except Exception as exc:
            self._refresh_progress(state)
            state.status = "error"
            state.detail = f"Repair failed: {exc}"
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            state.updated_at = _utc_now()
            state.finished_at = state.updated_at

    async def _monitor_progress(self, state: _JobState) -> None:
        while True:
            self._refresh_progress(state)
            await asyncio.sleep(1.0)

    def _refresh_progress(self, state: _JobState) -> None:
        stats = self._service.get_progress_stats(state.book_id)
        state.processed_docs = stats["processed_docs"]
        state.failed_docs = stats["failed_docs"]
        state.chunk_count = stats["chunk_count"]
        completed = state.processed_docs + state.failed_docs
        self._record_progress_sample(state, completed)
        if state.total_docs <= 0:
            state.total_docs = self._service.source_document_count(state.book_id)
        state.updated_at = _utc_now()
        if state.status == "running":
            prefix = "Repairing" if state.operation == "repair" else "Running"
            state.detail = f"{prefix}: {completed}/{state.total_docs} pages, failed={state.failed_docs}, chunks={state.chunk_count}"

    def _to_response(self, state: _JobState) -> IndexJobStatus:
        stats = self._service.get_progress_stats(state.book_id)
        metrics = self._build_timing_metrics(
            total_docs=state.total_docs,
            processed_docs=stats["processed_docs"],
            failed_docs=stats["failed_docs"],
            started_at=state.started_at,
            progress_samples=state.progress_samples,
        )
        return IndexJobStatus(
            book_id=state.book_id,
            status=state.status,
            detail=state.detail,
            total_docs=state.total_docs,
            processed_docs=stats["processed_docs"],
            failed_docs=stats["failed_docs"],
            remaining_docs=metrics["remaining_docs"],
            progress_percent=metrics["progress_percent"],
            chunk_count=stats["chunk_count"],
            entity_count=stats["entity_count"],
            relation_count=stats["relation_count"],
            format_error_count=state.format_error_count,
            relation_format_error_count=state.relation_format_error_count,
            entity_format_error_count=state.entity_format_error_count,
            warning_chunk_count=len(state.warning_chunks),
            last_warning=state.last_warning,
            elapsed_seconds=metrics["elapsed_seconds"],
            pages_per_minute=metrics["pages_per_minute"],
            eta_seconds=metrics["eta_seconds"],
            started_at=state.started_at,
            updated_at=state.updated_at,
            finished_at=state.finished_at,
            gpu=self._read_gpu_status(),
        )

    def _build_timing_metrics(
        self,
        total_docs: int,
        processed_docs: int,
        failed_docs: int,
        started_at: str | None,
        progress_samples: list[tuple[float, int]] | None = None,
    ) -> dict[str, int | float | None]:
        completed = processed_docs + failed_docs
        remaining = max(total_docs - completed, 0)
        progress_percent = round((completed / total_docs) * 100, 1) if total_docs > 0 else 0.0

        elapsed_seconds: int | None = None
        pages_per_minute: float | None = None
        eta_seconds: int | None = None
        if started_at:
            try:
                started = datetime.fromisoformat(started_at)
                elapsed_seconds = max(int((datetime.now(timezone.utc) - started).total_seconds()), 0)
            except ValueError:
                elapsed_seconds = None

        if progress_samples:
            pages_per_minute, eta_seconds = self._estimate_speed_and_eta(
                progress_samples=progress_samples,
                remaining=remaining,
            )

        return {
            "remaining_docs": remaining,
            "progress_percent": progress_percent,
            "elapsed_seconds": elapsed_seconds,
            "pages_per_minute": pages_per_minute,
            "eta_seconds": eta_seconds,
        }

    def _record_progress_sample(self, state: _JobState, completed: int) -> None:
        now = time.monotonic()
        if not state.progress_samples:
            state.progress_samples.append((now, completed))
            return

        last_time, last_completed = state.progress_samples[-1]
        if completed != last_completed or (now - last_time) >= 5:
            state.progress_samples.append((now, completed))

        window_seconds = 180
        cutoff = now - window_seconds
        state.progress_samples = [
            sample for sample in state.progress_samples if sample[0] >= cutoff
        ]

    def _estimate_speed_and_eta(
        self,
        progress_samples: list[tuple[float, int]],
        remaining: int,
    ) -> tuple[float | None, int | None]:
        if len(progress_samples) < 3:
            return None, None

        end_time, end_completed = progress_samples[-1]
        stable_samples = [
            sample for sample in progress_samples if (end_time - sample[0]) <= 90
        ]
        if len(stable_samples) < 3:
            return None, None

        start_time, start_completed = stable_samples[0]
        delta_time = end_time - start_time
        delta_completed = end_completed - start_completed
        if delta_time < 45 or delta_completed < 5:
            return None, None

        short_rate = delta_completed / (delta_time / 60)

        long_start_time, long_start_completed = progress_samples[0]
        long_delta_time = end_time - long_start_time
        long_delta_completed = end_completed - long_start_completed
        if long_delta_time < 60 or long_delta_completed < 5:
            return None, None

        long_rate = long_delta_completed / (long_delta_time / 60)
        if long_rate <= 0 or short_rate <= 0:
            return None, None

        stability_ratio = max(short_rate, long_rate) / min(short_rate, long_rate)
        if stability_ratio > 1.8:
            return None, None

        blended_rate = (short_rate * 0.65) + (long_rate * 0.35)
        pages_per_minute = round(blended_rate, 1)
        if pages_per_minute <= 0 or remaining <= 0:
            return pages_per_minute if pages_per_minute > 0 else None, None

        eta_seconds = max(int((remaining / pages_per_minute) * 60), 0)
        return pages_per_minute, eta_seconds

    def _read_gpu_status(self) -> GpuStatus | None:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return None

        if result.returncode != 0:
            return None

        line = next((item.strip() for item in result.stdout.splitlines() if item.strip()), "")
        if not line:
            return None

        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 4:
            return None

        try:
            return GpuStatus(
                name=parts[0],
                utilization_gpu=int(parts[1]),
                memory_used_mb=int(parts[2]),
                memory_total_mb=int(parts[3]),
            )
        except ValueError:
            return None


indexing_job_manager = IndexingJobManager()
