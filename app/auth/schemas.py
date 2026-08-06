from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100, examples=["Ana Torres"])
    email: EmailStr = Field(..., examples=["ana.torres@institucion.edu"])
    password: str = Field(..., min_length=6, examples=["contraseñaSegura123"])


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    nombre: str
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
