# Google Calendar Service Account
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.logging import logger
from app.core.settings import settings

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_service():
    """
    Constrói o serviço Google Calendar carregando credenciais da variável de
    ambiente GOOGLE_SERVICE_ACCOUNT_JSON (nunca de arquivo em disco).
    """
    raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    if not raw:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON não configurada. "
            "Defina a variável de ambiente com o JSON do service account."
        )

    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON contém JSON inválido") from exc

    credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    logger.info("[GCal] serviço Google Calendar inicializado via service account")
    return service
