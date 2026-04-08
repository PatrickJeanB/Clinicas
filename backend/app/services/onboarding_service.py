import re
import unicodedata

from app.core.dependencies import get_supabase
from app.core.logging import logger
from app.repositories.clinic_repo import clinic_repo
from app.repositories.clinic_settings_repo import clinic_settings_repo


class OnboardingService:

    # ------------------------------------------------------------------
    # Slug
    # ------------------------------------------------------------------

    def _slugify(self, name: str) -> str:
        """Remove acentos, lowercase, espaços → hífens."""
        # NFD decompõe em base + combining marks; filtramos os combining
        normalized = unicodedata.normalize("NFD", name)
        ascii_name = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
        return slug or "clinica"

    async def generate_slug(self, name: str) -> str:
        """Gera slug único verificando colisões no banco."""
        base = self._slugify(name)
        candidate = base
        suffix = 2

        while True:
            existing = await clinic_repo.get_by_slug(candidate)
            if not existing:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    # ------------------------------------------------------------------
    # Criação da clínica
    # ------------------------------------------------------------------

    async def create_clinic(
        self,
        clinic_name: str,
        doctor_name: str,
        email: str,
        password: str,
    ) -> dict:
        """
        Fluxo completo de onboarding:
          1. Cria usuário no Supabase Auth (email confirmado, sem verificação de e-mail)
          2. Cria clinics + clinic_settings + clinic_users
          3. Ingere documento RAG de boas-vindas
          4. Retorna { clinic_id, user_id }
        """
        client = await get_supabase()

        # 1. Criar usuário no Auth
        try:
            auth_response = await client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,   # pula verificação de e-mail
                }
            )
            user = auth_response.user
            user_id = user.id
        except Exception as exc:
            msg = str(exc)
            if "already" in msg.lower() or "exists" in msg.lower():
                raise ValueError(f"E-mail já cadastrado: {email}")
            raise RuntimeError(f"Erro ao criar usuário: {msg}")

        logger.info(f"[Onboarding] usuário criado: {email} → user_id={user_id}")

        # 2. Criar clínica
        slug = await self.generate_slug(clinic_name)
        clinic = await clinic_repo.create(name=clinic_name, slug=slug, plan="trial")
        clinic_id = clinic["id"]

        logger.info(f"[Onboarding] clínica criada: {clinic_name} slug={slug} clinic_id={clinic_id}")

        # 3. Criar configurações padrão
        await client.table("clinic_settings").insert(
            {
                "clinic_id":            clinic_id,
                "ai_name":              "Assistente",
                "ai_personality":       "empatica, calorosa, profissional",
                "clinic_display_name":  clinic_name,
                "doctor_name":          doctor_name,
                "doctor_phone":         "",
                "whatsapp_configured":  False,
                "gcal_configured":      False,
                "working_days":         ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "working_start":        "08:00",
                "working_end":          "18:00",
                "appointment_duration": 50,
                "briefing_hour":        8,
                "confirmation_hour":    19,
                "timezone":             "America/Sao_Paulo",
                "test_mode":            True,
                "debug_mode":           False,
            }
        ).execute()

        # 4. Vincular usuário à clínica (dispara trigger → injeta clinic_id no JWT)
        await client.table("clinic_users").insert(
            {
                "clinic_id": clinic_id,
                "user_id":   user_id,
                "role":      "owner",
                "is_active": True,
            }
        ).execute()

        logger.info(f"[Onboarding] clinic_users criado: user_id={user_id} clinic_id={clinic_id} role=owner")

        # 5. Documento RAG de boas-vindas
        await self._ingest_welcome_document(client, clinic_id, clinic_name, doctor_name)

        return {"clinic_id": clinic_id, "user_id": user_id}

    async def _ingest_welcome_document(
        self,
        client,
        clinic_id: str,
        clinic_name: str,
        doctor_name: str,
    ) -> None:
        """Insere documento RAG inicial com informações básicas da clínica."""
        content = (
            f"Clínica: {clinic_name}\n"
            f"Responsável: {doctor_name}\n"
            "Especialidade: Psicologia\n"
            "Atendimento: Segunda a sexta, 8h às 18h\n"
            "Duração das consultas: 50 minutos\n"
        )
        try:
            await client.table("documents").insert(
                {
                    "clinic_id": clinic_id,
                    "name":      "Informações da clínica",
                    "content":   content,
                }
            ).execute()
            logger.info(f"[Onboarding] documento RAG inicial criado para clinic_id={clinic_id}")
        except Exception as exc:
            # Não falha o onboarding por causa do RAG
            logger.warning(f"[Onboarding] falha ao criar documento RAG: {exc}")


onboarding_service = OnboardingService()
