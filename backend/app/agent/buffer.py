# Buffer de 8 segundos com Redis
import asyncio
import json
from typing import Callable, Awaitable

import redis.asyncio as aioredis

from app.core.logging import logger
from app.core.settings import settings

_BUFFER_TTL = 30        # segundos — TTL máximo da chave no Redis
_WINDOW_SECS = 8        # janela de debounce


class MessageBuffer:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        # phone → asyncio.Task do timer ativo
        self._timers: dict[str, asyncio.Task] = {}

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def add_message(self, phone: str, message: dict) -> None:
        """
        Armazena a mensagem no buffer Redis e reinicia o timer de 8s.
        Quando o timer expirar sem novas mensagens, publica o evento.
        """
        r = await self._client()
        key = f"buffer:{phone}"

        await r.rpush(key, json.dumps(message))
        await r.expire(key, _BUFFER_TTL)

        logger.debug(f"[Buffer] mensagem adicionada para {phone}")

        # Cancela timer anterior e cria um novo (debounce)
        self._reset_timer(phone)

    async def get_messages(self, phone: str) -> list[dict]:
        """Retorna e limpa o buffer do phone."""
        r = await self._client()
        key = f"buffer:{phone}"

        raw_items = await r.lrange(key, 0, -1)
        await r.delete(key)

        messages = [json.loads(item) for item in raw_items]
        logger.debug(f"[Buffer] {len(messages)} mensagem(ns) consumida(s) de {phone}")
        return messages

    def set_handler(self, handler: Callable[[str, list[dict]], Awaitable[None]]) -> None:
        """Registra a corrotina que será chamada quando o timer expirar."""
        self._handler = handler

    # ------------------------------------------------------------------
    # Timer de debounce
    # ------------------------------------------------------------------

    def _reset_timer(self, phone: str) -> None:
        existing = self._timers.get(phone)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(self._fire_after_window(phone))
        self._timers[phone] = task

    async def _fire_after_window(self, phone: str) -> None:
        try:
            await asyncio.sleep(_WINDOW_SECS)
        except asyncio.CancelledError:
            return  # timer foi resetado — não processa ainda

        logger.debug(f"[Buffer] janela de {_WINDOW_SECS}s expirada para {phone}")
        messages = await self.get_messages(phone)

        if not messages:
            return

        handler = getattr(self, "_handler", None)
        if handler:
            try:
                await handler(phone, messages)
            except Exception as exc:
                logger.exception(f"[Buffer] Erro no handler de {phone}: {exc}")
        else:
            # Publica no canal Redis como fallback
            r = await self._client()
            await r.publish(
                f"new_message:{phone}",
                json.dumps({"phone": phone, "messages": messages}),
            )
            logger.debug(f"[Buffer] evento publicado no canal new_message:{phone}")


message_buffer = MessageBuffer()
