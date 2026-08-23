import logging
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.auth.dependencies import (
    credenciales_invalidas,
    get_current_user,
    oauth2_scheme
)

from app.auth.schemas import (
    Token,
    UsuarioCreate,
    UsuarioOut
)

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password
)

from app.database import (
    token_blacklist_collection,
    users_collection
)

from app.utils import documento_requerido


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"]
)


def usuario_helper(usuario: dict) -> dict:
    return {
        "_id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "rol": usuario.get("rol", "usuario"),
    }


@router.post(
    "/register",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
async def registrar_usuario(
    datos: UsuarioCreate
):
    """
    Registra un nuevo usuario.

    Todos los usuarios registrados públicamente
    reciben automáticamente el rol 'usuario'.
    """

    nuevo_usuario = {
        "nombre": datos.nombre,
        "email": datos.email,
        "password_hash": hash_password(datos.password),

        # IMPORTANTE:
        # Nunca permitir que el cliente
        # seleccione este valor.
        "rol": "usuario",
    }

    try:

        resultado = await users_collection.insert_one(
            nuevo_usuario
        )

    except DuplicateKeyError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con ese email",
        ) from exc

    creado = await users_collection.find_one(
        {
            "_id": resultado.inserted_id
        }
    )

    return usuario_helper(
        documento_requerido(creado, "usuario", "registro")
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión"
)
async def iniciar_sesion(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Recibe `username` (el email) y `password`
    como form-data.

    Funciona directamente con el botón
    Authorize de Swagger.
    """

    usuario = await users_collection.find_one(
        {
            "email": form_data.username
        }
    )

    if (
        usuario is None
        or not verify_password(
            form_data.password,
            usuario.get("password_hash", "")
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token, _, _ = create_access_token(
        subject=str(usuario["_id"])
    )

    return Token(
        access_token=token
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión"
)
async def cerrar_sesion(
    token: str = Depends(oauth2_scheme),
    _usuario: dict = Depends(get_current_user)
):
    """
    Invalida el token actual agregándolo
    a la blacklist en MongoDB.
    """

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        # get_current_user ya validó el token; llegar aquí implica que algo
        # cambió entre ambas decodificaciones.
        logger.warning("Token no decodificable durante el logout: %s", exc)
        raise credenciales_invalidas() from exc

    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti is None or exp is None:
        logger.warning("Token sin jti/exp: no se puede invalidar")
        raise credenciales_invalidas()

    try:
        await token_blacklist_collection.insert_one(
            {
                "jti": jti,
                "expira_en": datetime.fromtimestamp(
                    exp,
                    tz=timezone.utc
                ),
            }
        )
    except DuplicateKeyError:
        # El token ya estaba invalidado: el logout es idempotente.
        logger.info("El token %s ya estaba en la blacklist", jti)

    return {
        "mensaje": "Sesión cerrada correctamente"
    }


@router.get(
    "/me",
    response_model=UsuarioOut,
    summary="Usuario autenticado actual"
)
async def usuario_actual(
    usuario: dict = Depends(get_current_user)
):
    return usuario_helper(usuario)