from bson import ObjectId
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.security import decode_access_token
from app.database import token_blacklist_collection, users_collection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

credenciales_invalidas = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o sesión expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise credenciales_invalidas

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if jti is None or user_id is None:
        raise credenciales_invalidas

    # Si el token fue invalidado por un logout previo, se rechaza
    en_blacklist = await token_blacklist_collection.find_one({"jti": jti})
    if en_blacklist is not None:
        raise credenciales_invalidas

    usuario = await users_collection.find_one({"_id": ObjectId(user_id)})
    if usuario is None:
        raise credenciales_invalidas

    return usuario
