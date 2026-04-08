# FastAPI Depends() centralizados
import redis.asyncio as aioredis
from supabase._async.client import AsyncClient
from supabase._async.client import create_client as acreate_client

from app.core.logging import logger
from app.core.settings import settings

# ── Supabase ──────────────────────────────────────────────────────────
_supabase: AsyncClient | None = None


async def init_supabase() -> None:
    """Inicializa o cliente Supabase. Chamado no lifespan do app."""
    global _supabase
    _supabase = await acreate_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    logger.info("[Dependencies] Supabase client inicializado")


async def get_supabase() -> AsyncClient:
    """Retorna o cliente Supabase async (singleton)."""
    if _supabase is None:
        # Fallback para testes e scripts que não usam lifespan
        await init_supabase()
    return _supabase  # type: ignore[return-value]


# ── Redis ──────────────────────────────────────────────────────────────
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Retorna o cliente Redis async (singleton)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


# ── Clinic Agent ───────────────────────────────────────────────────────
def get_clinic_agent():
    """
    Retorna o singleton ClinicAgent.
    Import lazy obrigatório: agent → repos → dependencies (evita ciclo).
    """
    from app.agent.agent import clinic_agent  # noqa: PLC0415
    return clinic_agent
