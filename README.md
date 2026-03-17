# RAG Books MVP

MVP за 24 часа: загрузка PDF-книги, извлечение текста, индексация в LightRAG, чат с тремя режимами:

- `naive` для простых фактологических вопросов
- `mix` как GraphRAG-lite
- `auto` как agentic-lite router через LLM без LangGraph

Подробный план находится в `docs/mvp_24h_plan.md`.

## Цель MVP

Система должна:

- принять PDF книги
- извлечь текст по страницам
- сохранить нормализованный текст и метаданные
- проиндексировать книгу в LightRAG
- ответить на вопрос в режимах `naive`, `mix`, `auto`
- вернуть ответ вместе с указанием источника

## Что не входит в MVP

- полноценный LangGraph orchestration
- Microsoft GraphRAG
- сложный OCR pipeline
- multi-agent routing
- production-grade auth, billing, queue system

## Быстрый запуск

1. Установить Python 3.11+
2. Создать виртуальное окружение
3. Установить зависимости
4. Настроить `.env`
5. Запустить API

Пример:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload
```

## Структура

```text
app/
  api/
  services/
  models/
  main.py
docs/
  mvp_24h_plan.md
data/
  raw/
  parsed/
  indexes/
scripts/
```

## API MVP

- `GET /health`
- `POST /books/upload`
- `POST /books/{book_id}/index`
- `POST /ask`

## Логика `auto`

- факт, цитата, страница -> `naive`
- связи сущностей, персонажей, терминов -> `local` или `mix`
- темы книги, итог, общий смысл -> `global` или `mix`
- если неясно -> `mix`

Для MVP `auto` сначала идет в LLM-router, а при ошибке или отсутствии ключа откатывается на простую эвристику. Это заметно проще, чем полноценный агентный граф, но точнее, чем чистый keyword routing.
