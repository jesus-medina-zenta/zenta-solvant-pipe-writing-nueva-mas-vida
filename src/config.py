"""
Configuración de la aplicación usando Pydantic para validación.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseConfig(BaseSettings):
    """Configuración para bases de datos PostgreSQL."""

    host: str = Field(default="localhost", description="Host de PostgreSQL")
    port: int = Field(default=5432, description="Puerto de PostgreSQL")
    database: str = Field(default="postgres", description="Nombre de la base de datos")
    user: str = Field(default="postgres", description="Usuario de PostgreSQL")
    password: str = Field(default="", description="Contraseña de PostgreSQL")

    model_config = {
        "env_prefix": "POSTGRES_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    @property
    def connection_string(self) -> str:
        """Retorna la cadena de conexión para PostgreSQL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class BigQueryConfig(BaseSettings):
    """Configuración para Google BigQuery."""

    project_id: str = Field(default="", description="ID del proyecto de Google Cloud")
    dataset: str = Field(default="", description="Dataset de BigQuery")
    table: str = Field(default="", description="Tabla de BigQuery")
    location: str = Field(default="US", description="Ubicación de BigQuery")

    model_config = {
        "env_prefix": "BIGQUERY_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


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


def get_config() -> AppConfig:
    """
    Obtiene la configuración de la aplicación.
    Útil para testing y para evitar errores en importación.
    """
    return AppConfig()


def get_database_config() -> DatabaseConfig:
    """
    Obtiene la configuración de la base de datos.
    """
    return DatabaseConfig()


def get_bigquery_config() -> BigQueryConfig:
    """
    Obtiene la configuración de BigQuery.
    """
    return BigQueryConfig()


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
