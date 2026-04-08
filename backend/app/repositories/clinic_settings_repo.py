from datetime import datetime, timezone

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase


class ClinicSettingsRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def get(self, clinic_id: str) -> dict | None:
        client = await self._client()
        response = (
            await client.table("clinic_settings")
            .select("*")
            .eq("clinic_id", clinic_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_verify_token(self, verify_token: str) -> dict | None:
        """Localiza settings pelo verify_token (usado na verificação GET do webhook Meta)."""
        client = await self._client()
        response = (
            await client.table("clinic_settings")
            .select("*")
            .eq("whatsapp_verify_token", verify_token)
            .eq("whatsapp_configured", True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_phone_id(self, whatsapp_phone_id: str) -> dict | None:
        """Localiza settings pelo phone_number_id do WhatsApp (usado no roteamento do webhook)."""
        client = await self._client()
        response = (
            await client.table("clinic_settings")
            .select("*")
            .eq("whatsapp_phone_id", whatsapp_phone_id)
            .eq("whatsapp_configured", True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def update(self, clinic_id: str, **kwargs) -> dict:
        client = await self._client()
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        response = (
            await client.table("clinic_settings")
            .update(kwargs)
            .eq("clinic_id", clinic_id)
            .execute()
        )
        return response.data[0]

    async def get_whatsapp_credentials(self, clinic_id: str) -> dict:
        """Retorna credenciais WhatsApp brutas (ainda criptografadas) para descriptografia na factory."""
        settings = await self.get(clinic_id)
        if not settings:
            return {}
        return {
            "token":        settings.get("whatsapp_token"),
            "phone_id":     settings.get("whatsapp_phone_id"),
            "app_secret":   settings.get("whatsapp_app_secret"),
            "verify_token": settings.get("whatsapp_verify_token"),
        }


clinic_settings_repo = ClinicSettingsRepo()
