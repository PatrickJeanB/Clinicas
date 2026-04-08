from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.exceptions import KarenException
from app.core.logging import logger
from app.core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.dependencies import init_supabase  # noqa: PLC0415
    await init_supabase()
    logger.info(f"Iniciando {settings.APP_NAME} — ambiente: {settings.APP_ENV}")
    yield
    logger.info(f"Encerrando {settings.APP_NAME}")


app = FastAPI(
    title="AppClinicas - Secretaria IA",
    description="Backend da secretaria de IA para clínicas via WhatsApp",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = (
    ["*"]
    if settings.APP_ENV == "development"
    else ([settings.FRONTEND_URL] if settings.FRONTEND_URL else [])
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(KarenException)
async def karen_exception_handler(request: Request, exc: KarenException) -> JSONResponse:
    logger.warning(f"KarenException [{exc.code}]: {exc.message}")
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log completo interno — stack trace nunca chega ao cliente
    logger.exception(f"Erro inesperado em {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "Erro interno do servidor"},
    )


# Rotas
from app.api import auth, doctor, health, settings_api, webhook  # noqa: E402

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(auth.router)
app.include_router(settings_api.router)
app.include_router(doctor.router, prefix="/doctor")

# Inicializa o agente — registra handler no buffer
from app.agent import agent  # noqa: E402, F401
