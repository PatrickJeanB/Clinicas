from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase


class BlockedDate(TypedDict):
    id: str
    clinic_id: str
    date: str           # formato YYYY-MM-DD
    reason: str | None
    created_at: str


class BlockedDateRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def is_blocked(self, date: str, clinic_id: str) -> bool:
        """date: formato YYYY-MM-DD"""
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .select("id")
            .eq("clinic_id", clinic_id)
            .eq("date", date)
            .limit(1)
            .execute()
        )
        return len(response.data) > 0

    async def list_all(self, clinic_id: str, limit: int = 400) -> list[BlockedDate]:
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .select("*")
            .eq("clinic_id", clinic_id)
            .order("date")
            .limit(limit)
            .execute()
        )
        return response.data

    async def add(self, date: str, clinic_id: str, reason: str | None = None) -> BlockedDate:
        """date: formato YYYY-MM-DD"""
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .insert({"clinic_id": clinic_id, "date": date, "reason": reason})
            .execute()
        )
        return response.data[0]


blocked_date_repo = BlockedDateRepo()
