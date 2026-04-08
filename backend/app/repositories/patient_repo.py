from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase
from app.core.exceptions import PatientNotFoundError


class Patient(TypedDict):
    id: str
    clinic_id: str
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

    async def get_by_phone(self, phone: str, clinic_id: str) -> Patient | None:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_id(self, id: str, clinic_id: str) -> Patient | None:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("id", id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def create(self, name: str, phone: str, clinic_id: str, email: str | None = None) -> Patient:
        client = await self._client()
        response = (
            await client.table("patients")
            .insert({"clinic_id": clinic_id, "name": name, "phone": phone, "email": email, "is_active": True})
            .execute()
        )
        return response.data[0]

    async def update(self, id: str, clinic_id: str, **kwargs) -> Patient:
        client = await self._client()
        response = (
            await client.table("patients")
            .update(kwargs)
            .eq("clinic_id", clinic_id)
            .eq("id", id)
            .execute()
        )
        if not response.data:
            raise PatientNotFoundError(id)
        return response.data[0]

    async def list_active(self, clinic_id: str, limit: int = 100) -> list[Patient]:
        client = await self._client()
        response = (
            await client.table("patients")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("is_active", True)
            .order("name")
            .limit(limit)
            .execute()
        )
        return response.data


patient_repo = PatientRepo()
