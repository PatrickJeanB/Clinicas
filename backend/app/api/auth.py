from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.auth_middleware import get_current_user_and_clinic
from app.core.dependencies import get_supabase
from app.core.logging import logger
from app.repositories.clinic_repo import clinic_repo
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/auth", tags=["auth"])


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class RegisterRequest(BaseModel):
    clinic_name: str
    doctor_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ------------------------------------------------------------------
# POST /auth/register
# ------------------------------------------------------------------

@router.post("/register", status_code=201)
async def register(body: RegisterRequest) -> dict:
    """
    Cria uma nova clínica e seu usuário owner.
    Retorna clinic_id e user_id para uso imediato.
    """
    try:
        result = await onboarding_service.create_clinic(
            clinic_name=body.clinic_name,
            doctor_name=body.doctor_name,
            email=body.email,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info(f"[Auth] registro concluído: {body.email} → clinic_id={result['clinic_id']}")
    return {
        "clinic_id": result["clinic_id"],
        "user_id":   result["user_id"],
        "message":   "Clínica criada com sucesso. Faça login para obter o token.",
    }


# ------------------------------------------------------------------
# POST /auth/login
# ------------------------------------------------------------------

@router.post("/login")
async def login(body: LoginRequest) -> dict:
    """
    Autentica no Supabase Auth.
    O JWT retornado já contém clinic_id no app_metadata (injetado pelo trigger).
    """
    client = await get_supabase()

    try:
        auth_response = await client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as exc:
        logger.warning(f"[Auth] falha no login: {body.email} — {exc}")
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    session = auth_response.session
    user    = auth_response.user

    if not session or not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    clinic_id = (user.app_metadata or {}).get("clinic_id")
    clinic_name = None

    if clinic_id:
        clinic = await clinic_repo.get_by_id(clinic_id)
        clinic_name = clinic["name"] if clinic else None

    return {
        "access_token": session.access_token,
        "token_type":   "bearer",
        "clinic_id":    clinic_id,
        "clinic_name":  clinic_name,
    }


# ------------------------------------------------------------------
# GET /auth/me
# ------------------------------------------------------------------

@router.get("/me")
async def me(ctx: dict = Depends(get_current_user_and_clinic)) -> dict:
    """
    Retorna dados do usuário autenticado e da clínica vinculada.
    Header: Authorization: Bearer {token}
    """
    user      = ctx["user"]
    clinic_id = ctx["clinic_id"]

    clinic = None
    if clinic_id:
        clinic = await clinic_repo.get_by_id(clinic_id)

    return {
        "user": {
            "id":    str(user.id),
            "email": user.email,
            "role":  (user.app_metadata or {}).get("clinic_role"),
        },
        "clinic": clinic,
    }
