import asyncio
import json
import logging
import re
import shlex
import shutil
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from app.config import get_settings
from app.models.schemas import AskResponse, BookIndexResponse, Citation, RepairPlanResponse, SettingsStatus
from app.services.book_catalog import BookCatalog
from app.services.local_embeddings import make_hash_embedding_func
from app.services.page_filter import is_indexable_page


PAGE_RE = re.compile(r"#page=(\d+)")
TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]{3,}")
DRAFT_GLOBAL_HINTS = (
    "summary",
    "краткое",
    "обзор",
    "в целом",
    "главные",
    "основные",
    "темы",
    "структура",
    "разделы",
    "что изучается",
)
LOGGER = logging.getLogger(__name__)
LLM_RESTART_LOCK = asyncio.Lock()


class LightRAGService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.book_catalog = BookCatalog()

    def settings_status(self) -> SettingsStatus:
        has_llm = bool(self.settings.openai_base_url and self.settings.openai_model)
        has_embedding_server = bool(self.settings.embedding_base_url and self.settings.embedding_model)
        embedding_backend = "local_hash"
        embedding_model = f"local-hash-{self.settings.embedding_dim}"
        if has_embedding_server:
            embedding_backend = "openai_compatible"
            embedding_model = self.settings.embedding_model

        return SettingsStatus(
            llm_base_url=self.settings.openai_base_url,
            llm_model=self.settings.openai_model,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            ready_for_query=has_llm,
            ready_for_indexing=has_llm,
        )

    async def delete_index(self, book_id: str) -> BookIndexResponse:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="Parsed book file not found. Upload the PDF first.",
            )

        removed = self._delete_index_artifacts(book_id)
        detail = "Index deleted." if removed else "No existing index artifacts were found."
        return BookIndexResponse(book_id=book_id, status="deleted", detail=detail)

    def scan_repair_plan(self, book_id: str) -> RepairPlanResponse:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return RepairPlanResponse(
                book_id=book_id,
                status="error",
                detail="Parsed book file not found. Upload the PDF first.",
            )

        _, ids, _ = self._build_page_documents(payload)
        doc_status = self._load_doc_status(book_id)
        full_doc_ids = self._load_full_doc_ids(book_id)

        processed_docs = 0
        failed_docs = 0
        pending_docs = 0
        processing_docs = 0
        inconsistent_docs = 0

        for doc_id, item in doc_status.items():
            status = str(item.get("status", "")).lower()
            if doc_id not in full_doc_ids and status in {"failed", "pending", "processing"}:
                inconsistent_docs += 1

            if status == "processed":
                processed_docs += 1
            elif status == "failed":
                failed_docs += 1
            elif status == "pending":
                pending_docs += 1
            elif status == "processing":
                processing_docs += 1

        missing_docs = len([doc_id for doc_id in ids if doc_id not in doc_status])
        repairable_docs = failed_docs + pending_docs + processing_docs + inconsistent_docs + missing_docs

        if repairable_docs == 0:
            status = "clean"
            detail = "No failed, pending, processing, inconsistent, or missing pages were found."
        else:
            status = "repairable"
            detail = (
                f"Repair scan found missing={missing_docs}, failed={failed_docs}, pending={pending_docs}, "
                f"processing={processing_docs}, inconsistent={inconsistent_docs}."
            )

        return RepairPlanResponse(
            book_id=book_id,
            status=status,
            detail=detail,
            total_docs=len(ids),
            processed_docs=processed_docs,
            failed_docs=failed_docs,
            pending_docs=pending_docs,
            processing_docs=processing_docs,
            inconsistent_docs=inconsistent_docs,
            missing_docs=missing_docs,
            repairable_docs=repairable_docs,
        )

    async def index_book(self, book_id: str) -> BookIndexResponse:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="Parsed book file not found. Upload the PDF first.",
            )

        if not self.settings.openai_base_url or not self.settings.openai_model:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="LLM config is missing. Set OPENAI_BASE_URL and OPENAI_MODEL in .env.",
            )

        documents, ids, file_paths = self._build_page_documents(payload)
        if not documents:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="Book has no extractable text pages to index.",
            )

        working_dir = self._book_workdir(book_id)
        self._delete_index_artifacts(book_id)
        working_dir.mkdir(parents=True, exist_ok=True)

        rag = self._create_rag(working_dir)

        try:
            async with self._managed_rag(rag):
                await rag.ainsert(documents, ids=ids, file_paths=file_paths)
        except Exception as exc:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail=f"Indexing failed: {exc}",
            )

        health = self._index_health(book_id)
        if health["chunk_count"] == 0 or health["failed_docs"] > 0:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail=(
                    "Indexing did not finish cleanly. "
                    f"chunks={health['chunk_count']}, failed_docs={health['failed_docs']}, "
                    f"processed_docs={health['processed_docs']}. Re-run indexing after fixing the LLM backend."
                ),
            )

        self._write_index_marker(payload, book_id, len(documents), health)

        return BookIndexResponse(
            book_id=book_id,
            status="indexed",
            detail=f"Indexed {len(documents)} text pages into LightRAG.",
        )

    async def reindex_book(self, book_id: str) -> BookIndexResponse:
        self._delete_index_artifacts(book_id)
        return await self.index_book(book_id)

    async def repair_index(self, book_id: str) -> BookIndexResponse:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="Parsed book file not found. Upload the PDF first.",
            )

        if not self.settings.openai_base_url or not self.settings.openai_model:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="LLM config is missing. Set OPENAI_BASE_URL and OPENAI_MODEL in .env.",
            )

        documents, ids, file_paths = self._build_page_documents(payload)
        if not documents:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail="Book has no extractable text pages to index.",
            )

        working_dir = self._book_workdir(book_id)
        if not working_dir.exists():
            return await self.index_book(book_id)

        repair_plan = self.scan_repair_plan(book_id)
        if repair_plan.status == "error":
            return BookIndexResponse(book_id=book_id, status="error", detail=repair_plan.detail)

        if repair_plan.repairable_docs == 0:
            health = self._index_health(book_id)
            if health["chunk_count"] > 0 and health["failed_docs"] == 0 and health["processed_docs"] > 0:
                self._write_index_marker(payload, book_id, len(documents), health)
                return BookIndexResponse(
                    book_id=book_id,
                    status="indexed",
                    detail="Repair scan found no missing or failed pages. The index is already clean.",
                )
            return BookIndexResponse(
                book_id=book_id,
                status="draft",
                detail="Repair scan found no new repair targets, but the index is still incomplete.",
            )

        expected_docs = {doc_id: document for doc_id, document in zip(ids, documents, strict=False)}
        expected_paths = {doc_id: file_path for doc_id, file_path in zip(ids, file_paths, strict=False)}
        doc_status = self._load_doc_status(book_id)
        full_doc_ids = self._load_full_doc_ids(book_id)
        inconsistent_ids = [
            doc_id
            for doc_id, item in doc_status.items()
            if doc_id not in full_doc_ids and str(item.get("status", "")).lower() in {"failed", "pending", "processing"}
        ]
        missing_ids = [doc_id for doc_id in ids if doc_id not in doc_status]
        enqueue_ids = [doc_id for doc_id in ids if doc_id in set(missing_ids) | set(inconsistent_ids)]

        if inconsistent_ids:
            for doc_id in inconsistent_ids:
                doc_status.pop(doc_id, None)
            doc_status_path = working_dir / "kv_store_doc_status.json"
            doc_status_path.write_text(json.dumps(doc_status, ensure_ascii=False, indent=2), encoding="utf-8")

        rag = self._create_rag(working_dir)
        try:
            async with self._managed_rag(rag):
                if enqueue_ids:
                    await rag.apipeline_enqueue_documents(
                        [expected_docs[doc_id] for doc_id in enqueue_ids],
                        ids=enqueue_ids,
                        file_paths=[expected_paths[doc_id] for doc_id in enqueue_ids],
                    )
                await rag.apipeline_process_enqueue_documents()
        except Exception as exc:
            return BookIndexResponse(
                book_id=book_id,
                status="error",
                detail=f"Repair failed: {exc}",
            )

        health = self._index_health(book_id)
        if health["chunk_count"] > 0 and health["failed_docs"] == 0 and health["processed_docs"] > 0:
            self._write_index_marker(payload, book_id, len(documents), health)
            return BookIndexResponse(
                book_id=book_id,
                status="indexed",
                detail=(
                    "Repair finished cleanly. "
                    f"processed_docs={health['processed_docs']}, failed_docs={health['failed_docs']}, chunks={health['chunk_count']}."
                ),
            )

        return BookIndexResponse(
            book_id=book_id,
            status="draft",
            detail=(
                "Repair finished, but the index is still partial. "
                f"processed_docs={health['processed_docs']}, failed_docs={health['failed_docs']}, chunks={health['chunk_count']}."
            ),
        )

    def source_document_count(self, book_id: str) -> int:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return 0
        documents, _, _ = self._build_page_documents(payload)
        return len(documents)

    def get_index_health(self, book_id: str) -> dict[str, int]:
        return self._index_health(book_id)

    def get_progress_stats(self, book_id: str) -> dict[str, int]:
        health = self._index_health(book_id)
        workdir = self._book_workdir(book_id)
        return {
            **health,
            "entity_count": self._sum_count_store(workdir / "kv_store_full_entities.json"),
            "relation_count": self._sum_count_store(workdir / "kv_store_full_relations.json"),
        }

    async def query(self, question: str, mode: str, requested_mode: str, book_id: str | None = None) -> AskResponse:
        normalized_mode = self._normalize_mode(mode)
        if not book_id:
            return AskResponse(
                mode_requested=requested_mode,  # type: ignore[arg-type]
                mode_used=normalized_mode,
                answer="Choose a book before asking a question.",
                citations=[],
            )

        index_marker = self.settings.index_dir / f"{book_id}.indexed.json"
        health = self._index_health(book_id)
        if not index_marker.exists():
            if health["processed_docs"] > 0 or health["chunk_count"] > 0:
                return await self._query_draft_index(
                    question=question,
                    mode=normalized_mode,
                    requested_mode=requested_mode,
                    book_id=book_id,
                    health=health,
                )
            return AskResponse(
                mode_requested=requested_mode,  # type: ignore[arg-type]
                mode_used=normalized_mode,
                answer="This book is not indexed yet. Upload it and click Reindex first.",
                citations=[],
            )

        if health["chunk_count"] == 0:
            if health["processed_docs"] > 0:
                return await self._query_draft_index(
                    question=question,
                    mode=normalized_mode,
                    requested_mode=requested_mode,
                    book_id=book_id,
                    health=health,
                )
            return AskResponse(
                mode_requested=requested_mode,  # type: ignore[arg-type]
                mode_used=normalized_mode,
                answer=(
                    "This index is incomplete: no text chunks were created. "
                    "Click Reindex again to rebuild the book after the backend fix."
                ),
                citations=[],
            )
        if health["failed_docs"] > 0:
            return await self._query_draft_index(
                question=question,
                mode=normalized_mode,
                requested_mode=requested_mode,
                book_id=book_id,
                health=health,
            )

        rag = self._create_rag(self._book_workdir(book_id))

        try:
            async with self._managed_rag(rag):
                result = await rag.aquery_llm(
                    question,
                    param=QueryParam(
                        mode=normalized_mode,
                        response_type="Multiple Paragraphs",
                        stream=False,
                        enable_rerank=False,
                    ),
                )
        except Exception:
            return await self._query_draft_index(
                question=question,
                mode=normalized_mode,
                requested_mode=requested_mode,
                book_id=book_id,
                health=health,
            )

        llm_response = result.get("llm_response", {})
        answer = llm_response.get("content") or "No relevant context found for the query."
        citations = self._extract_citations(result.get("data", {}), book_id)

        return AskResponse(
            mode_requested=requested_mode,  # type: ignore[arg-type]
            mode_used=normalized_mode,
            answer=answer,
            citations=citations,
        )

    async def _query_draft_index(
        self,
        question: str,
        mode: str,
        requested_mode: str,
        book_id: str,
        health: dict[str, int],
    ) -> AskResponse:
        prefer_spread = self._is_global_style_question(question, mode)
        limit = 12 if prefer_spread else 6
        draft_pages = self._select_draft_pages(
            book_id,
            question,
            limit=limit,
            prefer_spread=prefer_spread,
        )
        if not draft_pages:
            return AskResponse(
                mode_requested=requested_mode,  # type: ignore[arg-type]
                mode_used=mode,
                answer=(
                    "Draft index exists, but there are no stable processed pages available yet. "
                    "Wait for more pages or run Reindex again."
                ),
                citations=[],
            )

        try:
            answer = await self._answer_from_draft_pages(question, draft_pages)
        except Exception as exc:
            snippets = "\n\n".join(
                f"Page {item['page']}:\n{str(item['text'])[:800]}" for item in draft_pages[:3]
            )
            answer = (
                "Draft index answer fallback.\n\n"
                f"Question: {question}\n\n"
                f"Best available processed excerpts:\n{snippets}\n\n"
                f"LLM draft synthesis failed: {exc}"
            )

        note = (
            "[draft-index] Answer is based only on the already processed part of the book. "
            f"processed_docs={health['processed_docs']}, failed_docs={health['failed_docs']}, chunks={health['chunk_count']}.\n\n"
        )
        citations = [
            Citation(book_id=book_id, page=int(item["page"]), snippet=str(item["text"])[:240])
            for item in draft_pages[:6]
        ]

        return AskResponse(
            mode_requested=requested_mode,  # type: ignore[arg-type]
            mode_used=mode,
            answer=note + answer,
            citations=citations,
        )

    def _create_rag(self, working_dir: Path) -> LightRAG:
        llm_model = self.settings.openai_model or self.settings.router_model

        async def llm_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, Any]] | None = None,
            **kwargs: Any,
        ) -> str:
            llm_kwargs = dict(kwargs)
            llm_kwargs.pop("model", None)
            return await self._call_lightrag_llm(
                model=llm_model,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                **llm_kwargs,
            )

        return LightRAG(
            working_dir=str(working_dir),
            llm_model_name=llm_model,
            llm_model_func=llm_func,
            embedding_func=self._build_embedding_func(),
        )

    def _build_embedding_func(self) -> EmbeddingFunc:
        if self.settings.embedding_base_url and self.settings.embedding_model:
            actual_func = openai_embed.func if isinstance(openai_embed, EmbeddingFunc) else openai_embed

            async def remote_embedding(texts: list[str], **_: Any):
                return await actual_func(
                    texts=texts,
                    model=self.settings.embedding_model,
                    base_url=self.settings.embedding_base_url,
                    api_key=self.settings.embedding_api_key or self.settings.openai_api_key or "not-needed",
                    embedding_dim=self.settings.embedding_dim,
                )

            return EmbeddingFunc(
                embedding_dim=self.settings.embedding_dim,
                func=remote_embedding,
                model_name=self.settings.embedding_model,
            )

        return make_hash_embedding_func(self.settings.embedding_dim)

    @asynccontextmanager
    async def _managed_rag(self, rag: LightRAG):
        await rag.initialize_storages()
        try:
            yield rag
        finally:
            await rag.finalize_storages()

    async def _call_lightrag_llm(
        self,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        attempts = max(int(self.settings.llm_call_retry_attempts), 1)
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await openai_complete_if_cache(
                    model,
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages or [],
                    base_url=self.settings.openai_base_url,
                    api_key=self.settings.openai_api_key or "not-needed",
                    **kwargs,
                )
            except Exception as exc:
                last_exc = exc
                ready_now = await self._check_llm_ready(model)
                if ready_now:
                    raise

                grace_recovered = await self._wait_for_existing_llm_ready(
                    model=model,
                    timeout_seconds=max(int(self.settings.llm_restart_grace_seconds), 1),
                )
                if grace_recovered:
                    LOGGER.warning(
                        "LLM request failed, but the existing server recovered during grace wait. Retrying attempt %s/%s.",
                        attempt,
                        attempts,
                    )
                    continue

                LOGGER.warning(
                    "LLM call failed and readiness probe did not recover. Restart attempt %s/%s. Error: %s",
                    attempt,
                    attempts,
                    exc,
                )
                restarted = await self._restart_llm_and_wait_until_ready(model)
                if restarted:
                    continue

                if attempt >= attempts:
                    break

        if last_exc is None:
            raise RuntimeError("LLM call failed for an unknown reason.")

        raise RuntimeError(
            "LLM backend is unavailable. Auto-restart did not produce a healthy response in time."
        ) from last_exc

    async def _check_llm_health(self) -> bool:
        url = self._healthcheck_url()
        if not url:
            return False

        def _ping() -> bool:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=5) as response:
                status = getattr(response, "status", 200)
                return 200 <= int(status) < 300

        try:
            return await asyncio.to_thread(_ping)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            return False

    async def _check_llm_ready(self, model: str) -> bool:
        if not await self._check_llm_health():
            return False

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return True

        client_kwargs: dict[str, Any] = {
            "api_key": self.settings.openai_api_key or "not-needed",
            "timeout": 12,
        }
        if self.settings.openai_base_url:
            client_kwargs["base_url"] = self.settings.openai_base_url

        try:
            async with AsyncOpenAI(**client_kwargs) as client:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Return a short readiness pong."},
                        {"role": "user", "content": "ping"},
                    ],
                    temperature=0,
                    max_tokens=8,
                )
        except Exception:
            return False

        content = response.choices[0].message.content if response.choices else None
        return bool(content and str(content).strip())

    async def _restart_llm_and_wait_until_ready(self, model: str) -> bool:
        command = (self.settings.llm_restart_command or "").strip()
        if not command:
            return False

        async with LLM_RESTART_LOCK:
            if await self._wait_for_existing_llm_ready(
                model=model,
                timeout_seconds=max(int(self.settings.llm_restart_grace_seconds), 1),
            ):
                return True

            launched = await self._launch_restart_command(command)
            if not launched:
                return False

            timeout_seconds = max(int(self.settings.llm_restart_timeout_seconds), 10)
            poll_interval = max(float(self.settings.llm_restart_poll_interval_seconds), 0.5)
            deadline = asyncio.get_running_loop().time() + timeout_seconds

            while asyncio.get_running_loop().time() < deadline:
                if await self._check_llm_ready(model):
                    return True
                await asyncio.sleep(poll_interval)

            return False

    async def _launch_restart_command(self, command: str) -> bool:
        launchers = [
            self._build_powershell_start_command(command),
            ["cmd.exe", "/c", f'start "" {command}'],
        ]

        for launcher in launchers:
            if not launcher:
                continue
            try:
                wrapped_launcher = self._wrap_windows_launcher(launcher)
                result = await asyncio.to_thread(
                    subprocess.run,
                    wrapped_launcher,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
                LOGGER.warning("Failed to execute restart launcher %s: %s", launcher[0], exc)
                continue

            if result.returncode == 0:
                LOGGER.warning("Issued llama-server restart via %s", launcher[0])
                return True

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            LOGGER.warning(
                "Restart launcher %s failed with code %s. stdout=%s stderr=%s",
                launcher[0],
                result.returncode,
                stdout[:500],
                stderr[:500],
            )

        return False

    def _wrap_windows_launcher(self, launcher: list[str]) -> list[str]:
        command_line = " ".join(shlex.quote(part) for part in launcher)
        return ["/bin/bash", "-lc", command_line]

    def _build_powershell_start_command(self, command: str) -> list[str] | None:
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            LOGGER.warning("Failed to parse restart command for PowerShell launcher: %s", exc)
            return None

        if not parts:
            return None

        executable = parts[0]
        args = parts[1:]

        def _ps_quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        argument_list = ", ".join(_ps_quote(arg) for arg in args)
        script = (
            "$ErrorActionPreference='Stop'; "
            f"Start-Process -FilePath {_ps_quote(executable)} "
            f"-ArgumentList @({argument_list}) -WindowStyle Hidden"
        )

        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]

    async def _wait_for_existing_llm_ready(self, model: str, timeout_seconds: int) -> bool:
        if timeout_seconds <= 0:
            return await self._check_llm_ready(model)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        poll_interval = min(max(float(self.settings.llm_restart_poll_interval_seconds), 0.5), 2.0)

        while loop.time() < deadline:
            if await self._check_llm_ready(model):
                return True
            await asyncio.sleep(poll_interval)

        return await self._check_llm_ready(model)

    def _healthcheck_url(self) -> str | None:
        if self.settings.llm_healthcheck_url:
            return self.settings.llm_healthcheck_url.strip()

        base_url = (self.settings.openai_base_url or "").strip().rstrip("/")
        if not base_url:
            return None
        if base_url.endswith("/v1/models"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/models"
        return f"{base_url}/models"

    def _load_parsed_book(self, book_id: str) -> dict[str, Any] | None:
        parsed_path = self.settings.parsed_dir / f"{book_id}.json"
        try:
            return json.loads(parsed_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _index_health(self, book_id: str) -> dict[str, int]:
        working_dir = self._book_workdir(book_id)
        doc_status_path = working_dir / "kv_store_doc_status.json"
        text_chunks_path = working_dir / "kv_store_text_chunks.json"

        failed_docs = 0
        processed_docs = 0
        chunk_count = 0

        if doc_status_path.exists():
            try:
                doc_status = json.loads(doc_status_path.read_text(encoding="utf-8"))
                for item in doc_status.values():
                    status = str(item.get("status", ""))
                    if status == "failed":
                        failed_docs += 1
                    if status == "processed":
                        processed_docs += 1
            except (json.JSONDecodeError, OSError):
                pass

        if text_chunks_path.exists():
            try:
                chunk_store = json.loads(text_chunks_path.read_text(encoding="utf-8"))
                chunk_count = len(chunk_store)
            except (json.JSONDecodeError, OSError):
                chunk_count = 0

        return {
            "failed_docs": failed_docs,
            "processed_docs": processed_docs,
            "chunk_count": chunk_count,
        }

    def _build_page_documents(self, payload: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        title = str(payload.get("title", payload.get("book_id", "Book")))
        book_id = str(payload.get("book_id"))
        raw_path = str(payload.get("raw_path", self.settings.raw_dir / f"{book_id}.pdf"))

        documents: list[str] = []
        ids: list[str] = []
        file_paths: list[str] = []
        for page in payload.get("pages", []):
            page_number = int(page.get("page", 0))
            text = str(page.get("text", "")).strip()
            if not text:
                continue
            if not is_indexable_page(text):
                continue

            documents.append(f"Book: {title}\nPage: {page_number}\n\n{text}")
            ids.append(f"{book_id}-page-{page_number:04d}")
            file_paths.append(f"{raw_path}#page={page_number}")

        return documents, ids, file_paths

    def _select_draft_pages(
        self,
        book_id: str,
        question: str,
        limit: int = 6,
        prefer_spread: bool = False,
    ) -> list[dict[str, Any]]:
        payload = self._load_parsed_book(book_id)
        if payload is None:
            return []

        doc_status = self._load_doc_status(book_id)
        if not doc_status:
            return []

        pages_by_number = {
            int(page.get("page", 0)): str(page.get("text", "")).strip()
            for page in payload.get("pages", [])
            if int(page.get("page", 0)) > 0
        }
        tokens = self._question_tokens(question)
        candidates: list[dict[str, Any]] = []

        for item in doc_status.values():
            if str(item.get("status")) != "processed":
                continue
            page = self._extract_page_number(str(item.get("file_path", "")))
            if page is None:
                continue
            full_text = pages_by_number.get(page, "").strip()
            summary = str(item.get("content_summary", "")).strip()
            text = full_text or summary
            if not text:
                continue
            haystack = f"{summary}\n{text}".lower()
            score = sum(haystack.count(token) for token in tokens)
            if score == 0 and tokens:
                continue
            candidates.append(
                {
                    "page": page,
                    "text": text,
                    "summary": summary,
                    "updated_at": str(item.get("updated_at", "")),
                    "score": score,
                }
            )

        if not candidates:
            for item in doc_status.values():
                if str(item.get("status")) != "processed":
                    continue
                page = self._extract_page_number(str(item.get("file_path", "")))
                if page is None:
                    continue
                full_text = pages_by_number.get(page, "").strip()
                summary = str(item.get("content_summary", "")).strip()
                text = full_text or summary
                if not text:
                    continue
                candidates.append(
                    {
                        "page": page,
                        "text": text,
                        "summary": summary,
                        "updated_at": str(item.get("updated_at", "")),
                        "score": 0,
                    }
                )

        if prefer_spread:
            candidates.sort(key=lambda item: int(item["page"]))
            return self._spread_sample(candidates, limit)

        candidates.sort(key=lambda item: (-int(item["score"]), int(item["page"])))
        return candidates[:limit]

    async def _answer_from_draft_pages(self, question: str, draft_pages: list[dict[str, Any]]) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return "\n\n".join(
                f"Page {item['page']}:\n{str(item['text'])[:1200]}" for item in draft_pages[:3]
            )

        model = self.settings.openai_model or self.settings.router_model
        if not await self._check_llm_ready(model):
            await self._restart_llm_and_wait_until_ready(model)

        client_kwargs: dict[str, str] = {"api_key": self.settings.openai_api_key or "not-needed"}
        if self.settings.openai_base_url:
            client_kwargs["base_url"] = str(self.settings.openai_base_url)

        context = "\n\n".join(
            f"[Page {item['page']}]\n{str(item['text'])[:2400]}" for item in draft_pages
        )
        system_prompt = (
            "You answer questions about a PDF book using only the provided context. "
            "This is a draft partial index, so be explicit when context may be incomplete. "
            "Do not invent facts outside the supplied excerpts."
        )
        user_prompt = (
            "The following excerpts come only from already processed pages of the book.\n\n"
            f"Question:\n{question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer in Russian. If the context is insufficient, say so plainly."
        )

        try:
            async with AsyncOpenAI(**client_kwargs) as client:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=900,
                )
        except Exception:
            restarted = await self._restart_llm_and_wait_until_ready(model)
            if not restarted:
                raise
            async with AsyncOpenAI(**client_kwargs) as client:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=900,
                )
        return response.choices[0].message.content or "Недостаточно контекста в драфт-индексе."

    def _load_doc_status(self, book_id: str) -> dict[str, Any]:
        path = self._book_workdir(book_id) / "kv_store_doc_status.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _is_global_style_question(self, question: str, mode: str) -> bool:
        lowered = question.lower()
        if mode == "global":
            return True
        return any(hint in lowered for hint in DRAFT_GLOBAL_HINTS)

    def _spread_sample(self, candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        if len(candidates) <= limit:
            return candidates

        if limit <= 1:
            return [candidates[0]]

        last_index = len(candidates) - 1
        selected: list[dict[str, Any]] = []
        used_indexes: set[int] = set()

        for i in range(limit):
            index = round((last_index * i) / (limit - 1))
            if index in used_indexes:
                continue
            used_indexes.add(index)
            selected.append(candidates[index])

        return selected[:limit]

    def _load_full_doc_ids(self, book_id: str) -> set[str]:
        path = self._book_workdir(book_id) / "kv_store_full_docs.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return set()

        if not isinstance(payload, dict):
            return set()
        return {str(doc_id) for doc_id in payload.keys()}

    def _question_tokens(self, question: str) -> list[str]:
        tokens = [token.lower() for token in TOKEN_RE.findall(question)]
        seen: set[str] = set()
        result: list[str] = []
        for token in tokens:
            if token not in seen:
                result.append(token)
                seen.add(token)
        return result[:12]

    def _sum_count_store(self, path: Path) -> int:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return 0

        total = 0
        for item in payload.values():
            try:
                total += int(item.get("count", 0))
            except (TypeError, ValueError, AttributeError):
                continue
        return total

    def _extract_citations(self, data: dict[str, Any], book_id: str) -> list[Citation]:
        references = data.get("references", [])
        chunks = data.get("chunks", [])

        ref_to_snippets: dict[str, list[str]] = {}
        for chunk in chunks:
            ref_id = str(chunk.get("reference_id", ""))
            content = str(chunk.get("content", "")).strip()
            if ref_id and content:
                ref_to_snippets.setdefault(ref_id, []).append(content)

        citations: list[Citation] = []
        for ref in references[:6]:
            ref_id = str(ref.get("reference_id", ""))
            file_path = str(ref.get("file_path", ""))
            page = self._extract_page_number(file_path)
            snippet = ref_to_snippets.get(ref_id, [""])[0][:240]
            citations.append(Citation(book_id=book_id, page=page, snippet=snippet))

        if not citations and chunks:
            first_chunk = chunks[0]
            citations.append(
                Citation(
                    book_id=book_id,
                    page=self._extract_page_number(str(first_chunk.get("file_path", ""))),
                    snippet=str(first_chunk.get("content", ""))[:240],
                )
            )

        return citations

    def _extract_page_number(self, file_path: str) -> int | None:
        match = PAGE_RE.search(file_path)
        if match:
            return int(match.group(1))
        return None

    def _book_workdir(self, book_id: str) -> Path:
        return self.settings.lightrag_workdir / book_id

    def _write_index_marker(
        self,
        payload: dict[str, Any],
        book_id: str,
        indexed_pages: int,
        health: dict[str, int],
    ) -> None:
        index_marker = self.settings.index_dir / f"{book_id}.indexed.json"
        index_marker.write_text(
            json.dumps(
                {
                    "book_id": book_id,
                    "title": payload.get("title"),
                    "pages": len(payload.get("pages", [])),
                    "indexed_pages": indexed_pages,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "status": "indexed",
                    "working_dir": str(self._book_workdir(book_id)),
                    "embedding_backend": self.settings_status().embedding_backend,
                    "chunk_count": health["chunk_count"],
                    "processed_docs": health["processed_docs"],
                    "failed_docs": health["failed_docs"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _delete_index_artifacts(self, book_id: str) -> bool:
        removed = False
        working_dir = self._book_workdir(book_id)
        index_marker = self.settings.index_dir / f"{book_id}.indexed.json"

        if working_dir.exists():
            shutil.rmtree(working_dir)
            removed = True
        if index_marker.exists():
            index_marker.unlink()
            removed = True

        return removed

    def _normalize_mode(self, mode: str) -> str:
        if mode == "auto":
            return "mix"
        return mode
