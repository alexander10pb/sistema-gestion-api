import logging

import cloudinary.uploader
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorCollection


from app.cloudinary_config import CLOUDINARY_CONFIGURADO

logger = logging.getLogger(__name__)

def producto_helper(producto: dict) -> dict:
    """Convierte un documento de MongoDB en un dict compatible con ProductoOut."""
    return {
        "_id": str(producto["_id"]),
        "nombre": producto["nombre"],
        "descripcion": producto.get("descripcion"),
        "precio": producto["precio"],
        "categoria": producto["categoria"],
        "disponible": producto.get("disponible", True),
        "imagen_url": producto.get("imagen_url"),
    }


def validar_object_id(id_valor: str, nombre_entidad: str = "recurso") -> ObjectId:
    """
    Valida que el ID recibido tenga un formato válido de MongoDB.
    """
    try:
        return ObjectId(id_valor)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El id del {nombre_entidad} no tiene un formato válido",
        ) from exc


async def obtener_documento_o_404(
    coleccion: AsyncIOMotorCollection,
    object_id: ObjectId,
    nombre_entidad: str,
) -> dict:
    documento = await coleccion.find_one({"_id": object_id})

    if documento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{nombre_entidad.capitalize()} no encontrado",
        )

    return documento


def evento_helper(evento: dict) -> dict:
    """
    Convierte un documento de MongoDB al formato de respuesta
    utilizado por EventoOut.
    """
    inscritos = evento.get("inscritos", 0)

    return {
        "_id": str(evento["_id"]),
        "nombre": evento["nombre"],
        "descripcion": evento.get("descripcion"),
        "categoria": evento["categoria"],
        "fecha": evento["fecha"],
        "lugar": evento["lugar"],
        "cupo_maximo": evento["cupo_maximo"],
        "activo": evento.get("activo", True),
        "inscritos": inscritos,
        "cupos_disponibles": max(evento["cupo_maximo"] - inscritos, 0),
        "imagen_url": evento.get("imagen_url"),
    }


def documento_requerido(
    documento: dict | None,
    nombre_entidad: str,
    contexto: str,
) -> dict:
    """
    Garantiza que una relectura de MongoDB devolvió el documento esperado.

    Evita que un `None` inesperado se propague hasta los helpers de
    serialización, donde produciría un TypeError sin ninguna pista del
    origen real del problema.
    """
    if documento is None:
        logger.error(
            "No se pudo releer el %s desde MongoDB (%s)",
            nombre_entidad,
            contexto,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo obtener el {nombre_entidad} después de la operación",
        )

    return documento


def subir_imagen_cloudinary(contenido: bytes, folder: str) -> tuple[str, str]:
    """
    Sube una imagen a Cloudinary y devuelve (secure_url, public_id).

    Traduce los fallos del proveedor a errores HTTP explícitos en lugar de
    dejar escapar excepciones de la librería o KeyError al leer la respuesta.
    """
    if not CLOUDINARY_CONFIGURADO:
        logger.error(
            "Intento de subir una imagen sin CLOUDINARY_URL configurada"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de imágenes no está configurado",
        )

    try:
        resultado = cloudinary.uploader.upload(
            contenido,
            folder=folder,
            resource_type="image",
        )
    except Exception as exc:
        logger.exception("Error al subir la imagen a Cloudinary (%s)", folder)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo subir la imagen al servicio de imágenes",
        ) from exc

    imagen_url = resultado.get("secure_url")
    public_id = resultado.get("public_id")

    if not imagen_url or not public_id:
        logger.error(
            "Respuesta inesperada de Cloudinary al subir la imagen: %s",
            resultado,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Respuesta inválida del servicio de imágenes",
        )

    return imagen_url, public_id


def eliminar_imagen_cloudinary(public_id: str, contexto: str) -> bool:
    """
    Elimina una imagen de Cloudinary sin interrumpir la petición.

    Devuelve True si Cloudinary confirmó la eliminación. Los fallos se
    registran con nivel WARNING (incluyendo el traceback) porque dejan
    una imagen huérfana que requiere limpieza manual.
    """
    try:
        resultado = cloudinary.uploader.destroy(
            public_id,
            resource_type="image",
        )
    except Exception:
        logger.warning(
            "No se pudo eliminar la imagen %s de Cloudinary (%s); "
            "queda huérfana y debe limpiarse manualmente",
            public_id,
            contexto,
            exc_info=True,
        )
        return False

    if resultado.get("result") != "ok":
        logger.warning(
            "Cloudinary no eliminó la imagen %s (%s): %s",
            public_id,
            contexto,
            resultado,
        )
        return False

    return True
