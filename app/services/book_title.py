import re
from pathlib import Path
from typing import Any, Mapping, Sequence


AUTHOR_INITIALS_RE = re.compile(r"^(?:[A-ZА-ЯЁ]\.\s*){1,3}[A-ZА-ЯЁ][A-ZА-ЯЁA-Za-zА-Яа-яЁё-]+$")
BOOK_ID_SUFFIX_RE = re.compile(r"-[0-9a-f]{8}$", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)
STOP_TITLE_LINE_RE = re.compile(
    r"(оглавление|содержание|table of contents|contents|предисловие|isbn|copyright|all rights reserved|"
    r"удк|ббк|допущено|министерств|издательств|пресс\b|press\b|издание\s+\w+|edition\b|москва\b|moscow\b)",
    re.IGNORECASE,
)


def sanitize_pdf_metadata(metadata: Mapping[str, Any] | None) -> dict[str, str]:
    if not metadata:
        return {}

    cleaned: dict[str, str] = {}
    for key in ("title", "author", "subject", "keywords", "creator", "producer"):
        value = str(metadata.get(key, "")).strip()
        if value:
            cleaned[key] = _normalize_spaces(value)
    return cleaned


def resolve_book_title(
    *,
    filename: str | None = None,
    book_id: str | None = None,
    current_title: str | None = None,
    metadata_title: str | None = None,
    page_texts: Sequence[str] | None = None,
) -> str:
    normalized_current = _normalize_spaces(current_title or "")
    if normalized_current and not _looks_like_placeholder_title(normalized_current, filename, book_id):
        return normalized_current

    normalized_metadata = _normalize_spaces(metadata_title or "")
    if normalized_metadata and not _looks_like_placeholder_title(normalized_metadata, filename, book_id):
        return normalized_metadata

    inferred = _infer_title_from_pages(page_texts or [])
    if inferred:
        return inferred

    fallback = _prettify_filename(filename) or _prettify_filename(book_id) or "Book"
    return fallback


def _infer_title_from_pages(page_texts: Sequence[str]) -> str:
    for page_text in page_texts[:5]:
        candidate = _extract_title_from_page(page_text)
        if candidate:
            return candidate
    return ""


def _extract_title_from_page(page_text: str | None) -> str:
    lines = [
        _normalize_spaces(line)
        for line in str(page_text or "").splitlines()
        if _normalize_spaces(line)
    ]
    if not lines:
        return ""

    if _is_non_title_page(lines):
        return ""

    while len(lines) > 2 and AUTHOR_INITIALS_RE.fullmatch(lines[0]):
        lines = lines[1:]

    collected: list[str] = []
    for line in lines[:12]:
        if STOP_TITLE_LINE_RE.search(line):
            if collected:
                break
            continue
        if _looks_like_noise_line(line):
            if collected:
                break
            continue

        collected.append(_smart_title_case(line))
        if len(collected) >= 4:
            break

    title = _normalize_spaces(" ".join(collected))
    return title if len(title) >= 4 else ""


def _is_non_title_page(lines: Sequence[str]) -> bool:
    preview = " ".join(lines[:4]).lower()
    return any(marker in preview for marker in ("оглавление", "содержание", "table of contents", "contents"))


def _looks_like_noise_line(line: str) -> bool:
    stripped = line.strip(" .,-_/*")
    if not stripped:
        return True
    if len(stripped) > 120:
        return True
    if re.fullmatch(r"[\d./ -]+", stripped):
        return True
    digits = sum(char.isdigit() for char in stripped)
    letters = sum(char.isalpha() for char in stripped)
    if digits >= 4 and digits >= letters:
        return True
    return False


def _looks_like_placeholder_title(title: str, filename: str | None, book_id: str | None) -> bool:
    normalized_title = _slugish(title)
    if not normalized_title:
        return True

    candidates = {
        _slugish(Path(filename).stem) if filename else "",
        _slugish(_book_id_stem(book_id)) if book_id else "",
    }
    candidates.discard("")
    return normalized_title in candidates


def _book_id_stem(book_id: str | None) -> str:
    return BOOK_ID_SUFFIX_RE.sub("", str(book_id or ""))


def _prettify_filename(value: str | None) -> str:
    stem = Path(str(value or "")).stem
    if not stem:
        return ""
    pretty = re.sub(r"[_-]+", " ", stem)
    pretty = _normalize_spaces(pretty)
    if not pretty:
        return ""
    return _smart_title_case(pretty)


def _smart_title_case(value: str) -> str:
    value = _normalize_spaces(value)
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё]+", "", value)
    if letters and letters.upper() == letters:
        return value.lower().title()
    return value


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slugish(value: str) -> str:
    return NON_ALNUM_RE.sub("", str(value or "").lower())
