from pathlib import Path
from typing import List, Optional

import cloudinary.uploader
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app import cloudinary_config
from app.auth.dependencies import get_current_user
from app.database import productos_collection
from app.schemas import CategoriaProducto, ProductoCreate, ProductoOut, ProductoUpdate
from app.utils import producto_helper, validar_object_id

router = APIRouter(prefix="/productos", tags=["Productos"])

EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
TAMANO_MAXIMO_MB = 5


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
    oid = validar_object_id(producto_id, "producto")
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
    archivo: UploadFile = File(
        ...,
        description="Imagen del producto (jpg, png, webp o gif, máx. 5 MB)",
    ),
    _usuario: dict = Depends(get_current_user),
):
    """Sube una imagen a Cloudinary y la asocia al producto."""

    oid = validar_object_id(producto_id, "producto")

    producto = await productos_collection.find_one({"_id": oid})

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    extension = Path(archivo.filename or "").suffix.lower()

    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato no soportado. Usa: "
                f"{', '.join(sorted(EXTENSIONES_PERMITIDAS))}"
            ),
        )

    contenido = await archivo.read()

    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"La imagen supera el tamaño máximo de "
                f"{TAMANO_MAXIMO_MB} MB"
            ),
        )

    # Guardamos los datos de la imagen anterior
    public_id_anterior = producto.get("imagen_public_id")

    try:
        # Subir nueva imagen a Cloudinary
        resultado = cloudinary.uploader.upload(
            contenido,
            folder="cafeteria/productos",
            resource_type="image",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir la imagen: {str(e)}",
        )

    imagen_url = resultado["secure_url"]
    public_id_nuevo = resultado["public_id"]

    # Guardar la nueva imagen en MongoDB
    await productos_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "imagen_url": imagen_url,
                "imagen_public_id": public_id_nuevo,
            }
        },
    )

    # Si había una imagen anterior de Cloudinary, eliminarla
    if public_id_anterior:
        try:
            cloudinary.uploader.destroy(
                public_id_anterior,
                resource_type="image",
            )
        except Exception as e:
            print(f"No se pudo eliminar la imagen anterior: {e}")

    actualizado = await productos_collection.find_one({"_id": oid})

    return producto_helper(actualizado)


@router.delete(
    "/{producto_id}/imagen",
    response_model=ProductoOut,
    summary="Quitar la imagen de un producto",
)
async def eliminar_imagen_producto(
    producto_id: str,
    _usuario: dict = Depends(get_current_user),
):
    oid = validar_object_id(producto_id, "producto")

    producto = await productos_collection.find_one({"_id": oid})

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    public_id = producto.get("imagen_public_id")

    # Eliminar imagen de Cloudinary
    if public_id:
        try:
            cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
            )
        except Exception as e:
            print(f"No se pudo eliminar la imagen de Cloudinary: {e}")

    # Limpiar referencias en MongoDB
    await productos_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "imagen_url": None,
                "imagen_public_id": None,
            }
        },
    )

    actualizado = await productos_collection.find_one({"_id": oid})

    return producto_helper(actualizado)


@router.put("/{producto_id}", response_model=ProductoOut, summary="Actualizar un producto")
async def actualizar_producto(
    producto_id: str, cambios: ProductoUpdate, _usuario: dict = Depends(get_current_user)
):
    oid = validar_object_id(producto_id, "producto")
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
async def eliminar_producto(
    producto_id: str,
    _usuario: dict = Depends(get_current_user),
):
    """Elimina un producto del menú por id."""

    oid = validar_object_id(producto_id, "producto")

    producto = await productos_collection.find_one({"_id": oid})

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    public_id = producto.get("imagen_public_id")

    # Eliminar imagen de Cloudinary si existe
    if public_id:
        try:
            cloudinary.uploader.destroy(
                public_id,
                resource_type="image",
            )
        except Exception as e:
            print(f"No se pudo eliminar la imagen: {e}")

    await productos_collection.delete_one({"_id": oid})

    return None
