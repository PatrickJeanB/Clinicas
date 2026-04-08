from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from gotrue import User

from app.core.dependencies import get_supabase
from app.core.logging import logger

_bearer = HTTPBearer()


async def _validate_token(token: str) -> User:
    """Valida o Bearer token contra o Supabase e retorna o User autenticado."""
    client = await get_supabase()
    try:
        response = await client.auth.get_user(token)
        user = response.user
    except Exception as exc:
        logger.warning(f"[Auth] Falha ao validar token: {exc}")
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    return user


async def get_current_clinic_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """
    Dependency FastAPI — extrai e valida o Bearer token, retorna clinic_id.

    Uso nos endpoints:
        clinic_id: str = Depends(get_current_clinic_id)
    """
    user = await _validate_token(credentials.credentials)

    clinic_id = (user.app_metadata or {}).get("clinic_id")
    if not clinic_id:
        raise HTTPException(
            status_code=403,
            detail="Usuário não vinculado a nenhuma clínica",
        )

    return clinic_id


async def get_current_user_and_clinic(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Dependency que retorna { user, clinic_id } — usado em /auth/me.
    """
    user = await _validate_token(credentials.credentials)
    clinic_id = (user.app_metadata or {}).get("clinic_id")
    return {"user": user, "clinic_id": clinic_id}
