from pathlib import Path

import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status

from app import cloudinary_config as _cloudinary_config


EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
TAMANO_MAXIMO_MB = 5


async def leer_imagen_validada(archivo: UploadFile) -> bytes:
    extension = Path(archivo.filename or "").suffix.lower()

    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Formato no soportado. Usa: "
                f"{', '.join(sorted(EXTENSIONES_PERMITIDAS))}"
            ),
        )

    contenido = await archivo.read()

    if len(contenido) > TAMANO_MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La imagen supera el tamaño máximo de "
                f"{TAMANO_MAXIMO_MB} MB"
            ),
        )

    return contenido


def subir_imagen(contenido: bytes, carpeta: str) -> tuple[str, str]:
    try:
        resultado = cloudinary.uploader.upload(
            contenido,
            folder=carpeta,
            resource_type="image",
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir la imagen: {str(error)}",
        )

    return resultado["secure_url"], resultado["public_id"]


def eliminar_imagen(public_id: str | None) -> None:
    if not public_id:
        return

    try:
        cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
        )
    except Exception as error:
        print(f"No se pudo eliminar la imagen de Cloudinary: {error}")
