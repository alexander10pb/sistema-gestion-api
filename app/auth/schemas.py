from enum import Enum

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RolUsuario(str, Enum):
    USUARIO = "usuario"
    ADMIN = "admin"


class UsuarioCreate(BaseModel):
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["Ana Torres"]
    )

    email: EmailStr = Field(
        ...,
        examples=["ana.torres@institucion.edu"]
    )

    password: str = Field(
        ...,
        min_length=6,
        examples=["contraseñaSegura123"]
    )


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True
    )

    id: str = Field(
        ...,
        alias="_id"
    )

    nombre: str

    email: EmailStr

    rol: RolUsuario = RolUsuario.USUARIO


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"