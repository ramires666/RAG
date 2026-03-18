from __future__ import annotations

import re


URL_RE = re.compile(r"(https?://|www\.|@\w+\.)", re.IGNORECASE)
ISBN_RE = re.compile(r"\bisbn\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d\-\(\) ]{7,}\d)")

PROMO_MARKERS = (
    "другие книги",
    "книги издательства",
    "наши книги",
    "в этой серии",
    "серия книг",
    "каталог",
    "новинки",
    "готовятся к печати",
    "по вопросам приобретения",
    "интернет-магазин",
    "в продаже",
    "заказать книгу",
    "оптовая продажа",
    "наш сайт",
    "издательство",
    "e-mail",
    "email",
)

PRINTING_MARKERS = (
    "подписано в печать",
    "формат ",
    "гарнитура",
    "тираж",
    "заказ №",
    "заказ n",
    "отпечатано",
    "отпечатан",
    "печатных листов",
)

CONTENT_MARKERS = (
    "глава",
    "раздел",
    "§",
    "теорема",
    "лемма",
    "доказательство",
    "докажем",
    "определение",
    "пример",
    "задача",
    "решение",
    "упражнение",
    "формула",
    "интеграл",
    "производн",
    "функци",
    "матриц",
    "уравнен",
)


def is_indexable_page(text: str) -> bool:
    return classify_noncontent_page(text) is None


def classify_noncontent_page(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return "empty"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    short_lines = [line for line in lines if len(line) <= 28]
    short_line_ratio = (len(short_lines) / len(lines)) if lines else 0.0

    promo_hits = sum(1 for marker in PROMO_MARKERS if marker in normalized)
    printing_hits = sum(1 for marker in PRINTING_MARKERS if marker in normalized)
    content_hits = sum(1 for marker in CONTENT_MARKERS if marker in normalized)
    url_hits = len(URL_RE.findall(text))
    isbn_hits = len(ISBN_RE.findall(text))
    phone_hits = len(PHONE_RE.findall(text))

    if printing_hits >= 3 and content_hits == 0:
        return "printing-metadata"

    if promo_hits >= 3 and (url_hits + isbn_hits + phone_hits >= 1 or short_line_ratio >= 0.55):
        return "publisher-promo"

    if promo_hits >= 2 and (url_hits + phone_hits >= 2) and content_hits == 0:
        return "contact-promo"

    if "каталог" in normalized and short_line_ratio >= 0.55 and content_hits == 0:
        return "catalog-page"

    return None
