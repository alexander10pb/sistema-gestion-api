import logging
import os

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

load_dotenv()

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "cafeteria_db")

client = AsyncIOMotorClient(MONGO_URI)
database = client[DB_NAME]

# Colección de productos del menú
productos_collection = database.get_collection("productos")

# Colección de usuarios (autenticación)
users_collection = database.get_collection("usuarios")

# Tokens invalidados por logout — el índice TTL se crea en el startup de la app
token_blacklist_collection = database.get_collection("token_blacklist")

# Colección de eventos
eventos_collection = database.get_collection("eventos")

# Colección de inscripciones a eventos
inscripciones_collection = database.get_collection("inscripciones")


async def crear_indices():
    """
    Índices necesarios para la aplicación.

    Un fallo aquí (MongoDB inaccesible, credenciales inválidas, índice
    existente con otras opciones) se registra con contexto y se propaga:
    sin estos índices la API no puede garantizar unicidad de emails ni
    de inscripciones activas.
    """

    try:
        # Usuarios
        await users_collection.create_index(
            "email",
            unique=True
        )

        # Tokens invalidados por logout
        await token_blacklist_collection.create_index(
            "expira_en",
            expireAfterSeconds=0
        )

        # Eventos
        await eventos_collection.create_index(
            "fecha"
        )

        # Inscripciones
        # Un usuario no puede tener dos inscripciones
        # activas en el mismo evento.
        #
        # Si cancela su inscripción, puede volver
        # a inscribirse posteriormente.

        await inscripciones_collection.create_index(
            [
                ("evento_id", 1),
                ("usuario_id", 1)
            ],
            unique=True,
            partialFilterExpression={
                "estado": "activa"
            }
        )

    except PyMongoError:
        logger.exception(
            "No se pudieron crear los índices en la base de datos %s",
            DB_NAME,
        )
        raise

    logger.info("Índices verificados en la base de datos %s", DB_NAME)
