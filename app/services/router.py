from __future__ import annotations

import json
from typing import Literal

from app.config import get_settings


RouteMode = Literal["naive", "local", "global", "hybrid", "mix"]
ALLOWED_MODES: tuple[RouteMode, ...] = ("naive", "local", "global", "hybrid", "mix")

ROUTER_INSTRUCTIONS = """
You are the retrieval-mode router for a PDF-book RAG system.

Your task is to choose exactly one mode for the user's question:
- naive: direct lookup in text chunks. Best for quotes, definitions, formulas, page-specific questions, and exact factual extraction.
- local: graph retrieval around a bounded set of entities, terms, characters, theorems, or concepts. Best for "how is A related to B?" in a narrow scope.
- global: whole-book or whole-chapter understanding. Best for themes, high-level summaries, main ideas, structure, conclusions, and overall interpretation.
- hybrid: combine local and global graph retrieval. Best when the user needs both specific concept relations and broader context, but the question is still concept-centric rather than quote-centric.
- mix: combine graph retrieval and vector chunk retrieval. Best for ambiguous, multi-hop, open-ended, or mixed questions where both conceptual structure and concrete passages/examples are likely needed.

Decision policy:
1. Choose naive when the user is asking for an exact place in text, a quotation, a formula, a page, or a short factual extraction.
2. Choose local when the question is about links among specific named items in a limited context.
3. Choose global when the question is about the whole book, a broad topic, a summary, the author's main point, or major sections.
4. Choose hybrid when the user asks to explain how several important concepts fit together at a meaningful but still structured level.
5. Choose mix when the question is broad, ambiguous, multi-part, needs examples plus interpretation, or may benefit from both graph reasoning and exact text evidence.

Tie-breaking:
- If the question mentions a page number, quote, citation, formula, or "what exactly is written", prefer naive.
- If the question asks "how are X and Y connected" and X/Y are specific concepts or names, prefer local.
- If the question asks "what is this book about overall", prefer global.
- If the question asks for a conceptual map of several important notions across the book, prefer hybrid.
- If the question asks for both overview and concrete supporting details/examples, prefer mix.
- When unsure between hybrid and mix, prefer mix.

Think silently. Return JSON only with one field: {"mode":"..."}.
""".strip()

ROUTER_USER_TEMPLATE = """
Classify this user question into exactly one mode: naive, local, global, hybrid, or mix.

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
            "связаны",
            "персонаж",
            "термин",
            "концепт",
            "зависимость",
        )
        self.broad_relation_keywords = (
            "главные понятия",
            "основные понятия",
            "в книге",
            "между собой",
            "главные темы",
            "основные темы",
        )
        self.hybrid_keywords = (
            "как устроено",
            "как связаны",
            "как соотносятся",
            "объясни взаимосвязь",
            "карта понятий",
            "система понятий",
            "как понятия связаны",
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
        if any(keyword in text for keyword in self.hybrid_keywords):
            return "hybrid"
        if any(keyword in text for keyword in self.graph_keywords) and any(
            keyword in text for keyword in self.broad_relation_keywords
        ):
            return "mix"
        if any(keyword in text for keyword in self.graph_keywords):
            return "local"
        return "mix"
