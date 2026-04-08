from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth_middleware import get_current_clinic_id
from app.core.encryption import encrypt
from app.core.logging import logger
from app.gateway.whatsapp_factory import whatsapp_factory
from app.repositories.clinic_settings_repo import clinic_settings_repo

router = APIRouter(prefix="/settings", tags=["settings"])


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class IdentityUpdate(BaseModel):
    ai_name:             str | None = None
    ai_personality:      str | None = None
    clinic_display_name: str | None = None
    doctor_name:         str | None = None
    doctor_phone:        str | None = None


class WhatsAppUpdate(BaseModel):
    whatsapp_phone_id:     str
    whatsapp_token:        str
    whatsapp_app_secret:   str
    whatsapp_verify_token: str


class ScheduleUpdate(BaseModel):
    working_days:         list[str] | None = None
    working_start:        str | None = None
    working_end:          str | None = None
    appointment_duration: int | None = None
    timezone:             str | None = None


# ------------------------------------------------------------------
# GET /settings
# ------------------------------------------------------------------

@router.get("")
async def get_settings(clinic_id: str = Depends(get_current_clinic_id)) -> dict:
    """Retorna todas as configurações da clínica autenticada."""
    cfg = await clinic_settings_repo.get(clinic_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Configurações não encontradas")

    # Remove campos sensíveis da resposta
    cfg.pop("whatsapp_token", None)
    cfg.pop("whatsapp_app_secret", None)
    cfg.pop("gcal_credentials", None)
    return cfg


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
