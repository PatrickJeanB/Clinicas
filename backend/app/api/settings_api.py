from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth_middleware import get_current_clinic_id
from app.core.encryption import encrypt
from app.core.logging import logger
from app.core.schemas import ClinicSettingsResponse
from app.gateway.whatsapp_factory import whatsapp_factory
from app.repositories.clinic_settings_repo import clinic_settings_repo

router = APIRouter(prefix="/settings", tags=["settings"])


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

_MAX_STR = 200  # limite de tamanho para strings de entrada


class IdentityUpdate(BaseModel):
    ai_name:             str | None = Field(None, max_length=_MAX_STR)
    ai_personality:      str | None = Field(None, max_length=500)
    clinic_display_name: str | None = Field(None, max_length=_MAX_STR)
    doctor_name:         str | None = Field(None, max_length=_MAX_STR)
    doctor_phone:        str | None = Field(None, max_length=30)

    def model_post_init(self, __context: object) -> None:
        # Sanitiza whitespace em todas as strings
        for field in ("ai_name", "ai_personality", "clinic_display_name", "doctor_name", "doctor_phone"):
            val = getattr(self, field)
            if val is not None:
                setattr(self, field, val.strip())


class WhatsAppUpdate(BaseModel):
    whatsapp_phone_id:     str = Field(..., max_length=50)
    whatsapp_token:        str = Field(..., min_length=10, max_length=500)
    whatsapp_app_secret:   str = Field(..., min_length=10, max_length=500)
    whatsapp_verify_token: str = Field(..., min_length=4, max_length=200)


class ScheduleUpdate(BaseModel):
    working_days:         list[str] | None = None
    working_start:        str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    working_end:          str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    appointment_duration: int | None = Field(None, ge=15, le=240)
    timezone:             str | None = Field(None, max_length=50)


# ------------------------------------------------------------------
# GET /settings
# ------------------------------------------------------------------

@router.get("", response_model=ClinicSettingsResponse)
async def get_settings(clinic_id: str = Depends(get_current_clinic_id)) -> ClinicSettingsResponse:
    """
    Retorna configurações da clínica autenticada.
    Campos sensíveis (token, app_secret, gcal_credentials) nunca são retornados.
    """
    cfg = await clinic_settings_repo.get(clinic_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")

    return ClinicSettingsResponse.from_db(cfg)


# ------------------------------------------------------------------
# PUT /settings/identity
# ------------------------------------------------------------------

@router.put("/identity")
async def update_identity(
    body: IdentityUpdate,
    clinic_id: str = Depends(get_current_clinic_id),
) -> dict:
    """Atualiza nome do agente, personalidade e dados do médico."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    cfg = await clinic_settings_repo.update(clinic_id, **updates)
    logger.info(f"[Settings] identity atualizado: clinic_id={clinic_id} campos={list(updates)}")
    return {"message": "Configurações de identidade atualizadas", "updated": list(updates)}


# ------------------------------------------------------------------
# PUT /settings/whatsapp
# ------------------------------------------------------------------

@router.put("/whatsapp")
async def update_whatsapp(
    body: WhatsAppUpdate,
    clinic_id: str = Depends(get_current_clinic_id),
) -> dict:
    """
    Atualiza credenciais WhatsApp.
    Token e app_secret são criptografados com Fernet antes de salvar.
    O cache do WhatsAppFactory é invalidado para forçar reconexão.
    """
    try:
        encrypted_token      = encrypt(body.whatsapp_token)
        encrypted_app_secret = encrypt(body.whatsapp_app_secret)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao criptografar credenciais: {exc}")

    await clinic_settings_repo.update(
        clinic_id,
        whatsapp_phone_id     = body.whatsapp_phone_id,
        whatsapp_token        = encrypted_token,
        whatsapp_app_secret   = encrypted_app_secret,
        whatsapp_verify_token = body.whatsapp_verify_token,
        whatsapp_configured   = True,
    )

    # Invalida cache para que a próxima mensagem use as novas credenciais
    whatsapp_factory.invalidate(clinic_id)

    logger.info(f"[Settings] WhatsApp atualizado: clinic_id={clinic_id} phone_id={body.whatsapp_phone_id}")
    return {"message": "Credenciais WhatsApp atualizadas e criptografadas"}


# ------------------------------------------------------------------
# PUT /settings/schedule
# ------------------------------------------------------------------

@router.put("/schedule")
async def update_schedule(
    body: ScheduleUpdate,
    clinic_id: str = Depends(get_current_clinic_id),
) -> dict:
    """Atualiza configurações de agenda."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar")

    await clinic_settings_repo.update(clinic_id, **updates)
    logger.info(f"[Settings] schedule atualizado: clinic_id={clinic_id} campos={list(updates)}")
    return {"message": "Configurações de agenda atualizadas", "updated": list(updates)}
