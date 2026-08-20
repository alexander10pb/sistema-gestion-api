from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CategoriaProducto(str, Enum):
    desayuno = "desayuno"
    almuerzo = "almuerzo"
    bebida = "bebida"
    postre = "postre"


class ProductoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100, examples=["Sándwich de pollo"])
    descripcion: Optional[str] = Field(None, max_length=300, examples=["Pan integral con pollo y vegetales"])
    precio: float = Field(..., gt=0, examples=[8500])
    categoria: CategoriaProducto = Field(..., examples=["almuerzo"])
    disponible: bool = Field(True, examples=[True])


class ProductoCreate(ProductoBase):
    """Datos requeridos para crear un producto (POST). La imagen se sube después, en un endpoint aparte."""
    pass


class ProductoUpdate(BaseModel):
    """Datos opcionales para actualizar un producto (PUT/PATCH)."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=300)
    precio: Optional[float] = Field(None, gt=0)
    categoria: Optional[CategoriaProducto] = None
    disponible: Optional[bool] = None


class ProductoOut(ProductoBase):
    """Representación de un producto que se devuelve al cliente."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", examples=["64f1c2a9b3e2a1a1a1a1a1a1"])
    imagen_url: Optional[str] = Field(None, examples=["/static/productos/3f1c2a9b.jpg"])

class EventoBase(BaseModel):
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=150,
        examples=["Taller de Python"],
    )

    descripcion: Optional[str] = Field(
        None,
        max_length=500,
        examples=["Introducción al desarrollo con Python"],
    )

    categoria: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["Tecnología"],
    )

    fecha: datetime = Field(
        ...,
        examples=["2026-09-15T14:00:00"],
    )

    lugar: str = Field(
        ...,
        min_length=1,
        max_length=200,
        examples=["Laboratorio 302"],
    )

    cupo_maximo: int = Field(
        ...,
        gt=0,
        examples=[30],
    )


class EventoCreate(EventoBase):
    """Datos necesarios para crear un evento."""
    pass


class EventoUpdate(BaseModel):
    """Datos opcionales para actualizar un evento."""

    nombre: Optional[str] = Field(
        None,
        min_length=1,
        max_length=150,
    )

    descripcion: Optional[str] = Field(
        None,
        max_length=500,
    )

    categoria: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
    )

    fecha: Optional[datetime] = None

    lugar: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
    )

    cupo_maximo: Optional[int] = Field(
        None,
        gt=0,
    )

    activo: Optional[bool] = None


class EventoOut(EventoBase):
    """Información de un evento."""

    model_config = ConfigDict(
        populate_by_name=True
    )

    id: str = Field(
        ...,
        alias="_id",
    )

    activo: bool = True

    inscritos: int = 0

    cupos_disponibles: int = 0

    imagen_url: Optional[str] = None


class InscripcionOut(BaseModel):
    """Información de una inscripción."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        alias="_id"
    )

    evento_id: str

    usuario_id: str

    fecha_inscripcion: datetime

    estado: str

class InscripcionOut(BaseModel):
    """Información de una inscripción."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        alias="_id"
    )

    evento_id: str

    usuario_id: str

    fecha_inscripcion: datetime

    estado: str
