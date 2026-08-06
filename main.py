import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import crear_indices
from app.routers import auth, productos

app = FastAPI(
    title="Cafetería API",
    description=(
        "API REST para administrar el menú de la cafetería institucional "
        "(desayunos, almuerzos, bebidas y postres). "
        "Documentación interactiva disponible en /docs (Swagger UI) y /redoc."
    ),
    version="1.0.0",
)

# Sirve las imágenes subidas de los productos: /static/productos/archivo.jpg
os.makedirs("static/productos", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS abierto para pruebas locales; ajustar en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(productos.router)


@app.on_event("startup")
async def crear_indices_al_iniciar():
    await crear_indices()


@app.get("/", tags=["Root"], summary="Estado de la API")
async def root():
    return {"mensaje": "API de la cafetería funcionando correctamente", "docs": "/docs"}
