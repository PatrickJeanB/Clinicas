"""
Schemas Pydantic de resposta — garantem que nenhum campo sensível
vaze para o frontend. Toda resposta de endpoint autenticado usa estes modelos.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Configurações da clínica ───────────────────────────────────────────────

class WhatsAppStatusResponse(BaseModel):
    """Indica se o WhatsApp está configurado — nunca expõe o token."""
    configured: bool
    phone_id: str | None = None
    token_set: bool = False  # True = token existe no banco, mas nunca retornado


class ScheduleResponse(BaseModel):
    working_days: list[str]
    working_start: str
    working_end: str
    appointment_duration: int
    timezone: str


class ClinicSettingsResponse(BaseModel):
    """
    Resposta segura de GET /settings.
    Campos sensíveis (token, app_secret, gcal_credentials) nunca aparecem aqui.
    """
    clinic_id: str
    ai_name: str | None = None
    ai_personality: str | None = None
    clinic_display_name: str | None = None
    doctor_name: str | None = None
    doctor_phone: str | None = None
    whatsapp: WhatsAppStatusResponse
    gcal_configured: bool = False
    schedule: ScheduleResponse
    test_mode: bool = False
    debug_mode: bool = False
    updated_at: str | None = None

    @classmethod
    def from_db(cls, row: dict) -> "ClinicSettingsResponse":
        """Constrói a resposta a partir de um row bruto do banco."""
        return cls(
            clinic_id=row["clinic_id"],
            ai_name=row.get("ai_name"),
            ai_personality=row.get("ai_personality"),
            clinic_display_name=row.get("clinic_display_name"),
            doctor_name=row.get("doctor_name"),
            doctor_phone=row.get("doctor_phone"),
            whatsapp=WhatsAppStatusResponse(
                configured=bool(row.get("whatsapp_configured")),
                phone_id=row.get("whatsapp_phone_id"),
                token_set=bool(row.get("whatsapp_token")),
            ),
            gcal_configured=bool(row.get("gcal_configured")),
            schedule=ScheduleResponse(
                working_days=row.get("working_days") or [],
                working_start=row.get("working_start") or "08:00",
                working_end=row.get("working_end") or "18:00",
                appointment_duration=row.get("appointment_duration") or 50,
                timezone=row.get("timezone") or "America/Sao_Paulo",
            ),
            test_mode=bool(row.get("test_mode")),
            debug_mode=bool(row.get("debug_mode")),
            updated_at=row.get("updated_at"),
        )


# ── Usuário autenticado ────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    email: str
    role: str | None = None


class ClinicBriefResponse(BaseModel):
    id: str
    name: str
    plan: str | None = None


class UserMeResponse(BaseModel):
    """
    Resposta segura de GET /auth/me.
    Nunca expõe tokens, hashes de senha ou dados internos do Supabase.
    """
    user: UserResponse
    clinic: ClinicBriefResponse | None = None


# ── Erros ─────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Formato padronizado de erro — sem stack traces."""
    error: str
    message: str = Field(..., description="Mensagem segura para exibição ao usuário")
