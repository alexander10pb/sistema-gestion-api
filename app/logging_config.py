import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configurar_logging() -> None:
    """Configura el logger raíz para que los logs de la app sean visibles."""
    nivel = getattr(logging, LOG_LEVEL, logging.INFO)

    raiz = logging.getLogger()

    if not raiz.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )
        raiz.addHandler(handler)

    raiz.setLevel(nivel)
