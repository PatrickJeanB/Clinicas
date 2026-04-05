from app.core.exceptions import PatientNotFoundError
from app.core.logging import logger
from app.repositories.patient_repo import Patient, patient_repo


class PatientService:
    async def get_or_create(self, phone: str, name: str) -> tuple[Patient, bool]:
        """
        Retorna (patient, created).
        Se o paciente já existe, retorna sem alterar o nome.
        """
        existing = await patient_repo.get_by_phone(phone)
        if existing:
            logger.debug(f"Paciente encontrado: {phone}")
            return existing, False

        patient = await patient_repo.create(name=name, phone=phone)
        logger.info(f"Novo paciente criado: {phone} — {name}")
        return patient, True

    async def update_profile(self, phone: str, **kwargs) -> Patient:
        patient = await patient_repo.get_by_phone(phone)
        if not patient:
            raise PatientNotFoundError(phone)
        updated = await patient_repo.update(patient["id"], **kwargs)
        logger.info(f"Perfil atualizado: {phone}")
        return updated

    async def get_profile(self, phone: str) -> Patient:
        patient = await patient_repo.get_by_phone(phone)
        if not patient:
            raise PatientNotFoundError(phone)
        return patient


patient_service = PatientService()
