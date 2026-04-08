# Meta Cloud API - envio e parse de mensagens
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.exceptions import WhatsAppError
from app.core.logging import logger

_BASE_URL = "https://graph.facebook.com/v19.0"


class WhatsAppGateway:
    def __init__(self, token: str, phone_id: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._phone_id = phone_id
        self._url = f"{_BASE_URL}/{phone_id}/messages"

    # ------------------------------------------------------------------
    # Envio
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_br_phone(number: str) -> str:
        """Insere o nono dígito em números brasileiros de 12 dígitos (55 + DDD + 8 dígitos)."""
        if number.startswith("55") and len(number) == 12:
            return number[:4] + "9" + number[4:]
        return number

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, WhatsAppError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def send_text(self, to: str, message: str) -> bool:
        to = self._normalize_br_phone(to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self._url, json=payload, headers=self._headers)

        if response.status_code != 200:
            logger.error(f"[WhatsApp] Falha ao enviar texto para {to}: {response.text}")
            raise WhatsAppError(f"HTTP {response.status_code}: {response.text}")

        logger.info(f"[WhatsApp] ✓ texto enviado → {to}")
        return True

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, WhatsAppError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def send_audio(self, to: str, audio_url: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"link": audio_url},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self._url, json=payload, headers=self._headers)

        if response.status_code != 200:
            logger.error(f"[WhatsApp] Falha ao enviar áudio para {to}: {response.text}")
            raise WhatsAppError(f"HTTP {response.status_code}: {response.text}")

        logger.info(f"[WhatsApp] ✓ áudio enviado → {to}")
        return True

    # ------------------------------------------------------------------
    # Parsing (não depende de credenciais — pode ser chamado antes do login)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_incoming(payload: dict) -> dict | None:
        """
        Extrai mensagem de um webhook payload da Meta.
        Retorna None se for status update (delivered, read, etc.).
        """
        try:
            entry = payload["entry"][0]
            change = entry["changes"][0]["value"]

            # Ignora status updates
            if "statuses" in change and "messages" not in change:
                return None

            message = change["messages"][0]
            contact = change["contacts"][0]
            msg_type = message["type"]

            content = WhatsAppGateway._extract_content(message, msg_type)

            parsed = {
                "message_id": message["id"],
                "from_phone": message["from"],
                "from_name": contact.get("profile", {}).get("name", ""),
                "message_type": msg_type,
                "content": content,
                "timestamp": message["timestamp"],
            }

            logger.info(
                f"[WhatsApp] ← recebido {msg_type} de {parsed['from_phone']}"
            )
            return parsed

        except (KeyError, IndexError) as exc:
            logger.warning(f"[WhatsApp] Payload inesperado: {exc} | payload={payload}")
            return None

    @staticmethod
    def _extract_content(message: dict, msg_type: str) -> str:
        """Extrai o conteúdo relevante dependendo do tipo."""
        if msg_type == "text":
            return message["text"]["body"]
        if msg_type == "audio":
            return message["audio"].get("id", "")
        if msg_type == "image":
            return message["image"].get("id", "")
        if msg_type == "document":
            return message["document"].get("id", "")

        logger.debug(f"[WhatsApp] Tipo não mapeado: {msg_type}")
        return ""

    @staticmethod
    def extract_phone_number_id(payload: dict) -> str | None:
        """Extrai o phone_number_id do metadata do webhook (usado para roteamento multi-tenant)."""
        try:
            return payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
        except (KeyError, IndexError):
            return None
