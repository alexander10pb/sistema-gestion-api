from bson import ObjectId
import jwt

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.security import decode_access_token
from app.database import (
    token_blacklist_collection,
    users_collection
)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


credenciales_invalidas = HTTPException(
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
    except jwt.PyJWTError:
        raise credenciales_invalidas

    jti = payload.get("jti")
    user_id = payload.get("sub")

    if jti is None or user_id is None:
        raise credenciales_invalidas

    # Verificar si el token fue invalidado por logout
    en_blacklist = await token_blacklist_collection.find_one(
        {
            "jti": jti
        }
    )

    if en_blacklist is not None:
        raise credenciales_invalidas

    # Validar ObjectId
    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise credenciales_invalidas

    # Buscar usuario
    usuario = await users_collection.find_one(
        {
            "_id": object_id
        }
    )

    if usuario is None:
        raise credenciales_invalidas

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