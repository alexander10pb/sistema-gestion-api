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
