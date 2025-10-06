"""
Punto de entrada principal de la aplicación.
"""
import sys
import asyncio

from src.config import init_config
from src.pipeline import Pipeline
from src.utils.logger import get_logger

# Inicializar configuración
config = init_config()
logger = get_logger(__name__)


async def main() -> int:
    """
    Función principal que ejecuta el pipeline.
    
    Returns:
        int: Código de salida (0 para éxito, 1 para error)
    """
    logger.info("Iniciando %s en modo %s", config.app_name, config.environment)

    try:
        # Inicializar el pipeline
        pipeline = Pipeline()

        # Ejecutar el pipeline
        result = await pipeline.run()

        if result:
            logger.info("Pipeline ejecutado exitosamente")
            return 0
        else:
            logger.error("Pipeline falló")
            return 1

    except Exception as e:
        logger.exception("Error inesperado en el pipeline: %s", e)
        return 1


def sync_main() -> int:
    """
    Wrapper síncrono para la función principal asíncrona.
    
    Returns:
        int: Código de salida
    """
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Pipeline interrumpido por el usuario")
        return 1
    except Exception as e:
        logger.exception("Error crítico: %s", e)
        return 1


if __name__ == "__main__":
    exit_code = sync_main()
    sys.exit(exit_code)
