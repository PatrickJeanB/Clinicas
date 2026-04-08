from app.core.exceptions import PatientNotFoundError
from app.core.logging import logger
from app.repositories.patient_repo import Patient, patient_repo


class PatientService:
    async def get_or_create(self, phone: str, name: str, clinic_id: str) -> tuple[Patient, bool]:
        """
        Retorna (patient, created).
        Se o paciente já existe na clínica, retorna sem alterar o nome.
        """
        existing = await patient_repo.get_by_phone(phone, clinic_id)
        if existing:
            logger.debug(f"Paciente encontrado: {phone} clinic={clinic_id}")
            return existing, False

        patient = await patient_repo.create(name=name, phone=phone, clinic_id=clinic_id)
        logger.info(f"Novo paciente criado: {phone} — {name} clinic={clinic_id}")
        return patient, True

    async def update_profile(self, phone: str, clinic_id: str, **kwargs) -> Patient:
        patient = await patient_repo.get_by_phone(phone, clinic_id)
        if not patient:
            raise PatientNotFoundError(phone)
        updated = await patient_repo.update(patient["id"], clinic_id, **kwargs)
        logger.info(f"Perfil atualizado: {phone} clinic={clinic_id}")
        return updated

    async def get_profile(self, phone: str, clinic_id: str) -> Patient:
        patient = await patient_repo.get_by_phone(phone, clinic_id)
        if not patient:
            raise PatientNotFoundError(phone)
        return patient


patient_service = PatientService()
