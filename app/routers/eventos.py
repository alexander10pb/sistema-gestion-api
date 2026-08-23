import logging
from datetime import datetime, timezone
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.auth.dependencies import get_current_user, get_current_admin
from app.database import eventos_collection, inscripciones_collection
from app.image_utils import eliminar_imagen, leer_imagen_validada, subir_imagen 
from app.schemas import (
    EventoCreate,
    EventoOut,
    EventoUpdate,
    InscripcionOut,
    EstadoInscripcion
)
from app.utils import evento_helper, obtener_documento_o_404, validar_object_id, eliminar_imagen_cloudinary, documento_requerido


router = APIRouter(
    prefix="/eventos",
    tags=["Eventos"],
)

logger = logging.getLogger(__name__)


# ============================================================
# LISTAR EVENTOS
# ============================================================

@router.get(
    "",
    response_model=List[EventoOut],
    summary="Listar eventos",
)
async def listar_eventos():
    """
    Lista todos los eventos activos.

    Los eventos se ordenan por fecha ascendente.
    """

    eventos = []

    async for evento in eventos_collection.find(
        {"activo": True}
    ).sort("fecha", 1):

        eventos.append(
            evento_helper(evento)
        )

    return eventos


# ============================================================
# MIS INSCRIPCIONES
# ============================================================
# IMPORTANTE:
# Esta ruta debe estar antes de /{evento_id} para evitar
# que "mis-inscripciones" sea interpretado como un ID.
# ============================================================

@router.get(
    "/mis-inscripciones",
    response_model=List[InscripcionOut],
    summary="Consultar mis inscripciones",
)
async def mis_inscripciones(
    usuario: dict = Depends(get_current_user),
):
    """
    Consulta las inscripciones activas del usuario autenticado.
    """

    usuario_id = str(usuario["_id"])

    inscripciones = []

    async for inscripcion in inscripciones_collection.find(
        {
            "usuario_id": usuario_id,
            "estado": EstadoInscripcion.activa, 
        }
    ).sort("fecha_inscripcion", -1):

        inscripcion["_id"] = str(
            inscripcion["_id"]
        )

        inscripciones.append(inscripcion)

    return inscripciones


# ============================================================
# OBTENER EVENTO POR ID
# ============================================================

@router.get(
    "/{evento_id}",
    response_model=EventoOut,
    summary="Obtener un evento por id",
)
async def obtener_evento(
    evento_id: str,
):
    """
    Obtiene un evento específico por su ID.
    """

    oid = validar_object_id(evento_id, "evento")

    evento = await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    return evento_helper(evento)


# ============================================================
# CREAR EVENTO
# ============================================================

@router.post(
    "",
    response_model=EventoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo evento",
)
async def crear_evento(
    evento: EventoCreate,
    _usuario: dict = Depends(get_current_admin),
):
    """
    Crea un nuevo evento.

    Requiere autenticación.
    """

    nuevo_evento = evento.model_dump()

    nuevo_evento["activo"] = True
    nuevo_evento["inscritos"] = 0

    # Datos de la imagen
    nuevo_evento["imagen_url"] = None
    nuevo_evento["imagen_public_id"] = None

    nuevo_evento["created_at"] = datetime.now(timezone.utc)
    nuevo_evento["updated_at"] = datetime.now(timezone.utc)

    resultado = await eventos_collection.insert_one(
        nuevo_evento
    )

    creado = await eventos_collection.find_one(
        {
            "_id": resultado.inserted_id,
        }
    )

    return evento_helper(
        documento_requerido(creado, "evento", "creación")
    )


# ============================================================
# SUBIR / REEMPLAZAR IMAGEN
# ============================================================

@router.post(
    "/{evento_id}/imagen",
    response_model=EventoOut,
    summary="Subir o reemplazar la imagen de un evento",
)
async def subir_imagen_evento(
    evento_id: str,
    archivo: UploadFile = File(
        ...,
        description=(
            "Imagen del evento "
            "(jpg, png, webp o gif, máx. 5 MB)"
        ),
    ),
    _usuario: dict = Depends(get_current_admin),
):
    """
    Sube una imagen a Cloudinary y la asocia al evento.

    Si el evento ya tenía una imagen, la imagen anterior
    será eliminada de Cloudinary después de subir la nueva.
    """

    oid = validar_object_id(evento_id, "evento")

    evento = await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    contenido = await leer_imagen_validada(archivo)

    # --------------------------------------------------------
    # Guardar referencia de imagen anterior
    # --------------------------------------------------------

    public_id_anterior = evento.get(
        "imagen_public_id"
    )

    imagen_url, public_id_nuevo = subir_imagen(
        contenido,
        "cafeteria/eventos",
    )

    resultado = await eventos_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "imagen_url": imagen_url,
                "imagen_public_id": public_id_nuevo,
            }
        },
    )

    if resultado.matched_count == 0:
        # El evento fue eliminado mientras se subía la imagen.
        eliminar_imagen_cloudinary(
            public_id_nuevo,
            "evento inexistente",
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado",
        )

    eliminar_imagen(public_id_anterior)

    # --------------------------------------------------------
    # Obtener evento actualizado
    # --------------------------------------------------------

    actualizado = await eventos_collection.find_one(
        {
            "_id": oid,
        }
    )

    return evento_helper(
        documento_requerido(actualizado, "evento", "subida de imagen")
    )


# ============================================================
# ELIMINAR IMAGEN
# ============================================================

@router.delete(
    "/{evento_id}/imagen",
    response_model=EventoOut,
    summary="Quitar la imagen de un evento",
)
async def eliminar_imagen_evento(
    evento_id: str,
    _usuario: dict = Depends(get_current_admin),
):
    """
    Elimina la imagen del evento de Cloudinary
    y limpia sus referencias en MongoDB.
    """

    oid = validar_object_id(evento_id, "evento")

    evento = await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    public_id = evento.get(
        "imagen_public_id"
    )

    eliminar_imagen(public_id)

    # --------------------------------------------------------
    # Limpiar MongoDB
    # --------------------------------------------------------

    await eventos_collection.update_one(
        {
            "_id": oid,
        },
        {
            "$set": {
                "imagen_url": None,
                "imagen_public_id": None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    actualizado = await eventos_collection.find_one(
        {
            "_id": oid,
        }
    )

    return evento_helper(
        documento_requerido(actualizado, "evento", "eliminación de imagen")
    )


# ============================================================
# ACTUALIZAR EVENTO
# ============================================================

@router.put(
    "/{evento_id}",
    response_model=EventoOut,
    summary="Actualizar un evento",
)
async def actualizar_evento(
    evento_id: str,
    cambios: EventoUpdate,
    _usuario: dict = Depends(get_current_admin),
):
    """
    Actualiza uno o varios campos de un evento.

    No permite reducir el cupo máximo por debajo
    de la cantidad actual de inscritos.
    """

    oid = validar_object_id(evento_id, "evento")

    # --------------------------------------------------------
    # Obtener evento actual
    # --------------------------------------------------------

    await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    # --------------------------------------------------------
    # Obtener únicamente los campos enviados
    # --------------------------------------------------------

    datos = cambios.model_dump(
        exclude_unset=True
    )

    if not datos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Debe enviar al menos un campo "
                "para actualizar"
            ),
        )

    # --------------------------------------------------------
    # Validar cupo máximo
    # --------------------------------------------------------

    if "cupo_maximo" in datos:

        inscritos = await inscripciones_collection.count_documents(
            {
                "evento_id": evento_id,
                "estado": EstadoInscripcion.activa,
            }
        )

        if datos["cupo_maximo"] < inscritos:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "El cupo máximo no puede ser menor "
                    "al número actual de inscritos "
                    f"({inscritos})"
                ),
            )

    # --------------------------------------------------------
    # Actualizar fecha de modificación
    # --------------------------------------------------------

    datos["updated_at"] = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # Actualizar MongoDB
    # --------------------------------------------------------

    resultado = await eventos_collection.update_one(
        {
            "_id": oid,
        },
        {
            "$set": datos,
        },
    )

    if resultado.matched_count == 0:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado",
        )

    actualizado = await eventos_collection.find_one(
        {
            "_id": oid,
        }
    )

    return evento_helper(
        documento_requerido(actualizado, "evento", "actualización")
    )


# ============================================================
# DESACTIVAR EVENTO
# ============================================================

@router.delete(
    "/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar un evento",
)
async def eliminar_evento(
    evento_id: str,
    _usuario: dict = Depends(get_current_admin),
):
    """
    Desactiva un evento.

    No elimina físicamente el documento de MongoDB.
    """

    oid = validar_object_id(evento_id, "evento")

    await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    await eventos_collection.update_one(
        {
            "_id": oid,
        },
        {
            "$set": {
                "activo": False,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return None


# ============================================================
# INSCRIBIRSE A EVENTO
# ============================================================

async def _devolver_cupo(oid, contexto: str) -> None:
    """
    Libera un cupo reservado.

    Se usa en los caminos de error de la inscripción. Un fallo aquí deja el
    contador de inscritos inflado, por lo que se registra explícitamente en
    lugar de perderse dentro del error original.
    """
    try:
        await eventos_collection.update_one(
            {
                "_id": oid,
                "inscritos": {
                    "$gt": 0,
                },
            },
            {
                "$inc": {
                    "inscritos": -1,
                }
            },
        )
    except PyMongoError:
        logger.exception(
            "No se pudo devolver el cupo del evento %s (%s): "
            "el contador de inscritos quedó inflado",
            oid,
            contexto,
        )


@router.post(
    "/{evento_id}/inscribirse",
    response_model=InscripcionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Inscribirse a un evento",
)
async def inscribirse_evento(
    evento_id: str,
    usuario: dict = Depends(get_current_user),
):
    """
    Inscribe al usuario autenticado en un evento.

    El incremento del contador de inscritos se realiza
    de forma atómica en MongoDB para evitar superar
    el cupo máximo.
    """

    oid = validar_object_id(evento_id, "evento")

    usuario_id = str(
        usuario["_id"]
    )

    # --------------------------------------------------------
    # 1. Verificar que el evento exista
    # --------------------------------------------------------

    await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    # --------------------------------------------------------
    # 2. Verificar que el usuario no esté inscrito
    # --------------------------------------------------------

    inscripcion_existente = (
        await inscripciones_collection.find_one(
            {
                "evento_id": evento_id,
                "usuario_id": usuario_id,
                "estado": EstadoInscripcion.activa,
            }
        )
    )

    if inscripcion_existente:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya estás inscrito en este evento",
        )

    # --------------------------------------------------------
    # 3. Incrementar inscritos solo si hay cupo
    # --------------------------------------------------------

    evento_actualizado = (
        await eventos_collection.find_one_and_update(
            {
                "_id": oid,
                "activo": True,
                "$expr": {
                    "$lt": [
                        {
                            "$ifNull": [
                                "$inscritos",
                                0,
                            ]
                        },
                        "$cupo_maximo",
                    ]
                },
            },
            {
                "$inc": {
                    "inscritos": 1,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
    )

    if evento_actualizado is None:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El evento no tiene cupos disponibles",
        )

    # --------------------------------------------------------
    # 4. Crear inscripción
    # --------------------------------------------------------

    nueva_inscripcion = {
        "evento_id": evento_id,
        "usuario_id": usuario_id,
        "fecha_inscripcion": datetime.now(timezone.utc),
        "estado": "activa",
    }

    try:

        resultado = (
            await inscripciones_collection.insert_one(
                nueva_inscripcion
            )
        )

    except DuplicateKeyError as exc:

        # ----------------------------------------------------
        # Si ya existía la inscripción, devolver el cupo
        # ----------------------------------------------------

        await _devolver_cupo(oid, "inscripción duplicada")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya estás inscrito en este evento",
        ) from exc

    except PyMongoError:

        # El cupo ya fue reservado: sin la inscripción quedaría ocupado
        # para siempre.
        logger.exception(
            "Fallo al crear la inscripción del usuario %s en el evento %s",
            usuario_id,
            evento_id,
        )

        await _devolver_cupo(oid, "fallo al crear la inscripción")

        raise

    # --------------------------------------------------------
    # 5. Obtener inscripción creada
    # --------------------------------------------------------

    inscripcion = await inscripciones_collection.find_one(
        {
            "_id": resultado.inserted_id,
        }
    )

    if inscripcion is None:

        # Caso extremadamente improbable.
        # Devolvemos el cupo para mantener consistencia.

        logger.error(
            "No se pudo releer la inscripción %s recién creada",
            resultado.inserted_id,
        )

        await _devolver_cupo(oid, "inscripción no recuperable")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener la inscripción creada",
        )

    inscripcion["_id"] = str(
        inscripcion["_id"]
    )

    return inscripcion


# ============================================================
# CANCELAR INSCRIPCIÓN
# ============================================================

@router.delete(
    "/{evento_id}/inscribirse",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar inscripción a un evento",
)
async def cancelar_inscripcion(
    evento_id: str,
    usuario: dict = Depends(get_current_user),
):
    """
    Cancela la inscripción activa del usuario autenticado.

    Al cancelar, el contador de inscritos del evento
    se reduce en uno.
    """

    oid = validar_object_id(evento_id, "evento")

    usuario_id = str(
        usuario["_id"]
    )

    # --------------------------------------------------------
    # 1. Verificar que el evento exista
    # --------------------------------------------------------

    await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    # --------------------------------------------------------
    # 2. Buscar inscripción activa
    # --------------------------------------------------------

    inscripcion = await inscripciones_collection.find_one(
        {
            "evento_id": evento_id,
            "usuario_id": usuario_id,
            "estado": EstadoInscripcion.activa,
        }
    )

    if inscripcion is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes una inscripción activa en este evento",
        )

    # --------------------------------------------------------
    # 3. Cancelar inscripción
    # --------------------------------------------------------

    resultado = await inscripciones_collection.update_one(
        {
            "_id": inscripcion["_id"],
            "estado": EstadoInscripcion.activa,
        },
        {
            "$set": {
                "estado": EstadoInscripcion.cancelada,
            }
        },
    )

    if resultado.modified_count == 0:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La inscripción ya fue cancelada",
        )

    # --------------------------------------------------------
    # 4. Liberar cupo
    # --------------------------------------------------------

    try:
        await eventos_collection.update_one(
            {
                "_id": oid,
                "inscritos": {
                    "$gt": 0,
                },
            },
            {
                "$inc": {
                    "inscritos": -1,
                },
                "$set": {
                    "updated_at": datetime.now(timezone.utc),
                },
            },
        )
    except PyMongoError:
        # La inscripción ya está cancelada: dejar constancia de que el
        # contador del evento quedó desincronizado.
        logger.exception(
            "Inscripción %s cancelada pero no se pudo liberar el cupo "
            "del evento %s",
            inscripcion["_id"],
            evento_id,
        )
        raise

    return None


# ============================================================
# LISTAR INSCRITOS DE UN EVENTO
# ============================================================

@router.get(
    "/{evento_id}/inscritos",
    response_model=List[InscripcionOut],
    summary="Consultar inscritos de un evento",
)
async def listar_inscritos(
    evento_id: str,
    _usuario: dict = Depends(get_current_admin),
):
    """
    Lista las inscripciones activas de un evento.
    """

    oid = validar_object_id(evento_id, "evento")

    # --------------------------------------------------------
    # Verificar evento
    # --------------------------------------------------------

    await obtener_documento_o_404(
        eventos_collection,
        oid,
        "evento",
    )

    # --------------------------------------------------------
    # Buscar inscritos
    # --------------------------------------------------------

    inscritos = []

    async for inscripcion in inscripciones_collection.find(
        {
            "evento_id": evento_id,
            "estado": EstadoInscripcion.activa,
        }
    ).sort("fecha_inscripcion", 1):

        inscripcion["_id"] = str(
            inscripcion["_id"]
        )

        inscritos.append(inscripcion)

    return inscritos