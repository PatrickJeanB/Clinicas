# POST /webhook - recebe mensagens WhatsApp
import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from app.agent.buffer import message_buffer
from app.core.logging import logger
from app.core.settings import settings
from app.gateway.whatsapp import whatsapp_gateway

router = APIRouter()


# ------------------------------------------------------------------
# GET /webhook — verificação do webhook Meta
# ------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def webhook_verify(request: Request) -> str:
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
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

    # Valida assinatura HMAC-SHA256
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature_header):
        logger.warning("[Webhook] Assinatura HMAC inválida — requisição rejeitada")
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    # Responde 200 IMEDIATAMENTE antes de processar
    background_tasks.add_task(_process_payload, body)
    return Response(status_code=200)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str) -> bool:
    if not settings.META_APP_SECRET:
        return True  # desenvolvimento sem secret configurado

    expected = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def _process_payload(body: bytes) -> None:
    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("[Webhook] Payload não é JSON válido")
        return

    # Ignora notificações que não são de mensagem (ex.: account_update)
    if payload.get("object") != "whatsapp_business_account":
        return

    parsed = whatsapp_gateway.parse_incoming(payload)
    if parsed is None:
        # Status update (delivered/read) ou payload não reconhecido
        return

    phone = parsed["from_phone"]
    await message_buffer.add_message(phone, parsed)
