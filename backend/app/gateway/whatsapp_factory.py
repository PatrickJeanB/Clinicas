# Factory de WhatsAppGateway com cache por clinic_id
from app.core.encryption import decrypt
from app.core.logging import logger
from app.gateway.whatsapp import WhatsAppGateway
from app.repositories.clinic_settings_repo import clinic_settings_repo


class WhatsAppClientFactory:
    def __init__(self) -> None:
        self._cache: dict[str, WhatsAppGateway] = {}

    async def get_client(self, clinic_id: str) -> WhatsAppGateway:
        """
        Retorna um WhatsAppGateway para a clínica.
        Cria e cacheia na primeira chamada; reutiliza nas seguintes.
        """
        if clinic_id in self._cache:
            return self._cache[clinic_id]

        creds = await clinic_settings_repo.get_whatsapp_credentials(clinic_id)
        if not creds or not creds.get("token") or not creds.get("phone_id"):
            raise ValueError(f"Credenciais WhatsApp não configuradas para clinic_id={clinic_id}")

        raw_token = creds["token"]
        try:
            token = decrypt(raw_token)
        except Exception:
            token = raw_token  # token em texto puro (ambiente de desenvolvimento)

        phone_id = creds["phone_id"]  # phone_id não é criptografado

        gateway = WhatsAppGateway(token=token, phone_id=phone_id)
        self._cache[clinic_id] = gateway

        logger.info(f"[WhatsAppFactory] cliente criado para clinic_id={clinic_id} phone_id={phone_id}")
        return gateway

    def invalidate(self, clinic_id: str) -> None:
        """Remove a instância do cache (chamar ao trocar credenciais)."""
        removed = self._cache.pop(clinic_id, None)
        if removed:
            logger.info(f"[WhatsAppFactory] cache invalidado para clinic_id={clinic_id}")


whatsapp_factory = WhatsAppClientFactory()
