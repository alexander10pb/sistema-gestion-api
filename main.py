import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import crear_indices
from app.routers import auth, productos, eventos


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
)


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

os.makedirs("static/productos", exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# ============================================================
# CONFIGURACIÓN CORS
# ============================================================

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://evsite-v2.vercel.app"
]

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
# STARTUP
# ============================================================

@app.on_event("startup")
async def crear_indices_al_iniciar():
    await crear_indices()


# ============================================================
# ROOT
# ============================================================

@app.get("/", tags=["Root"], summary="Estado de la API")
async def root():
    return {
        "mensaje": "API de la cafetería funcionando correctamente",
        "docs": "/docs"
    }
