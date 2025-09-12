import paramiko
from typing import List, Dict, Any, Optional

from ..utils.logger import get_logger
from .base_service import BaseService

logger = get_logger(__name__)

class SFTPService(BaseService):
    """
    Servicio para extracción de archivos desde SFTP usando paramiko (sincrónico).
    """
    def __init__(self, connection_config: Optional[Dict[str, Any]] = None):
        super().__init__(connection_config)
        self.transport = None
        self.sftp_client = None

    def connect(self) -> bool:
        try:
            self.transport = paramiko.Transport(
                (self.connection_config.host, self.connection_config.port)
            )
            self.transport.connect(
                username=self.connection_config.username,
                password=self.connection_config.password
            )
            self.sftp_client = paramiko.SFTPClient.from_transport(self.transport)
            self.is_connected = True
            logger.info("Conexión SFTP exitosa (paramiko)")
            return True
        except Exception as e:
            logger.error(f"Error conectando a SFTP: {e}")
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        if self.sftp_client:
            self.sftp_client.close()
        if self.transport:
            self.transport.close()
        self.is_connected = False
        logger.info("Desconexión SFTP exitosa (paramiko)")

    def extract(self, *args, **kwargs):
        """
        Método stub para cumplir con la interfaz abstracta.
        """
        logger.warning("Extracción no soportada en SFTPService")
        return None

    def load(self, data: List[Dict[str, Any]], **kwargs) -> bool:
        logger.warning("Carga no soportada en SFTPService")
        return False