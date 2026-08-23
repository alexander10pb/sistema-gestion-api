import logging
import os

import cloudinary
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")

# Sin credenciales las subidas fallan con errores poco descriptivos de la
# librería, por lo que los endpoints de imágenes consultan esta bandera.
CLOUDINARY_CONFIGURADO = bool(CLOUDINARY_URL)

if not CLOUDINARY_CONFIGURADO:
    logger.warning(
        "CLOUDINARY_URL no está definida: los endpoints de imágenes "
        "responderán 503 hasta que se configure"
    )

cloudinary.config(
    cloudinary_url=CLOUDINARY_URL,
    secure=True,
)
