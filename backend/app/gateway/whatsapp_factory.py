# Factory de WhatsAppGateway com cache por clinic_id
from app.core.encryption import decrypt
from app.core.exceptions import WhatsAppError
from app.core.logging import logger
from app.gateway.whatsapp import WhatsAppGateway
from app.repositories.clinic_settings_repo import clinic_settings_repo

_UNAUTHORIZED_MARKER = "HTTP 401"


class WhatsAppClientFactory:
    def __init__(self) -> None:
        self._cache: dict[str, WhatsAppGateway] = {}

    async def get_client(self, clinic_id: str) -> WhatsAppGateway:
        """
        Retorna um WhatsAppGateway para a clínica.
        Token e phone_id vêm exclusivamente do banco (clinic_settings).
        Cria e cacheia na primeira chamada; reutiliza nas seguintes.
        """
        if clinic_id in self._cache:
            return self._cache[clinic_id]

        return await self._build_client(clinic_id)

    async def send_text_safe(self, clinic_id: str, to: str, message: str) -> bool:
        """
        Envia texto com auto-recuperação em caso de token expirado (401).
        Na primeira falha 401, invalida o cache e tenta com credenciais frescas.
        """
        client = await self.get_client(clinic_id)
        try:
            return await client.send_text(to, message)
        except WhatsAppError as exc:
            if _UNAUTHORIZED_MARKER in str(exc):
                logger.warning(
                    f"[WhatsAppFactory] 401 para clinic_id={clinic_id} — "
                    "invalidando cache e tentando com credenciais frescas"
                )
                self.invalidate(clinic_id)
                fresh_client = await self._build_client(clinic_id)
                return await fresh_client.send_text(to, message)
            raise

    async def _build_client(self, clinic_id: str) -> WhatsAppGateway:
        creds = await clinic_settings_repo.get_whatsapp_credentials(clinic_id)
        if not creds or not creds.get("token") or not creds.get("phone_id"):
            raise ValueError(f"Credenciais WhatsApp não configuradas para clinic_id={clinic_id}")

        try:
            token = decrypt(creds["token"])
        except Exception as exc:
            raise ValueError(
                f"Falha ao descriptografar whatsapp_token para clinic_id={clinic_id}"
            ) from exc

        phone_id = creds["phone_id"]
        gateway = WhatsAppGateway(token=token, phone_id=phone_id)
        self._cache[clinic_id] = gateway
        logger.info(f"[WhatsAppFactory] cliente criado para clinic_id={clinic_id} phone_id={phone_id}")
        return gateway

    def invalidate(self, clinic_id: str) -> None:
        """Remove a instância do cache (chamar ao trocar credenciais via PUT /settings/whatsapp)."""
        removed = self._cache.pop(clinic_id, None)
        if removed:
            logger.info(f"[WhatsAppFactory] cache invalidado para clinic_id={clinic_id}")


whatsapp_factory = WhatsAppClientFactory()
