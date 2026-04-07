# FastAPI Depends() centralizados
import redis.asyncio as aioredis
from supabase._async.client import AsyncClient
from supabase._async.client import create_client as acreate_client

from app.core.settings import settings

# ── Supabase ──────────────────────────────────────────────────────────
_supabase: AsyncClient | None = None


async def get_supabase() -> AsyncClient:
    """Retorna o cliente Supabase async (singleton)."""
    global _supabase
    if _supabase is None:
        _supabase = await acreate_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _supabase


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


# ── WhatsApp Gateway ───────────────────────────────────────────────────
def get_whatsapp():
    """Retorna o singleton WhatsAppGateway. Import lazy para evitar ciclo."""
    from app.gateway.whatsapp import whatsapp_gateway  # noqa: PLC0415
    return whatsapp_gateway


# ── Clinic Agent ───────────────────────────────────────────────────────
def get_clinic_agent():
    """
    Retorna o singleton ClinicAgent.
    Import lazy obrigatório: agent → repos → dependencies (evita ciclo).
    """
    from app.agent.agent import clinic_agent  # noqa: PLC0415
    return clinic_agent
