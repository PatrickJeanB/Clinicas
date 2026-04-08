from datetime import datetime, timedelta
from typing import TypedDict

from supabase._async.client import AsyncClient

from app.core.dependencies import get_supabase
from app.core.exceptions import AppointmentConflictError


class Appointment(TypedDict):
    id: str
    clinic_id: str
    patient_id: str
    datetime: str
    duration_minutes: int
    status: str
    notes: str | None
    google_event_id: str | None
    is_recurring: bool
    recurrence_rule: str | None
    created_at: str
    updated_at: str


class AppointmentRepo:
    async def _client(self) -> AsyncClient:
        return await get_supabase()

    async def get_by_id(self, id: str, clinic_id: str) -> Appointment | None:
        client = await self._client()
        response = (
            await client.table("appointments")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("id", id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def list_by_patient(self, patient_id: str, clinic_id: str) -> list[Appointment]:
        client = await self._client()
        response = (
            await client.table("appointments")
            .select("*")
            .eq("clinic_id", clinic_id)
            .eq("patient_id", patient_id)
            .order("datetime", desc=True)
            .execute()
        )
        return response.data

    async def list_by_date(self, date: str, clinic_id: str) -> list[Appointment]:
        """date: formato YYYY-MM-DD"""
        client = await self._client()
        next_day = (datetime.fromisoformat(date) + timedelta(days=1)).date().isoformat()
        response = (
            await client.table("appointments")
            .select("*")
            .eq("clinic_id", clinic_id)
            .gte("datetime", date)
            .lt("datetime", next_day)
            .order("datetime")
            .execute()
        )
        return response.data

    async def create(self, clinic_id: str, **kwargs) -> Appointment:
        client = await self._client()
        response = (
            await client.table("appointments")
            .insert({"clinic_id": clinic_id, **kwargs})
            .execute()
        )
        return response.data[0]

    async def update(self, id: str, clinic_id: str, **kwargs) -> Appointment:
        client = await self._client()
        response = (
            await client.table("appointments")
            .update(kwargs)
            .eq("clinic_id", clinic_id)
            .eq("id", id)
            .execute()
        )
        return response.data[0]

    async def check_conflict(
        self, dt: datetime, clinic_id: str, duration_minutes: int = 50, exclude_id: str | None = None
    ) -> bool:
        """Retorna True se o slot estiver ocupado na clínica."""
        client = await self._client()
        date_str = dt.date().isoformat()
        next_day = (dt.date() + timedelta(days=1)).isoformat()

        query = (
            client.table("appointments")
            .select("datetime, duration_minutes")
            .eq("clinic_id", clinic_id)
            .gte("datetime", date_str)
            .lt("datetime", next_day)
            .neq("status", "cancelled")
        )
        if exclude_id:
            query = query.neq("id", exclude_id)

        response = await query.execute()

        new_start = dt
        new_end = dt + timedelta(minutes=duration_minutes)

        for appt in response.data:
            existing_start = datetime.fromisoformat(appt["datetime"])
            existing_end = existing_start + timedelta(minutes=appt["duration_minutes"])
            if new_start < existing_end and new_end > existing_start:
                return True
        return False


appointment_repo = AppointmentRepo()
