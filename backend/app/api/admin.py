import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.admin_auth import get_admin
from app.core.dependencies import get_supabase
from app.core.logging import logger

router = APIRouter(dependencies=[Depends(get_admin)])

# Colunas de clinic_settings seguras para expor (exclui tokens, secrets e verify_token)
_SAFE_SETTINGS = (
    "ai_name,ai_personality,clinic_display_name,doctor_name,doctor_phone,"
    "whatsapp_phone_id,whatsapp_configured,gcal_calendar_id,gcal_configured,"
    "working_days,working_start,working_end,appointment_duration,"
    "briefing_hour,confirmation_hour,timezone,test_mode,debug_mode,updated_at"
)


# ── Request bodies ─────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: Literal["active", "suspended", "cancelled"]


class PlanUpdate(BaseModel):
    plan: Literal["trial", "starter", "pro", "enterprise"]


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_clinic_or_404(clinic_id: str) -> dict:
    client = await get_supabase()
    response = (
        await client.table("clinics")
        .select("*")
        .eq("id", clinic_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Clínica não encontrada")
    return response.data[0]


# ── GET /admin/clinics ─────────────────────────────────────────────────────

@router.get("/clinics")
async def list_clinics(
    status: str | None = Query(None, description="Filtrar: active | suspended | cancelled"),
    plan: str | None = Query(None, description="Filtrar: trial | starter | pro | enterprise"),
) -> list[dict]:
    """Lista todas as clínicas com suporte a filtros por status e plano."""
    client = await get_supabase()
    query = (
        client.table("clinics")
        .select(
            "id,name,slug,plan,status,trial_ends_at,created_at,"
            "clinic_settings(whatsapp_configured)"
        )
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    if plan:
        query = query.eq("plan", plan)

    response = await query.execute()

    result = []
    for clinic in response.data:
        cs = clinic.pop("clinic_settings", None)
        # Supabase retorna relação 1:1 como dict; protege contra list
        if isinstance(cs, list):
            cs = cs[0] if cs else None
        clinic["whatsapp_configured"] = (cs or {}).get("whatsapp_configured", False)
        result.append(clinic)

    logger.info(f"[Admin] list_clinics — {len(result)} clínicas (status={status} plan={plan})")
    return result


# ── GET /admin/clinics/{clinic_id} ─────────────────────────────────────────

@router.get("/clinics/{clinic_id}")
async def get_clinic(clinic_id: str) -> dict:
    """Detalhes completos de uma clínica: dados, settings, contagens."""
    client = await get_supabase()

    async def _fetch_clinic() -> dict | None:
        r = (
            await client.table("clinics")
            .select("*")
            .eq("id", clinic_id)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    async def _fetch_settings() -> dict | None:
        r = (
            await client.table("clinic_settings")
            .select(_SAFE_SETTINGS)
            .eq("clinic_id", clinic_id)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    async def _count_patients() -> int:
        r = (
            await client.table("patients")
            .select("id", count="exact")
            .eq("clinic_id", clinic_id)
            .execute()
        )
        return r.count or 0

    async def _count_appointments() -> int:
        r = (
            await client.table("appointments")
            .select("id", count="exact")
            .eq("clinic_id", clinic_id)
            .execute()
        )
        return r.count or 0

    clinic, settings_data, patient_count, appointment_count = await asyncio.gather(
        _fetch_clinic(),
        _fetch_settings(),
        _count_patients(),
        _count_appointments(),
    )

    if clinic is None:
        raise HTTPException(status_code=404, detail="Clínica não encontrada")

    logger.info(f"[Admin] get_clinic — clinic_id={clinic_id}")
    return {
        **clinic,
        "settings": settings_data,
        "patient_count": patient_count,
        "appointment_count": appointment_count,
    }


# ── PATCH /admin/clinics/{clinic_id}/status ────────────────────────────────

@router.patch("/clinics/{clinic_id}/status")
async def update_clinic_status(clinic_id: str, body: StatusUpdate) -> dict:
    """Atualiza o status de uma clínica (active | suspended | cancelled)."""
    await _get_clinic_or_404(clinic_id)
    client = await get_supabase()
    response = (
        await client.table("clinics")
        .update({"status": body.status})
        .eq("id", clinic_id)
        .execute()
    )
    logger.info(f"[Admin] update_status — clinic_id={clinic_id} → status={body.status}")
    return response.data[0]


# ── PATCH /admin/clinics/{clinic_id}/plan ──────────────────────────────────

@router.patch("/clinics/{clinic_id}/plan")
async def update_clinic_plan(clinic_id: str, body: PlanUpdate) -> dict:
    """Atualiza o plano de uma clínica (trial | starter | pro | enterprise)."""
    await _get_clinic_or_404(clinic_id)
    client = await get_supabase()
    response = (
        await client.table("clinics")
        .update({"plan": body.plan})
        .eq("id", clinic_id)
        .execute()
    )
    logger.info(f"[Admin] update_plan — clinic_id={clinic_id} → plan={body.plan}")
    return response.data[0]


# ── DELETE /admin/clinics/{clinic_id} ─────────────────────────────────────

@router.delete("/clinics/{clinic_id}")
async def soft_delete_clinic(clinic_id: str) -> dict:
    """Soft delete: marca a clínica como cancelled. Nunca apaga dados físicos."""
    await _get_clinic_or_404(clinic_id)
    client = await get_supabase()
    await (
        client.table("clinics")
        .update({"status": "cancelled"})
        .eq("id", clinic_id)
        .execute()
    )
    logger.info(f"[Admin] soft_delete — clinic_id={clinic_id} marcada como cancelled")
    return {"message": "Clínica desativada com sucesso", "clinic_id": clinic_id}


# ── GET /admin/metrics ─────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics() -> dict:
    """Métricas gerais do SaaS: clínicas por status/plano, crescimento, totais."""
    client = await get_supabase()
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    async def _count(table: str, field: str | None = None, value: str | None = None, since: str | None = None) -> int:
        query = client.table(table).select("id", count="exact")
        if field and value:
            query = query.eq(field, value)
        if since:
            query = query.gte("created_at", since)
        r = await query.execute()
        return r.count or 0

    (
        active, suspended, cancelled,
        trial, starter, pro, enterprise,
        new_clinics,
        total_patients,
        total_appointments,
    ) = await asyncio.gather(
        _count("clinics", "status", "active"),
        _count("clinics", "status", "suspended"),
        _count("clinics", "status", "cancelled"),
        _count("clinics", "plan", "trial"),
        _count("clinics", "plan", "starter"),
        _count("clinics", "plan", "pro"),
        _count("clinics", "plan", "enterprise"),
        _count("clinics", since=cutoff_30d),
        _count("patients"),
        _count("appointments"),
    )

    logger.info("[Admin] get_metrics — consulta executada")
    return {
        "total_clinics_by_status": {
            "active": active,
            "suspended": suspended,
            "cancelled": cancelled,
        },
        "total_clinics_by_plan": {
            "trial": trial,
            "starter": starter,
            "pro": pro,
            "enterprise": enterprise,
        },
        "clinics_created_last_30_days": new_clinics,
        "total_patients": total_patients,
        "total_appointments": total_appointments,
    }
