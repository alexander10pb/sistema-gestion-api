from datetime import datetime
from typing import List

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.database import eventos_collection, inscripciones_collection
from app.schemas import EventoCreate, EventoOut, EventoUpdate, InscripcionOut


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"]
)

def validar_object_id(evento_id: str) -> ObjectId:
    try:
        return ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id del evento no tiene un formato válido"
        )

async def evento_helper(evento: dict) -> dict:
    inscritos = evento.get("inscritos", 0)

    return {
        "_id": str(evento["_id"]),
        "nombre": evento["nombre"],
        "descripcion": evento.get("descripcion"),
        "fecha": evento["fecha"],
        "lugar": evento["lugar"],
        "cupo_maximo": evento["cupo_maximo"],
        "activo": evento.get("activo", True),
        "inscritos": inscritos,
        "cupos_disponibles": max(
            evento["cupo_maximo"] - inscritos,
            0
        )
    }

@router.get(
    "",
    response_model=List[EventoOut],
    summary="Listar eventos"
)
async def listar_eventos():

    eventos = []

    async for evento in eventos_collection.find(
        {"activo": True}
    ).sort("fecha", 1):

        eventos.append(
            await evento_helper(evento)
        )

    return eventos

@router.get(
    "/{evento_id}",
    response_model=EventoOut,
    summary="Obtener un evento por id"
)
async def obtener_evento(evento_id: str):

    oid = validar_object_id(evento_id)

    evento = await eventos_collection.find_one({
        "_id": oid
    })

    if evento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )

    return await evento_helper(evento)

@router.post(
    "",
    response_model=EventoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo evento"
)
async def crear_evento(
    evento: EventoCreate,
    _usuario: dict = Depends(get_current_user)
):
    """Crea un nuevo evento. Requiere autenticación."""

    nuevo_evento = evento.model_dump()

    nuevo_evento["activo"] = True
    nuevo_evento["inscritos"] = 0
    nuevo_evento["created_at"] = datetime.utcnow()
    nuevo_evento["updated_at"] = datetime.utcnow()

    resultado = await eventos_collection.insert_one(
        nuevo_evento
    )

    creado = await eventos_collection.find_one({
        "_id": resultado.inserted_id
    })

    return await evento_helper(creado)

@router.put(
    "/{evento_id}",
    response_model=EventoOut,
    summary="Actualizar un evento"
)
async def actualizar_evento(
    evento_id: str,
    cambios: EventoUpdate,
    _usuario: dict = Depends(get_current_user)
):

    oid = validar_object_id(evento_id)

    datos = {
        k: v
        for k, v in cambios.model_dump(
            exclude_unset=True
        ).items()
    }

    if not datos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar al menos un campo para actualizar"
        )

    # Verificar que no se reduzca el cupo
    # por debajo de los inscritos actuales
    if "cupo_maximo" in datos:

        inscritos = await inscripciones_collection.count_documents({
            "evento_id": evento_id,
            "estado": "activa"
        })

        if datos["cupo_maximo"] < inscritos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El cupo máximo no puede ser menor "
                    f"al número actual de inscritos ({inscritos})"
                )
            )

    datos["updated_at"] = datetime.utcnow()

    resultado = await eventos_collection.update_one(
        {"_id": oid},
        {"$set": datos}
    )

    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )

    actualizado = await eventos_collection.find_one({
        "_id": oid
    })

    return await evento_helper(actualizado)

@router.delete(
    "/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar un evento"
)
async def eliminar_evento(
    evento_id: str,
    _usuario: dict = Depends(get_current_user)
):

    oid = validar_object_id(evento_id)

    evento = await eventos_collection.find_one({
        "_id": oid
    })

    if evento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )

    await eventos_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "activo": False,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return None

@router.post(
    "/{evento_id}/inscribirse",
    response_model=InscripcionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Inscribirse a un evento"
)
async def inscribirse_evento(
    evento_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Inscribe al usuario autenticado en un evento.

    El incremento del contador de inscritos se realiza
    de forma atómica en MongoDB para evitar superar
    el cupo máximo.
    """

    oid = validar_object_id(evento_id)

    usuario_id = str(usuario["_id"])

    # -------------------------------------------------
    # 1. Verificar que el usuario no esté inscrito
    # -------------------------------------------------

    inscripcion_existente = await inscripciones_collection.find_one({
        "evento_id": evento_id,
        "usuario_id": usuario_id,
        "estado": "activa"
    })

    if inscripcion_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya estás inscrito en este evento"
        )

    # -------------------------------------------------
    # 2. Incrementar inscritos SOLO si todavía hay cupo
    # -------------------------------------------------

    evento_actualizado = await eventos_collection.find_one_and_update(
        {
            "_id": oid,
            "activo": True,
            "$expr": {
                "$lt": [
                    {"$ifNull": ["$inscritos", 0]},
                    "$cupo_maximo"
                ]
            }
        },
        {
            "$inc": {
                "inscritos": 1
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if evento_actualizado is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El evento no tiene cupos disponibles"
        )

    # -------------------------------------------------
    # 3. Crear la inscripción
    # -------------------------------------------------

    nueva_inscripcion = {
        "evento_id": evento_id,
        "usuario_id": usuario_id,
        "fecha_inscripcion": datetime.utcnow(),
        "estado": "activa"
    }

    try:

        resultado = await inscripciones_collection.insert_one(
            nueva_inscripcion
        )

    except DuplicateKeyError:

        # Si la inscripción ya existía, debemos devolver
        # el cupo que acabamos de reservar.

        await eventos_collection.update_one(
            {"_id": oid},
            {"$inc": {"inscritos": -1}}
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya estás inscrito en este evento"
        )

    # -------------------------------------------------
    # 4. Obtener inscripción creada
    # -------------------------------------------------

    inscripcion = await inscripciones_collection.find_one({
        "_id": resultado.inserted_id
    })

    inscripcion["_id"] = str(inscripcion["_id"])

    return inscripcion

@router.delete(
    "/{evento_id}/inscribirse",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar inscripción a un evento"
)
async def cancelar_inscripcion(
    evento_id: str,
    usuario: dict = Depends(get_current_user)
):
    """
    Cancela la inscripción del usuario autenticado
    en un evento.
    """

    oid = validar_object_id(evento_id)

    # Verificar que el evento exista
    evento = await eventos_collection.find_one({
        "_id": oid
    })

    if evento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )

    usuario_id = str(usuario["_id"])

    # Buscar inscripción activa
    await inscripciones_collection.update_one(
        {
            "_id": inscripcion["_id"]
        },
        {
            "$set": {
                "estado": "cancelada"
            }
        }
    )

    await eventos_collection.update_one(
        {
            "_id": oid,
            "inscritos": {
                "$gt": 0
            }
        },
        {
            "$inc": {
                "inscritos": -1
            }
        }
    )

    return None

@router.get(
    "/mis-inscripciones",
    response_model=List[InscripcionOut],
    summary="Consultar mis inscripciones"
)
async def mis_inscripciones(
    usuario: dict = Depends(get_current_user)
):
    usuario_id = str(usuario["_id"])

    inscripciones = []

    async for inscripcion in inscripciones_collection.find({
        "usuario_id": usuario_id,
        "estado": "activa"
    }).sort("fecha_inscripcion", -1):

        inscripcion["_id"] = str(inscripcion["_id"])

        inscripciones.append(inscripcion)

    return inscripciones

@router.get(
    "/{evento_id}/inscritos",
    response_model=List[InscripcionOut],
    summary="Consultar inscritos de un evento"
)
async def listar_inscritos(
    evento_id: str,
    _usuario: dict = Depends(get_current_user)
):
    oid = validar_object_id(evento_id)

    evento = await eventos_collection.find_one({
        "_id": oid
    })

    if evento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )

    inscritos = []

    async for inscripcion in inscripciones_collection.find({
        "evento_id": evento_id,
        "estado": "activa"
    }).sort("fecha_inscripcion", 1):

        inscripcion["_id"] = str(
            inscripcion["_id"]
        )

        inscritos.append(inscripcion)

    return inscritos