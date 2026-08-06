import uuid
from pathlib import Path
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.dependencies import get_current_user
from app.database import productos_collection
from app.schemas import CategoriaProducto, ProductoCreate, ProductoOut, ProductoUpdate
from app.utils import producto_helper

router = APIRouter(prefix="/productos", tags=["Productos"])

# Carpeta donde se guardan las imágenes subidas; se sirve como estática en main.py
CARPETA_IMAGENES = Path("static/productos")
CARPETA_IMAGENES.mkdir(parents=True, exist_ok=True)

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
TAMANO_MAXIMO_MB = 5


def validar_object_id(producto_id: str) -> ObjectId:
    try:
        return ObjectId(producto_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del producto no tiene un formato válido",
        )


@router.get("", response_model=List[ProductoOut], summary="Listar productos del menú")
async def listar_productos(
    categoria: Optional[CategoriaProducto] = None,
    disponible: Optional[bool] = None,
):
    """
    Consulta todos los productos del menú (GET).
    Permite filtrar opcionalmente por categoría y/o disponibilidad.
    """
    filtro = {}
    if categoria is not None:
        filtro["categoria"] = categoria.value
    if disponible is not None:
        filtro["disponible"] = disponible

    productos = []
    async for producto in productos_collection.find(filtro):
        productos.append(producto_helper(producto))
    return productos


@router.get("/{producto_id}", response_model=ProductoOut, summary="Obtener un producto por id")
async def obtener_producto(producto_id: str):
    oid = validar_object_id(producto_id)
    producto = await productos_collection.find_one({"_id": oid})
    if producto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return producto_helper(producto)


@router.post(
    "",
    response_model=ProductoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo producto",
)
async def crear_producto(producto: ProductoCreate, _usuario: dict = Depends(get_current_user)):
    """Crea un nuevo producto del menú (POST). Requiere estar autenticado."""
    nuevo_producto = producto.model_dump()
    resultado = await productos_collection.insert_one(nuevo_producto)
    creado = await productos_collection.find_one({"_id": resultado.inserted_id})
    return producto_helper(creado)


@router.post(
    "/{producto_id}/imagen",
    response_model=ProductoOut,
    summary="Subir o reemplazar la imagen de un producto",
)
async def subir_imagen_producto(
    producto_id: str,
    archivo: UploadFile = File(..., description="Imagen del producto (jpg, png, webp o gif, máx. 5 MB)"),
    _usuario: dict = Depends(get_current_user),
):
    """Sube una imagen y la asocia al producto. Si ya tenía una, la reemplaza."""
    oid = validar_object_id(producto_id)
    producto = await productos_collection.find_one({"_id": oid})
    if producto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    extension = Path(archivo.filename or "").suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado. Usa: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}",
        )

    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La imagen supera el tamaño máximo de {TAMANO_MAXIMO_MB} MB",
        )

    # Si el producto ya tenía una imagen local, se borra para no dejar archivos huérfanos
    imagen_anterior = producto.get("imagen_url")
    if imagen_anterior and imagen_anterior.startswith("/static/productos/"):
        ruta_anterior = Path(imagen_anterior.lstrip("/"))
        if ruta_anterior.exists():
            ruta_anterior.unlink()

    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    ruta_destino = CARPETA_IMAGENES / nombre_archivo
    with open(ruta_destino, "wb") as f:
        f.write(contenido)

    imagen_url = f"/static/productos/{nombre_archivo}"
    await productos_collection.update_one({"_id": oid}, {"$set": {"imagen_url": imagen_url}})

    actualizado = await productos_collection.find_one({"_id": oid})
    return producto_helper(actualizado)


@router.delete(
    "/{producto_id}/imagen",
    response_model=ProductoOut,
    summary="Quitar la imagen de un producto",
)
async def eliminar_imagen_producto(producto_id: str, _usuario: dict = Depends(get_current_user)):
    oid = validar_object_id(producto_id)
    producto = await productos_collection.find_one({"_id": oid})
    if producto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    imagen_actual = producto.get("imagen_url")
    if imagen_actual and imagen_actual.startswith("/static/productos/"):
        ruta = Path(imagen_actual.lstrip("/"))
        if ruta.exists():
            ruta.unlink()

    await productos_collection.update_one({"_id": oid}, {"$set": {"imagen_url": None}})
    actualizado = await productos_collection.find_one({"_id": oid})
    return producto_helper(actualizado)


@router.put("/{producto_id}", response_model=ProductoOut, summary="Actualizar un producto")
async def actualizar_producto(
    producto_id: str, cambios: ProductoUpdate, _usuario: dict = Depends(get_current_user)
):
    oid = validar_object_id(producto_id)
    datos = {k: v for k, v in cambios.model_dump(exclude_unset=True).items()}

    if not datos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar al menos un campo para actualizar",
        )

    resultado = await productos_collection.update_one({"_id": oid}, {"$set": datos})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    actualizado = await productos_collection.find_one({"_id": oid})
    return producto_helper(actualizado)


@router.delete(
    "/{producto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un producto",
)
async def eliminar_producto(producto_id: str, _usuario: dict = Depends(get_current_user)):
    """Elimina un producto del menú por id (DELETE). Requiere estar autenticado."""
    oid = validar_object_id(producto_id)
    producto = await productos_collection.find_one({"_id": oid})
    if producto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    imagen_url = producto.get("imagen_url")
    if imagen_url and imagen_url.startswith("/static/productos/"):
        ruta = Path(imagen_url.lstrip("/"))
        if ruta.exists():
            ruta.unlink()

    await productos_collection.delete_one({"_id": oid})
    return None
