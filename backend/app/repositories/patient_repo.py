from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase
from app.core.exceptions import PatientNotFoundError


class Patient(TypedDict):
    id: str
    name: str
    phone: str
    email: str | None
    notes: str | None
    is_active: bool
    created_at: str
    updated_at: str


class PatientRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def get_by_phone(self, phone: str) -> Patient | None:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    async def get_by_id(self, id: str) -> Patient | None:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("id", id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    async def create(self, name: str, phone: str, email: str | None = None) -> Patient:
        client = await self._client()
        response = (
            await client.table("patients")
            .insert({"name": name, "phone": phone, "email": email, "is_active": True})
            .execute()
        )
        return response.data[0]

    async def update(self, id: str, **kwargs) -> Patient:
        client = await self._client()
        response = (
            await client.table("patients")
            .update(kwargs)
            .eq("id", id)
            .execute()
        )
        if not response.data:
            raise PatientNotFoundError(id)
        return response.data[0]

    async def list_active(self) -> list[Patient]:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return response.data


patient_repo = PatientRepo()
