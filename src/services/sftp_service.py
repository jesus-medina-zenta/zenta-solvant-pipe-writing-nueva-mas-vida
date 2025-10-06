import paramiko
import os

from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.services.base_service import BaseService

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

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Sube un archivo al servidor SFTP.
        
        Args:
            local_path: Ruta del archivo local
            remote_path: Ruta destino en el servidor SFTP
            
        Returns:
            bool: True si la subida fue exitosa
        """
        if not self.is_connected:
            logger.error("No hay conexión SFTP activa")
            return False
        
        try:
            # Crear directorios remotos si no existen
            remote_dir = remote_path.rsplit('/', 1)[0]
            try:
                self._create_remote_directory(remote_dir)
            except Exception as e:
                logger.warning(f"No se pudo crear directorio remoto {remote_dir}: {e}")
            
            # Subir archivo
            self.sftp_client.put(local_path, remote_path)
            logger.info(f"Archivo subido exitosamente: {local_path} → {remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error subiendo archivo: {e}")
            return False

    def _create_remote_directory(self, remote_dir: str) -> None:
        """
        Crea un directorio remoto recursivamente.
        
        Args:
            remote_dir: Ruta del directorio a crear
        """
        try:
            # Intentar crear el directorio
            self.sftp_client.mkdir(remote_dir)
        except FileNotFoundError:
            # Si el directorio padre no existe, crearlo recursivamente
            parent_dir = remote_dir.rsplit('/', 1)[0]
            if parent_dir and parent_dir != remote_dir:
                self._create_remote_directory(parent_dir)
                self.sftp_client.mkdir(remote_dir)
        except OSError:
            # El directorio ya existe
            pass

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Descarga un archivo desde el servidor SFTP.
        
        Args:
            remote_path: Ruta del archivo en el servidor SFTP
            local_path: Ruta local donde guardar el archivo
            
        Returns:
            bool: True si la descarga fue exitosa
        """
        if not self.is_connected:
            logger.error("No hay conexión SFTP activa")
            return False
        
        try:
            # Crear directorio local si no existe
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
            
            # Descargar archivo
            self.sftp_client.get(remote_path, local_path)
            logger.info(f"Archivo descargado exitosamente: {remote_path} → {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error descargando archivo: {e}")
            return False

    def list_files(self, remote_dir: str = ".") -> List[str]:
        """
        Lista archivos en un directorio remoto.
        
        Args:
            remote_dir: Directorio remoto a listar
            
        Returns:
            List[str]: Lista de nombres de archivos
        """
        if not self.is_connected:
            logger.error("No hay conexión SFTP activa")
            return []
        
        try:
            files = self.sftp_client.listdir(remote_dir)
            logger.info(f"Listados {len(files)} archivos en {remote_dir}")
            return files
            
        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            return []

    def file_exists(self, remote_path: str) -> bool:
        """
        Verifica si un archivo existe en el servidor SFTP.
        
        Args:
            remote_path: Ruta del archivo a verificar
            
        Returns:
            bool: True si el archivo existe
        """
        if not self.is_connected:
            logger.error("No hay conexión SFTP activa")
            return False
        
        try:
            self.sftp_client.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error verificando archivo: {e}")
            return False

    def load(self, data: List[Dict[str, Any]], **kwargs) -> bool:
        logger.warning("Carga no soportada en SFTPService")
        return False