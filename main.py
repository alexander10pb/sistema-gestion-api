import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.database import crear_indices
from app.logging_config import configurar_logging
from app.routers import auth, productos, eventos

configurar_logging()

logger = logging.getLogger(__name__)


# ============================================================
# LIFESPAN (startup / shutdown)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await crear_indices()
    except Exception:
        # Arrancar sin índices permitiría emails e inscripciones duplicadas,
        # por lo que el arranque debe fallar de forma visible.
        logger.critical(
            "Fallo en el arranque: no se pudieron preparar los índices "
            "de MongoDB"
        )
        raise

    yield


app = FastAPI(
    title="Sistema de Gestión API",
    description=(
        "API REST desarrollada con FastAPI para la gestión de usuarios, "
        "productos y eventos. Permite la autenticación y autorización "
        "de usuarios mediante JWT, administración de productos y "
        "gestión de eventos e inscripciones con control de cupos "
        "disponibles. "
        "La API cuenta con documentación interactiva disponible "
        "en /docs (Swagger UI) y /redoc."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# CONFIGURACIÓN CORS
# ============================================================

ORIGINS_POR_DEFECTO = [
    "https://evsite-v2.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Se puede sobrescribir con ALLOWED_ORIGINS="https://a.com,https://b.com"
origins = [
    origen.strip()
    for origen in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origen.strip()
] or ORIGINS_POR_DEFECTO

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth.router)
app.include_router(productos.router)
app.include_router(eventos.router)


# ============================================================
# MANEJADORES DE ERRORES
# ============================================================

@app.exception_handler(PyMongoError)
async def error_base_datos(request: Request, exc: PyMongoError):
    """
    Traduce los fallos de MongoDB a 503 en lugar de un 500 sin contexto.
    """
    logger.exception(
        "Error de MongoDB en %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "La base de datos no está disponible en este momento"
        },
    )


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception):
    """
    Último recurso: registra el traceback completo del error y responde
    un 500 genérico sin filtrar detalles internos al cliente.
    """
    logger.exception(
        "Error no controlado en %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/", tags=["Root"], summary="Estado de la API")
async def root():
    return {
        "mensaje": "API de la cafetería funcionando correctamente",
        "docs": "/docs"
    }