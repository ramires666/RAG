# План MVP За 24 Часа

## 1. Продуктовая рамка

Нужно сделать максимально простую систему для PDF-книг, которая выглядит как:

- `RAG` в режиме `naive`
- `GraphRAG-lite` в режиме `mix`
- `AgenticRAG-lite` в режиме `auto`

Ключевой принцип: не строить три разных пайплайна. Один ingestion pipeline и один query API, но несколько режимов извлечения.

## 2. Почему не LangGraph в MVP

LangGraph полезен, когда нужны:

- многошаговые циклы `retrieve -> judge -> rewrite -> retry`
- сохранение состояния графа
- pause/resume
- human-in-the-loop
- checkpointing

Для суточного MVP это избыточно. Цена отказа от него:

- меньше гибкости для сложного agent workflow
- нет готового orchestration engine
- позже придется аккуратно заменить простой router на graph-based execution

Плюс для MVP:

- меньше кода
- меньше задержек
- меньше LLM-вызовов
- проще отладка

## 3. Архитектура

```text
PDF upload
  -> parse pages
  -> normalize text
  -> store metadata
  -> index in LightRAG
  -> ask(question, mode)
  -> route(mode=auto)
  -> answer + citations
```

## 4. Обязательные ограничения MVP

- поддерживать только `digital PDF` в первой версии
- OCR только как future task
- один пользовательский поток
- одна книга или небольшой набор книг
- без асинхронной очереди и без воркеров
- без отдельной БД на первом проходе

## 5. Компоненты

### 5.1 API слой

- `GET /health`
- `POST /books/upload`
- `POST /books/{book_id}/index`
- `POST /ask`

### 5.2 PDF ingestion

Минимум:

- принять файл
- сгенерировать `book_id`
- сохранить оригинальный PDF
- извлечь текст постранично
- сохранить `parsed/{book_id}.json`

Формат `parsed/{book_id}.json`:

```json
{
  "book_id": "sample-book",
  "title": "Sample Book",
  "pages": [
    {
      "page": 1,
      "text": "..."
    }
  ]
}
```

### 5.3 LightRAG adapter

Минимум:

- метод `index_book(book_id)`
- метод `query(question, mode)`
- поддержать `naive`, `mix`, `global`, `local`

Если интеграция с реальным LightRAG задерживает MVP, допускается временный stub adapter с тем же интерфейсом и последующая замена.

### 5.4 Router

Режим `auto`:

- сначала LLM-классификатор выбирает `naive`, `local`, `global` или `mix`
- если LLM недоступен или вернул невалидный ответ, включается fallback router
- fallback правила:
- если встречаются слова `цитата`, `страница`, `кто`, `когда`, `где` -> `naive`
- если встречаются `связь`, `отношение`, `как связан`, `персонаж`, `термин` -> `local`
- если встречаются `тема`, `смысл`, `главная идея`, `итог`, `summary` -> `global`
- иначе -> `mix`

### 5.5 Ответ

Формат ответа:

```json
{
  "mode_requested": "auto",
  "mode_used": "mix",
  "answer": "...",
  "citations": [
    {
      "book_id": "sample-book",
      "page": 12,
      "snippet": "..."
    }
  ]
}
```

## 6. Порядок разработки по часам

### Часы 1-2

- создать структуру проекта
- оформить `pyproject.toml`
- добавить `.env.example`
- поднять `FastAPI` с `/health`

### Часы 3-5

- реализовать загрузку PDF
- сохранить файл в `data/raw`
- извлечь текст по страницам
- сохранить нормализованный JSON в `data/parsed`

### Часы 6-8

- сделать `LightRAGService`
- подключить индексацию книги
- реализовать `POST /books/{book_id}/index`

### Часы 9-11

- сделать `POST /ask`
- реализовать `mode=naive|mix|global|local|auto`
- добавить простой роутер

### Часы 12-14

- показать источники в ответе
- проверить на 1-2 книгах
- подкрутить эвристики роутера

### Часы 15-18

- минимальный UI на Streamlit или Swagger-only usage
- smoke tests
- cleanup логов и ошибок

### Часы 19-24

- полировка
- демо-сценарии
- фиксация известных ограничений

## 7. Критерии готовности

- API запускается локально
- PDF можно загрузить
- текст книги извлекается и сохраняется
- книга индексируется
- запрос в `naive` отвечает
- запрос в `auto` выбирает режим и возвращает ответ
- ответ содержит хотя бы базовые ссылки на источник

## 8. Технический долг, который можно отложить

- OCR для scanned PDF
- reranker
- chunking по главам и секциям
- background jobs
- persistent DB
- полноценный Graph execution через LangGraph
- observability и tracing

## 9. Следующий шаг после MVP

После рабочего MVP:

1. заменить эвристический router на LLM router
2. добавить fallback loop
3. добавить retries и grading quality
4. при необходимости вынести orchestration в LangGraph
