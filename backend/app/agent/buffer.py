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
        # (clinic_id, phone) → asyncio.Task do timer ativo
        self._timers: dict[tuple[str, str], asyncio.Task] = {}

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

    async def add_message(self, phone: str, message: dict, clinic_id: str) -> None:
        """
        Armazena a mensagem no buffer Redis e reinicia o timer de 8s.
        Quando o timer expirar sem novas mensagens, dispara o handler.
        """
        r = await self._client()
        key = f"buffer:{clinic_id}:{phone}"

        await r.rpush(key, json.dumps(message))
        await r.expire(key, _BUFFER_TTL)

        logger.debug(f"[Buffer] mensagem adicionada para {phone} clinic={clinic_id}")

        self._reset_timer(phone, clinic_id)

    async def get_messages(self, phone: str, clinic_id: str) -> list[dict]:
        """Retorna e limpa o buffer do phone na clínica."""
        r = await self._client()
        key = f"buffer:{clinic_id}:{phone}"

        raw_items = await r.lrange(key, 0, -1)
        await r.delete(key)

        messages = [json.loads(item) for item in raw_items]
        logger.debug(f"[Buffer] {len(messages)} mensagem(ns) consumida(s) de {phone} clinic={clinic_id}")
        return messages

    def set_handler(self, handler: Callable[[str, list[dict], str], Awaitable[None]]) -> None:
        """Registra a corrotina chamada quando o timer expira.
        Assinatura esperada: handler(phone, messages, clinic_id)
        """
        self._handler = handler

    # ------------------------------------------------------------------
    # Timer de debounce
    # ------------------------------------------------------------------

    def _reset_timer(self, phone: str, clinic_id: str) -> None:
        key = (clinic_id, phone)
        existing = self._timers.get(key)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(self._fire_after_window(phone, clinic_id))
        self._timers[key] = task

    async def _fire_after_window(self, phone: str, clinic_id: str) -> None:
        key = (clinic_id, phone)
        current = asyncio.current_task()
        try:
            await asyncio.sleep(_WINDOW_SECS)
        except asyncio.CancelledError:
            return  # timer foi resetado — não processa ainda
        finally:
            # Só remove se esta task ainda é a entrada vigente no dict.
            # Se _reset_timer já colocou uma task nova, não toca.
            if self._timers.get(key) is current:
                self._timers.pop(key, None)

        logger.debug(f"[Buffer] janela de {_WINDOW_SECS}s expirada para {phone} clinic={clinic_id}")
        messages = await self.get_messages(phone, clinic_id)

        if not messages:
            return

        handler = getattr(self, "_handler", None)
        if handler:
            try:
                await handler(phone, messages, clinic_id)
            except Exception as exc:
                logger.exception(f"[Buffer] Erro no handler de {phone} clinic={clinic_id}: {exc}")
        else:
            r = await self._client()
            await r.publish(
                f"new_message:{clinic_id}:{phone}",
                json.dumps({"phone": phone, "clinic_id": clinic_id, "messages": messages}),
            )
            logger.debug(f"[Buffer] evento publicado no canal new_message:{clinic_id}:{phone}")


message_buffer = MessageBuffer()
