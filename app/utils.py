from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorCollection


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
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El id del {nombre_entidad} no tiene un formato válido",
        )


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
