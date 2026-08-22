from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class EventoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150, examples=["Taller de Python"])
    descripcion: Optional[str] = Field(None, max_length=500, examples=["Introducción al desarrollo con Python"])
    categoria: str = Field(..., min_length=1, max_length=100, examples=["Tecnología"])
    fecha: datetime = Field(..., examples=["2026-09-15T14:00:00"])
    lugar: str = Field(..., min_length=1, max_length=200, examples=["Laboratorio 302"])
    cupo_maximo: int = Field(..., gt=0, examples=[30])

    @field_validator("fecha")
    @classmethod
    def fecha_debe_ser_futura(cls, valor: datetime) -> datetime:
        ahora = datetime.now(timezone.utc)
        comparar = valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)
        if comparar <= ahora:
            raise ValueError("La fecha del evento debe ser posterior a la fecha actual")
        return valor


class EventoCreate(EventoBase):
    """Datos necesarios para crear un evento."""
    pass


class EventoUpdate(BaseModel):
    """Datos opcionales para actualizar un evento."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=150)
    descripcion: Optional[str] = Field(None, max_length=500)
    categoria: Optional[str] = Field(None, min_length=1, max_length=100)
    fecha: Optional[datetime] = None
    lugar: Optional[str] = Field(None, min_length=1, max_length=200)
    cupo_maximo: Optional[int] = Field(None, gt=0)
    activo: Optional[bool] = None

    @field_validator("fecha")
    @classmethod
    def fecha_debe_ser_futura(cls, valor: datetime) -> datetime:
        ahora = datetime.now(timezone.utc)
        comparar = valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)
        if comparar <= ahora:
            raise ValueError("La fecha del evento debe ser posterior a la fecha actual")
        return valor


class EventoOut(EventoBase):
    """Información de un evento."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    activo: bool = True
    inscritos: int = 0
    cupos_disponibles: int = 0
    imagen_url: Optional[str] = None