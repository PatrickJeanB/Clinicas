# GET /health
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter

from app.core.dependencies import get_supabase
from app.core.logging import logger
from app.core.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    supabase_ok = await _check_supabase()
    redis_ok = await _check_redis()

    overall = "ok" if supabase_ok and redis_ok else "degraded"

    return {
        "status": overall,
        "supabase": "ok" if supabase_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _check_supabase() -> bool:
    try:
        client = await get_supabase()
        # Consulta leve: busca 1 linha de qualquer tabela
        await client.table("patients").select("id").limit(1).execute()
        return True
    except Exception as exc:
        logger.warning(f"[Health] Supabase indisponível: {exc}")
        return False


async def _check_redis() -> bool:
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return True
    except Exception as exc:
        logger.warning(f"[Health] Redis indisponível: {exc}")
        return False
