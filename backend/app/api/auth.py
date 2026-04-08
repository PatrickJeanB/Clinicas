from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth_middleware import get_current_user_and_clinic
from app.core.dependencies import get_supabase
from app.core.logging import logger
from app.core.schemas import ClinicBriefResponse, UserMeResponse, UserResponse
from app.repositories.clinic_repo import clinic_repo
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = Limiter(key_func=get_remote_address)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class RegisterRequest(BaseModel):
    clinic_name: str = Field(..., min_length=2, max_length=200)
    doctor_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    def model_post_init(self, __context: object) -> None:
        self.clinic_name = self.clinic_name.strip()
        self.doctor_name = self.doctor_name.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


# ------------------------------------------------------------------
# POST /auth/register
# ------------------------------------------------------------------

@router.post("/register", status_code=201)
@_limiter.limit("10/hour")
async def register(request: Request, body: RegisterRequest) -> dict:
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
@_limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> dict:
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

@router.get("/me", response_model=UserMeResponse)
async def me(ctx: dict = Depends(get_current_user_and_clinic)) -> UserMeResponse:
    """
    Retorna dados do usuário autenticado e da clínica vinculada.
    Nunca retorna tokens, hashes de senha ou metadados internos do Supabase.
    Header: Authorization: Bearer {token}
    """
    user      = ctx["user"]
    clinic_id = ctx["clinic_id"]

    clinic_brief: ClinicBriefResponse | None = None
    if clinic_id:
        clinic_row = await clinic_repo.get_by_id(clinic_id)
        if clinic_row:
            clinic_brief = ClinicBriefResponse(
                id=clinic_row["id"],
                name=clinic_row["name"],
                plan=clinic_row.get("plan"),
            )

    return UserMeResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            role=(user.app_metadata or {}).get("clinic_role"),
        ),
        clinic=clinic_brief,
    )
