# POST /webhook - recebe mensagens WhatsApp
import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agent.buffer import message_buffer
from app.core.dependencies import get_redis
from app.core.encryption import decrypt
from app.core.logging import logger
from app.gateway.whatsapp import WhatsAppGateway
from app.repositories.clinic_settings_repo import clinic_settings_repo

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


# ------------------------------------------------------------------
# GET /webhook — verificação do webhook Meta
# ------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def webhook_verify(request: Request) -> str:
    """
    A Meta envia hub.verify_token para verificar o webhook.
    Buscamos o verify_token no banco pelo phone_number_id (passado via hub.phone_number_id
    ou inferido pelo token recebido comparado com todos os configurados).

    Como a Meta não envia phone_number_id no GET de verificação, comparamos o token
    recebido contra todos os clinic_settings que tenham whatsapp_configured=true.
    """
    params    = request.query_params
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode != "subscribe" or not token:
        logger.warning(f"[Webhook] Verificação falhou: mode={mode} token={token}")
        raise HTTPException(status_code=403, detail="Token inválido")

    # Busca clínica cujo verify_token bate com o enviado pela Meta
    clinic_cfg = await clinic_settings_repo.get_by_verify_token(token)
    if not clinic_cfg:
        logger.warning(f"[Webhook] verify_token não encontrado no banco: {token}")
        raise HTTPException(status_code=403, detail="Token inválido")

    logger.info(f"[Webhook] Verificação Meta OK — clinic_id={clinic_cfg['clinic_id']}")
    return challenge or ""


# ------------------------------------------------------------------
# POST /webhook — recepção de mensagens
# ------------------------------------------------------------------

@router.post("/webhook")
@_limiter.limit("100/minute")
async def webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    try:
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
            return Response(status_code=200)

        clinic_id = clinic_cfg["clinic_id"]

        # Valida assinatura HMAC com o app_secret da clínica (sem fallback)
        signature_header = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(body, signature_header, clinic_cfg):
            logger.warning(f"[Webhook] Assinatura HMAC inválida — clinic={clinic_id}")
            return Response(status_code=403)

        # Parse antecipado para deduplicação por message_id
        parsed = WhatsAppGateway.parse_incoming(payload)
        if parsed:
            message_id = parsed.get("message_id")
            if message_id:
                redis = await get_redis()
                dedup_key = f"processed:{message_id}"
                if await redis.exists(dedup_key):
                    logger.warning(
                        f"[Webhook] Mensagem duplicada ignorada — message_id={message_id}"
                    )
                    return Response(status_code=200)
                await redis.set(dedup_key, "1", ex=86400)  # TTL: 24 horas

        # Responde 200 IMEDIATAMENTE e processa em background
        background_tasks.add_task(_process_payload, parsed, clinic_id)
        return Response(status_code=200)

    except Exception:
        logger.exception("[Webhook] Erro inesperado no processamento — retornando 200 para Meta")
        return Response(status_code=200)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str, clinic_cfg: dict) -> bool:
    raw_secret = clinic_cfg.get("whatsapp_app_secret")
    clinic_id = clinic_cfg.get("clinic_id")

    if not raw_secret:
        logger.error(f"[Webhook] app_secret ausente — rejeitando request para clinic_id={clinic_id}")
        return False

    try:
        app_secret = decrypt(raw_secret)
    except Exception as exc:
        raise ValueError(
            f"Falha ao descriptografar app_secret para clinic_id={clinic_id}"
        ) from exc

    expected = "sha256=" + hmac.new(
        app_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def _process_payload(parsed: dict | None, clinic_id: str) -> None:
    if parsed is None:
        return

    phone = parsed["from_phone"]
    await message_buffer.add_message(phone, parsed, clinic_id)
