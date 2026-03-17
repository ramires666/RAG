from __future__ import annotations

import json
from typing import Literal

from app.config import get_settings


RouteMode = Literal["naive", "local", "global", "mix"]
ALLOWED_MODES: tuple[RouteMode, ...] = ("naive", "local", "global", "mix")

ROUTER_INSTRUCTIONS = """
You are a query router for a PDF books RAG system.

Classify the user question into exactly one retrieval mode:
- naive: factual lookup, quote request, page-specific question, direct extraction
- local: relationships between entities, characters, terms, or concepts in a bounded context
- global: whole-book themes, high-level summaries, central ideas, broad conclusions
- mix: ambiguous, broad, multi-hop, or when both graph-style and vector-style retrieval may help

Return only JSON that matches the provided schema.
""".strip()

ROUTER_USER_TEMPLATE = """
Classify this user question into exactly one mode: naive, local, global, or mix.

Question:
{question}

Return JSON only, for example:
{{"mode":"mix"}}
""".strip()


class QueryRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.naive_keywords = (
            "цитата",
            "страница",
            "кто",
            "когда",
            "где",
            "сколько",
            "как зовут",
        )
        self.graph_keywords = (
            "связь",
            "отношение",
            "связан",
            "персонаж",
            "термин",
            "концепт",
            "зависимость",
        )
        self.global_keywords = (
            "тема",
            "смысл",
            "главная идея",
            "итог",
            "вывод",
            "summary",
            "резюме",
        )

    async def route(self, question: str) -> RouteMode:
        llm_mode = await self._route_with_llm(question)
        if llm_mode is not None:
            return llm_mode
        return self._heuristic_route(question)

    async def _route_with_llm(self, question: str) -> RouteMode | None:
        if not self.settings.openai_api_key and not self.settings.openai_base_url:
            return None

        try:
            from openai import AsyncOpenAI
        except ImportError:
            return None

        client_kwargs: dict[str, str] = {"api_key": self.settings.openai_api_key or "not-needed"}
        if self.settings.openai_base_url:
            client_kwargs["base_url"] = str(self.settings.openai_base_url)

        schema = {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": list(ALLOWED_MODES),
                }
            },
            "required": ["mode"],
            "additionalProperties": False,
        }

        try:
            async with AsyncOpenAI(**client_kwargs) as client:
                response = await client.chat.completions.create(
                    model=self.settings.router_model,
                    messages=[
                        {"role": "system", "content": ROUTER_INSTRUCTIONS},
                        {
                            "role": "user",
                            "content": ROUTER_USER_TEMPLATE.format(question=question),
                        },
                    ],
                    temperature=0,
                    max_tokens=32,
                    response_format={"type": "json_object"},
                )
        except Exception:
            return None

        content = response.choices[0].message.content if response.choices else ""
        return self._parse_llm_output(content or "")

    def _parse_llm_output(self, output_text: str) -> RouteMode | None:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError:
            return self._extract_mode(output_text)

        mode = payload.get("mode")
        if mode in ALLOWED_MODES:
            return mode
        return self._extract_mode(output_text)

    def _extract_mode(self, text: str) -> RouteMode | None:
        lowered = text.lower()
        for mode in ALLOWED_MODES:
            if mode in lowered:
                return mode
        return None

    def _heuristic_route(self, question: str) -> RouteMode:
        text = question.lower()
        if any(keyword in text for keyword in self.naive_keywords):
            return "naive"
        if any(keyword in text for keyword in self.global_keywords):
            return "global"
        if any(keyword in text for keyword in self.graph_keywords):
            return "local"
        return "mix"
