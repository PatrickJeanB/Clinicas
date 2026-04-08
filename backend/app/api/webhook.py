# POST /webhook - recebe mensagens WhatsApp
import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from app.agent.buffer import message_buffer
from app.core.encryption import decrypt
from app.core.logging import logger
from app.core.settings import settings
from app.gateway.whatsapp import WhatsAppGateway
from app.repositories.clinic_settings_repo import clinic_settings_repo

router = APIRouter()


# ------------------------------------------------------------------
# GET /webhook — verificação do webhook Meta
# ------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def webhook_verify(request: Request) -> str:
    params = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        logger.info("[Webhook] Verificação Meta OK")
        return challenge or ""

    logger.warning(f"[Webhook] Verificação falhou: mode={mode} token={token}")
    raise HTTPException(status_code=403, detail="Token inválido")


# ------------------------------------------------------------------
# POST /webhook — recepção de mensagens
# ------------------------------------------------------------------

@router.post("/webhook")
async def webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    body = await request.body()

    # Extrai phone_number_id do payload para roteamento multi-tenant
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("[Webhook] Payload não é JSON válido")
        return Response(status_code=200)

    phone_number_id = WhatsAppGateway.extract_phone_number_id(payload)
    if not phone_number_id:
        logger.warning("[Webhook] phone_number_id não encontrado no payload")
        return Response(status_code=200)

    # Localiza a clínica pelo phone_number_id
    clinic_cfg = await clinic_settings_repo.get_by_phone_id(phone_number_id)
    if not clinic_cfg:
        logger.warning(f"[Webhook] Clínica não encontrada para phone_number_id={phone_number_id}")
        return Response(status_code=200)  # nunca retornar erro para a Meta

    clinic_id = clinic_cfg["clinic_id"]

    # Valida assinatura HMAC com o app_secret da clínica
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature_header, clinic_cfg):
        logger.warning(f"[Webhook] Assinatura HMAC inválida — clinic={clinic_id}")
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    # Responde 200 IMEDIATAMENTE e processa em background
    background_tasks.add_task(_process_payload, payload, clinic_id)
    return Response(status_code=200)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str, clinic_cfg: dict) -> bool:
    # Tenta app_secret da clínica (descriptografado); fallback para settings global
    raw_secret = clinic_cfg.get("whatsapp_app_secret")
    if raw_secret:
        try:
            app_secret = decrypt(raw_secret)
        except Exception:
            app_secret = settings.META_APP_SECRET
    else:
        app_secret = settings.META_APP_SECRET

    if not app_secret:
        return True  # desenvolvimento sem secret configurado

    expected = "sha256=" + hmac.new(
        app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def _process_payload(payload: dict, clinic_id: str) -> None:
    # Ignora notificações que não são de mensagem (ex.: account_update)
    if payload.get("object") != "whatsapp_business_account":
        return

    parsed = WhatsAppGateway.parse_incoming(payload)
    if parsed is None:
        # Status update (delivered/read) ou payload não reconhecido
        return

    phone = parsed["from_phone"]
    await message_buffer.add_message(phone, parsed, clinic_id)
