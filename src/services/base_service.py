"""
Servicio base abstracto para todos los conectores de datos.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
from contextlib import asynccontextmanager

from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseService(ABC):
    """
    Clase base abstracta para todos los servicios de datos.
    Define la interfaz común que deben implementar todos los conectores.
    """
    
    def __init__(self, connection_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el servicio base.
        
        Args:
            connection_config: Configuración de conexión específica del servicio
        """
        self.connection_config = connection_config or {}
        self.connection = None
        self.is_connected = False
        
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establece la conexión con el servicio de datos.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Cierra la conexión con el servicio de datos.
        """
        pass
    
    @abstractmethod
    async def extract(self, query: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrae datos del servicio.
        
        Args:
            query: Consulta o filtro para extraer datos
            **kwargs: Parámetros adicionales específicos del servicio
            
        Returns:
            List[Dict[str, Any]]: Datos extraídos
        """
        pass
    
    @abstractmethod
    async def load(self, data: List[Dict[str, Any]], **kwargs) -> bool:
        """
        Carga datos en el servicio.
        
        Args:
            data: Datos a cargar
            **kwargs: Parámetros adicionales específicos del servicio
            
        Returns:
            bool: True si la carga fue exitosa
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Verifica la salud de la conexión.
        
        Returns:
            bool: True si el servicio está saludable
        """
        try:
            if not self.is_connected:
                return await self.connect()
            return True
        except Exception as e:
            logger.warning(f"Health check falló para {self.__class__.__name__}: {e}")
            return False
    
    @asynccontextmanager
    async def connection_context(self):
        """
        Context manager para manejar conexiones automáticamente.
        """
        try:
            if not self.is_connected:
                await self.connect()
            yield self
        finally:
            if self.is_connected:
                await self.disconnect()
    
    async def retry_operation(self, operation, max_retries: int = 3, delay: int = 1):
        """
        Ejecuta una operación con reintentos automáticos.
        
        Args:
            operation: Función asíncrona a ejecutar
            max_retries: Número máximo de reintentos
            delay: Retraso entre reintentos en segundos
            
        Returns:
            Resultado de la operación
        """
        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Operación falló después de {max_retries} reintentos: {e}")
                    raise
                
                logger.warning(f"Intento {attempt + 1} falló: {e}. Reintentando en {delay}s...")
                await asyncio.sleep(delay * (attempt + 1))  # Backoff exponencial
