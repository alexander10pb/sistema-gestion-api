def producto_helper(producto: dict) -> dict:
    """Convierte un documento de MongoDB en un dict compatible con ProductoOut."""
    return {
        "_id": str(producto["_id"]),
        "nombre": producto["nombre"],
        "descripcion": producto.get("descripcion"),
        "precio": producto["precio"],
        "categoria": producto["categoria"],
        "disponible": producto.get("disponible", True),
        "imagen_url": producto.get("imagen_url"),
    }
