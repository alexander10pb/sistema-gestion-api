import logging

from bson import ObjectId
from bson.errors import InvalidId
import jwt

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.security import decode_access_token
from app.database import (
    token_blacklist_collection,
    users_collection
)


logger = logging.getLogger(__name__)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


def credenciales_invalidas() -> HTTPException:
    """
    Construye el error 401 usado en toda la autenticación.

    Es una función y no una instancia compartida para no reutilizar el
    mismo objeto de excepción (y su traceback) entre peticiones.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> dict:

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        logger.info("Token rechazado: %s", exc)
        raise credenciales_invalidas() from exc

    jti = payload.get("jti")
    user_id = payload.get("sub")

    if jti is None or user_id is None:
        logger.warning("Token sin claims obligatorios (jti/sub)")
        raise credenciales_invalidas()

    # Verificar si el token fue invalidado por logout
    en_blacklist = await token_blacklist_collection.find_one(
        {
            "jti": jti
        }
    )

    if en_blacklist is not None:
        raise credenciales_invalidas()

    # Validar ObjectId
    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError) as exc:
        logger.warning("Token con sub no convertible a ObjectId: %r", user_id)
        raise credenciales_invalidas() from exc

    # Buscar usuario
    usuario = await users_collection.find_one(
        {
            "_id": object_id
        }
    )

    if usuario is None:
        logger.info("Token válido de un usuario inexistente: %s", user_id)
        raise credenciales_invalidas()

    # Usuarios antiguos que todavía no tengan rol
    # serán considerados usuarios normales.
    if "rol" not in usuario:
        usuario["rol"] = "usuario"

    return usuario


async def get_current_admin(
    usuario: dict = Depends(get_current_user)
) -> dict:
    """
    Permite el acceso únicamente a usuarios
    con rol de administrador.
    """

    if usuario.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador",
        )

    return usuario
