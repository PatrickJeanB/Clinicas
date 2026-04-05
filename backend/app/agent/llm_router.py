# Roteia modelo por tarefa OpenRouter
import json
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import logger
from app.core.settings import settings

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"

_TASK_MODELS: dict[str, str] = {
    "classify": "openai/gpt-4o-mini",
    "respond": "anthropic/claude-3.5-sonnet",
    "summarize": "openai/gpt-4o-mini",
}

_RETRY_KWARGS = dict(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)


class LLMRouter:
    def __init__(self) -> None:
        self._or_client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=_OPENROUTER_BASE,
            default_headers={
                "HTTP-Referer": "https://clinicas.app",
                "X-Title": "Karen - Secretária IA",
            },
        )
        self._oai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ------------------------------------------------------------------
    # Completions
    # ------------------------------------------------------------------

    @retry(**_RETRY_KWARGS)
    async def complete(
        self,
        task: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.4,
    ) -> str | dict:
        """
        Envia mensagens para o modelo correspondente à tarefa.

        Retorna:
          - str quando não há tool calls
          - dict {"type": "tool_use", "tool_calls": [...]} quando o modelo
            solicita execução de ferramentas
        """
        model = _TASK_MODELS.get(task, _TASK_MODELS["respond"])
        logger.debug(f"[LLM] task={task} model={model} msgs={len(messages)}")

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._or_client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # Tool use
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in choice.message.tool_calls
            ]
            logger.debug(f"[LLM] tool_calls solicitados: {[c['name'] for c in calls]}")
            return {
                "type": "tool_use",
                "tool_calls": calls,
                "raw_message": choice.message,
            }

        content = choice.message.content or ""
        logger.debug(f"[LLM] resposta ({len(content)} chars)")
        return content

    # ------------------------------------------------------------------
    # Embeddings (direto OpenAI)
    # ------------------------------------------------------------------

    @retry(**_RETRY_KWARGS)
    async def embed(self, text: str) -> list[float]:
        logger.debug(f"[LLM] embed ({len(text)} chars)")
        response = await self._oai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding


llm_router = LLMRouter()
