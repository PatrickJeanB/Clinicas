from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase


class Message(TypedDict):
    id: str
    patient_id: str
    direction: str          # "inbound" | "outbound"
    content: str
    message_type: str       # "text" | "audio" | "image" | "document"
    whatsapp_message_id: str | None
    created_at: str


class MessageRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def save(
        self,
        patient_id: str,
        direction: str,
        content: str,
        message_type: str = "text",
        whatsapp_message_id: str | None = None,
    ) -> Message:
        client = await self._client()
        response = (
            await client.table("messages")
            .insert(
                {
                    "patient_id": patient_id,
                    "direction": direction,
                    "content": content,
                    "message_type": message_type,
                    "whatsapp_message_id": whatsapp_message_id,
                }
            )
            .execute()
        )
        return response.data[0]

    async def list_recent(self, patient_id: str, limit: int = 10) -> list[Message]:
        client = await self._client()
        response = (
            await client.table("messages")
            .select("*")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Retorna em ordem cronológica (mais antiga primeiro)
        return list(reversed(response.data))


message_repo = MessageRepo()
