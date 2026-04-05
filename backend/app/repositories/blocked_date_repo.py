from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase


class BlockedDate(TypedDict):
    id: str
    date: str           # formato YYYY-MM-DD
    reason: str | None
    created_at: str


class BlockedDateRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def is_blocked(self, date: str) -> bool:
        """date: formato YYYY-MM-DD"""
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .select("id")
            .eq("date", date)
            .limit(1)
            .execute()
        )
        return len(response.data) > 0

    async def list_all(self) -> list[BlockedDate]:
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .select("*")
            .order("date")
            .execute()
        )
        return response.data

    async def add(self, date: str, reason: str | None = None) -> BlockedDate:
        """date: formato YYYY-MM-DD"""
        client = await self._client()
        response = (
            await client.table("blocked_dates")
            .insert({"date": date, "reason": reason})
            .execute()
        )
        return response.data[0]


blocked_date_repo = BlockedDateRepo()
