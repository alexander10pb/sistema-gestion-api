from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.auth.schemas import Token, UsuarioCreate, UsuarioOut
from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from app.database import token_blacklist_collection, users_collection

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def usuario_helper(usuario: dict) -> dict:
    return {"_id": str(usuario["_id"]), "nombre": usuario["nombre"], "email": usuario["email"]}


@router.post(
    "/register",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
async def registrar_usuario(datos: UsuarioCreate):
    nuevo_usuario = {
        "nombre": datos.nombre,
        "email": datos.email,
        "password_hash": hash_password(datos.password),
    }
    try:
        resultado = await users_collection.insert_one(nuevo_usuario)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con ese email",
        )

    creado = await users_collection.find_one({"_id": resultado.inserted_id})
    return usuario_helper(creado)


@router.post("/login", response_model=Token, summary="Iniciar sesión")
async def iniciar_sesion(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Recibe `username` (el email) y `password` como form-data
    (estándar OAuth2, así funciona directo con el botón "Authorize" de Swagger).
    """
    usuario = await users_collection.find_one({"email": form_data.username})
    if usuario is None or not verify_password(form_data.password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, _, _ = create_access_token(subject=str(usuario["_id"]))
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_200_OK, summary="Cerrar sesión")
async def cerrar_sesion(token: str = Depends(oauth2_scheme), _usuario: dict = Depends(get_current_user)):
    """
    Invalida el token actual agregándolo a una blacklist en Mongo.
    El registro expira solo (índice TTL) en el mismo momento en que
    habría expirado el JWT, así la colección no crece indefinidamente.
    """
    payload = decode_access_token(token)
    await token_blacklist_collection.insert_one(
        {
            "jti": payload["jti"],
            "expira_en": datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        }
    )
    return {"mensaje": "Sesión cerrada correctamente"}


@router.get("/me", response_model=UsuarioOut, summary="Usuario autenticado actual")
async def usuario_actual(usuario: dict = Depends(get_current_user)):
    return usuario_helper(usuario)
