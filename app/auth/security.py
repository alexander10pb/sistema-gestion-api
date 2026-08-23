import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from passlib.context import CryptContext
from passlib.exc import PasswordValueError, UnknownHashError

load_dotenv()

CLAVE_DE_EJEMPLO = "cambia-esta-clave-en-produccion"

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY or SECRET_KEY == CLAVE_DE_EJEMPLO:
    raise RuntimeError(
        "La variable de entorno SECRET_KEY no está configurada con una clave "
        "propia. Genera una con: "
        'python3 -c "import secrets; print(secrets.token_hex(32))"'
    )

ALGORITHM = "HS256"

_expiracion = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(_expiracion)
except ValueError as exc:
    raise RuntimeError(
        "ACCESS_TOKEN_EXPIRE_MINUTES debe ser un número entero de minutos, "
        f"se recibió {_expiracion!r}"
    ) from exc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica la contraseña.

    Un hash ausente o corrupto en la base de datos significa credenciales
    inválidas, no un error del servidor: se registra y se devuelve False.
    """
    if not password_hash:
        logger.error("Usuario sin password_hash almacenado")
        return False

    try:
        return pwd_context.verify(password, password_hash)
    except (UnknownHashError, PasswordValueError, ValueError):
        logger.exception("No se pudo verificar la contraseña: hash inválido")
        return False


def create_access_token(subject: str) -> tuple[str, str, datetime]:
    """
    Crea un JWT firmado.
    Devuelve (token, jti, fecha_expiracion) — el jti se usa para poder
    invalidar el token puntualmente en el logout.
    """
    jti = str(uuid.uuid4())
    expira_en = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": subject,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expira_en,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti, expira_en


def decode_access_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido o expiró."""
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "jti"]},
    )
