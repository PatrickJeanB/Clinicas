from fastapi import Header, HTTPException

from app.core.settings import settings


async def get_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> None:
    """
    Dependency que valida o header X-Admin-Key em todos os endpoints admin.
    Retorna 403 se a chave for inválida ou ausente.
    """
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Chave admin inválida")
