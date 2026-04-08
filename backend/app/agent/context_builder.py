# Monta contexto por mensagem
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.logging import logger
from app.repositories.message_repo import message_repo
from app.repositories.patient_repo import patient_repo
from app.services.appointment_service import appointment_service

_BR_TZ = ZoneInfo("America/Sao_Paulo")


class ContextBuilder:
    async def build(self, phone: str, clinic_id: str) -> dict:
        """
        Constrói o contexto completo para uma conversa.

        Retorna:
        {
            "patient": Patient | None,
            "recent_messages": list[Message],
            "upcoming_appointments": list[Appointment],
            "current_datetime": str,   # ISO 8601 com timezone Brasil
        }
        """
        patient, recent_messages, upcoming = await self._fetch_all(phone, clinic_id)

        context = {
            "patient": patient,
            "recent_messages": recent_messages,
            "upcoming_appointments": upcoming,
            "current_datetime": datetime.now(_BR_TZ).isoformat(),
        }

        logger.debug(
            f"[Context] phone={phone} clinic={clinic_id} "
            f"patient={'sim' if patient else 'novo'} "
            f"msgs={len(recent_messages)} "
            f"consultas={len(upcoming)}"
        )
        return context

    async def _fetch_all(self, phone: str, clinic_id: str) -> tuple:
        patient = await patient_repo.get_by_phone(phone, clinic_id)

        if patient is None:
            return None, [], []

        # Busca histórico e consultas em paralelo
        recent_messages, upcoming = await asyncio.gather(
            message_repo.list_recent(patient["id"], clinic_id, limit=10),
            _safe_upcoming(phone, clinic_id),
        )
        return patient, recent_messages, upcoming


async def _safe_upcoming(phone: str, clinic_id: str) -> list:
    try:
        return await appointment_service.list_upcoming(phone, clinic_id)
    except Exception as exc:
        logger.warning(f"[Context] falha ao buscar consultas futuras para {phone} clinic={clinic_id}: {exc}")
        return []


context_builder = ContextBuilder()
