import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

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


async def crear_indices():
    """Índices necesarios: email único y expiración automática de la blacklist."""
    await users_collection.create_index("email", unique=True)
    await token_blacklist_collection.create_index("expira_en", expireAfterSeconds=0)
