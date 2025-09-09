"""
Configuración de logging para la aplicación.
"""
import logging
import sys
from typing import Optional
from pathlib import Path

from ..config import get_config


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Configura el sistema de logging para la aplicación.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Archivo donde escribir los logs (opcional)
        format_string: Formato personalizado para los logs
    """
    
    # Usar configuración por defecto si no se especifica
    app_config = get_config()
    log_level = level or app_config.log_level
    
    # Formato por defecto
    if not format_string:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )
    
    # Configurar el logger raíz
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[]
    )
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter(format_string)
    console_handler.setFormatter(console_formatter)
    
    # Handler para archivo (si se especifica)
    file_handler = None
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
    
    # Obtener logger raíz y configurar handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Limpiar handlers existentes
    root_logger.addHandler(console_handler)
    
    if file_handler:
        root_logger.addHandler(file_handler)
    
    # Configurar loggers de terceros para ser menos verbosos
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("pandas").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado para un módulo específico.
    
    Args:
        name: Nombre del módulo (típicamente __name__)
        
    Returns:
        logging.Logger: Logger configurado
    """
    # Configurar logging si no se ha hecho ya
    if not logging.getLogger().handlers:
        setup_logging()
    
    logger = logging.getLogger(name)
    
    # Añadir información contextual si estamos en desarrollo
    app_config = get_config()
    if app_config.environment == "development":
        logger.setLevel(logging.DEBUG)
    
    return logger


class StructuredLogger:
    """
    Logger estructurado que añade contexto adicional a los logs.
    """
    
    def __init__(self, name: str):
        """
        Inicializa el logger estructurado.
        
        Args:
            name: Nombre del logger
        """
        self.logger = get_logger(name)
        self.context = {}
    
    def add_context(self, **kwargs) -> None:
        """
        Añade contexto que se incluirá en todos los logs.
        
        Args:
            **kwargs: Pares clave-valor de contexto
        """
        self.context.update(kwargs)
    
    def remove_context(self, *keys) -> None:
        """
        Remueve claves del contexto.
        
        Args:
            *keys: Claves a remover
        """
        for key in keys:
            self.context.pop(key, None)
    
    def clear_context(self) -> None:
        """Limpia todo el contexto."""
        self.context.clear()
    
    def _format_message(self, message: str, **kwargs) -> str:
        """
        Formatea el mensaje incluyendo contexto.
        
        Args:
            message: Mensaje base
            **kwargs: Contexto adicional para este log
            
        Returns:
            str: Mensaje formateado
        """
        full_context = {**self.context, **kwargs}
        
        if full_context:
            context_str = " | ".join([f"{k}={v}" for k, v in full_context.items()])
            return f"{message} | {context_str}"
        
        return message
    
    def debug(self, message: str, **kwargs) -> None:
        """Log nivel DEBUG con contexto."""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        """Log nivel INFO con contexto."""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log nivel WARNING con contexto."""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, **kwargs) -> None:
        """Log nivel ERROR con contexto."""
        self.logger.error(self._format_message(message, **kwargs))
    
    def critical(self, message: str, **kwargs) -> None:
        """Log nivel CRITICAL con contexto."""
        self.logger.critical(self._format_message(message, **kwargs))
    
    def exception(self, message: str, **kwargs) -> None:
        """Log de excepción con contexto."""
        self.logger.exception(self._format_message(message, **kwargs))


class LoggerContextManager:
    """
    Context manager para añadir contexto temporal al logger.
    """
    
    def __init__(self, logger: StructuredLogger, **context):
        """
        Inicializa el context manager.
        
        Args:
            logger: Logger estructurado
            **context: Contexto a añadir temporalmente
        """
        self.logger = logger
        self.temp_context = context
        self.original_context = {}
    
    def __enter__(self):
        """Añade el contexto temporal."""
        # Guardar contexto original para claves que vamos a sobrescribir
        for key in self.temp_context:
            if key in self.logger.context:
                self.original_context[key] = self.logger.context[key]
        
        # Añadir contexto temporal
        self.logger.add_context(**self.temp_context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restaura el contexto original."""
        # Remover claves temporales
        self.logger.remove_context(*self.temp_context.keys())
        
        # Restaurar contexto original
        if self.original_context:
            self.logger.add_context(**self.original_context)


def with_context(logger: StructuredLogger, **context) -> LoggerContextManager:
    """
    Función helper para crear un context manager de logger.
    
    Args:
        logger: Logger estructurado
        **context: Contexto temporal
        
    Returns:
        LoggerContextManager: Context manager configurado
    """
    return LoggerContextManager(logger, **context)


# Inicializar logging al importar el módulo
setup_logging()
