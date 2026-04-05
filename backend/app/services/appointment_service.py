from datetime import datetime

from app.core.exceptions import (
    AppointmentConflictError,
    PatientNotFoundError,
)
from app.core.logging import logger
from app.repositories.appointment_repo import Appointment, appointment_repo
from app.repositories.blocked_date_repo import blocked_date_repo
from app.repositories.patient_repo import patient_repo

DEFAULT_DURATION = 50  # minutos


def _parse_dt(datetime_str: str) -> datetime:
    """Aceita 'YYYY-MM-DD HH:MM' ou ISO 8601."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Formato de data inválido: {datetime_str}")


class AppointmentService:
    async def check_availability(self, datetime_str: str) -> bool:
        """Retorna True se o horário estiver disponível."""
        dt = _parse_dt(datetime_str)

        if await blocked_date_repo.is_blocked(dt.date().isoformat()):
            logger.debug(f"Data bloqueada: {dt.date()}")
            return False

        conflict = await appointment_repo.check_conflict(dt, DEFAULT_DURATION)
        return not conflict

    async def book(
        self,
        patient_phone: str,
        datetime_str: str,
        notes: str | None = None,
        duration_minutes: int = DEFAULT_DURATION,
    ) -> Appointment:
        patient = await patient_repo.get_by_phone(patient_phone)
        if not patient:
            raise PatientNotFoundError(patient_phone)

        dt = _parse_dt(datetime_str)

        if await blocked_date_repo.is_blocked(dt.date().isoformat()):
            raise AppointmentConflictError(datetime_str)

        if await appointment_repo.check_conflict(dt, duration_minutes):
            raise AppointmentConflictError(datetime_str)

        appointment = await appointment_repo.create(
            patient_id=patient["id"],
            datetime=dt.isoformat(),
            duration_minutes=duration_minutes,
            status="scheduled",
            notes=notes,
        )
        logger.info(f"Agendamento criado: {patient_phone} — {datetime_str}")
        return appointment

    async def reschedule(
        self,
        appointment_id: str,
        new_datetime_str: str,
        duration_minutes: int = DEFAULT_DURATION,
    ) -> Appointment:
        appointment = await appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise ValueError(f"Agendamento não encontrado: {appointment_id}")

        new_dt = _parse_dt(new_datetime_str)

        if await blocked_date_repo.is_blocked(new_dt.date().isoformat()):
            raise AppointmentConflictError(new_datetime_str)

        if await appointment_repo.check_conflict(
            new_dt, duration_minutes, exclude_id=appointment_id
        ):
            raise AppointmentConflictError(new_datetime_str)

        updated = await appointment_repo.update(
            appointment_id,
            datetime=new_dt.isoformat(),
            duration_minutes=duration_minutes,
            status="scheduled",
        )
        logger.info(f"Agendamento remarcado: {appointment_id} → {new_datetime_str}")
        return updated

    async def cancel(self, appointment_id: str) -> Appointment:
        appointment = await appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise ValueError(f"Agendamento não encontrado: {appointment_id}")

        updated = await appointment_repo.update(appointment_id, status="cancelled")
        logger.info(f"Agendamento cancelado: {appointment_id}")
        return updated

    async def list_upcoming(self, patient_phone: str) -> list[Appointment]:
        patient = await patient_repo.get_by_phone(patient_phone)
        if not patient:
            raise PatientNotFoundError(patient_phone)

        now_iso = datetime.now().isoformat()
        all_appts = await appointment_repo.list_by_patient(patient["id"])

        return [
            a for a in all_appts
            if a["datetime"] >= now_iso and a["status"] != "cancelled"
        ]


appointment_service = AppointmentService()
