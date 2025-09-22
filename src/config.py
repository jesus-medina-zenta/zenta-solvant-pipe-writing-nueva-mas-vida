"""
Configuración de la aplicación usando Pydantic para validación.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field



class AppConfig(BaseSettings):
    """Configuración principal de la aplicación."""

    # Configuración general
    app_name: str = Field(default="zenta-template-pipe-python", description="Nombre de la aplicación")
    log_level: str = Field(default="INFO", description="Nivel de logging")
    environment: str = Field(default="dev", description="Entorno de ejecución")

    # Configuración de procesamiento
    batch_size: int = Field(default=1000, description="Tamaño del lote para procesamiento")
    max_retries: int = Field(default=3, description="Número máximo de reintentos")
    retry_delay: int = Field(default=5, description="Delay entre reintentos en segundos")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignora variables de entorno adicionales
    }

class SFTPConfig(BaseSettings):
    host: str
    port: int
    username: str
    password: str

    model_config = {
        "env_prefix": "SFTP_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

class FirestoreConfig(BaseSettings):
    project_id: str
    collection: str
    database: str = "" 

    model_config = {
        "env_prefix": "FIRESTORE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

class FileExportConfig(BaseSettings):
    """Configuración para exportación de archivos."""
    
    csv_filename_template: str = Field(default="export_{timestamp}.csv", description="Template para nombres de CSV")
    txt1_filename_template: str = Field(default="report1_{timestamp}.txt", description="Template para primer TXT")
    txt2_filename_template: str = Field(default="report2_{timestamp}.txt", description="Template para segundo TXT")
    audio_filename_template: str = Field(default="conversation_{conversation_id}.{extension}", description="Template para archivos de audio")
    
    sftp_csv_path: str = Field(default="/exports/csv", description="Ruta SFTP para archivos CSV")
    sftp_txt_path: str = Field(default="/exports/txt", description="Ruta SFTP para archivos TXT")
    sftp_audio_path: str = Field(default="/exports/audio", description="Ruta SFTP para archivos de audio")
    
    model_config = {
        "env_prefix": "EXPORT_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

def get_config() -> AppConfig:
    """
    Obtiene la configuración de la aplicación.
    Útil para testing y para evitar errores en importación.
    """
    return AppConfig()


def get_sftp_config() -> SFTPConfig:
    return SFTPConfig()

def get_firestore_config() -> FirestoreConfig:
    return FirestoreConfig()

def get_file_export_config() -> FileExportConfig:
    """Obtiene la configuración de exportación de archivos."""
    return FileExportConfig()


# Instancia global de configuración (solo se crea cuando se necesita)
config: Optional[AppConfig] = None


def init_config() -> AppConfig:
    """
    Inicializa la configuración global.
    """
    global config
    if config is None:
        config = AppConfig()
    return config
