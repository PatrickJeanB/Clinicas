from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase


class ClinicRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def get_by_id(self, clinic_id: str) -> dict | None:
        client = await self._client()
        response = (
            await client.table("clinics")
            .select("*")
            .eq("id", clinic_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_slug(self, slug: str) -> dict | None:
        client = await self._client()
        response = (
            await client.table("clinics")
            .select("*")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def list_active(self) -> list[dict]:
        client = await self._client()
        response = (
            await client.table("clinics")
            .select("*")
            .eq("status", "active")
            .order("name")
            .execute()
        )
        return response.data

    async def create(self, name: str, slug: str, plan: str = "trial") -> dict:
        client = await self._client()
        response = (
            await client.table("clinics")
            .insert({"name": name, "slug": slug, "plan": plan})
            .execute()
        )
        return response.data[0]


clinic_repo = ClinicRepo()
