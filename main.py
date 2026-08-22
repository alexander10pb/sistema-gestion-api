import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import crear_indices
from app.routers import auth, productos, eventos


# ============================================================
# LIFESPAN (startup / shutdown)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await crear_indices()
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
# ROOT
# ============================================================

@app.get("/", tags=["Root"], summary="Estado de la API")
async def root():
    return {
        "mensaje": "API de la cafetería funcionando correctamente",
        "docs": "/docs"
    }