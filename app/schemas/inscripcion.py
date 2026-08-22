from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EstadoInscripcion(str, Enum):
    activa = "activa"
    cancelada = "cancelada"


class InscripcionOut(BaseModel):
    """Información de una inscripción."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    evento_id: str
    usuario_id: str
    fecha_inscripcion: datetime
    estado: EstadoInscripcion