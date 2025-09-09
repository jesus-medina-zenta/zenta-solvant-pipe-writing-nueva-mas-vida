"""
Servicio para conexiones a Google BigQuery.
"""
import asyncio
from typing import List, Dict, Any, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from ..config import get_bigquery_config
from .base_service import BaseService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BigQueryService(BaseService):
    """
    Servicio para manejar conexiones y operaciones con Google BigQuery.
    """
    
    def __init__(self):
        """Inicializa el servicio de BigQuery."""
        super().__init__()
        self.client: Optional[bigquery.Client] = None
        self.bq_config = get_bigquery_config()
        self.project_id = self.bq_config.project_id
        self.dataset_id = self.bq_config.dataset
        self.table_id = self.bq_config.table
        self.location = self.bq_config.location
        
    async def connect(self) -> bool:
        """
        Establece la conexión con BigQuery.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            logger.info("Conectando a BigQuery...")
            
            # Ejecutar en thread pool ya que el cliente de BigQuery es síncrono
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None, 
                lambda: bigquery.Client(project=self.project_id, location=self.location)
            )
            
            # Verificar conexión listando datasets
            await loop.run_in_executor(None, lambda: list(self.client.list_datasets(max_results=1)))
            
            self.is_connected = True
            logger.info("Conexión a BigQuery establecida exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a BigQuery: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """Cierra la conexión con BigQuery."""
        if self.client:
            # BigQuery client no requiere cierre explícito
            self.client = None
            self.is_connected = False
            logger.info("Conexión a BigQuery cerrada")
    
    async def extract(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extrae datos de BigQuery usando una consulta.
        
        Args:
            query: Consulta SQL a ejecutar
            parameters: Parámetros para la consulta
            
        Returns:
            List[Dict[str, Any]]: Resultados de la consulta
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.client:
            raise RuntimeError("No hay conexión disponible a BigQuery")
        
        try:
            loop = asyncio.get_event_loop()
            
            # Configurar la consulta
            job_config = bigquery.QueryJobConfig()
            if parameters:
                # Convertir parámetros a formato BigQuery
                job_config.query_parameters = [
                    bigquery.ScalarQueryParameter(key, "STRING", value)
                    for key, value in parameters.items()
                ]
            
            # Ejecutar consulta
            query_job = await loop.run_in_executor(
                None,
                lambda: self.client.query(query, job_config=job_config)
            )
            
            # Obtener resultados
            results = await loop.run_in_executor(None, query_job.result)
            
            # Convertir a lista de diccionarios
            data = await loop.run_in_executor(
                None,
                lambda: [dict(row) for row in results]
            )
            
            logger.info(f"Extraídos {len(data)} registros de BigQuery")
            return data
            
        except Exception as e:
            logger.error(f"Error extrayendo datos de BigQuery: {e}")
            raise
    
    async def load(self, data: List[Dict[str, Any]], table: Optional[str] = None,
                   write_disposition: str = "WRITE_APPEND") -> bool:
        """
        Carga datos en una tabla de BigQuery.
        
        Args:
            data: Datos a insertar
            table: Nombre de la tabla (opcional, usa config por defecto)
            write_disposition: Modo de escritura (WRITE_APPEND, WRITE_TRUNCATE, WRITE_EMPTY)
            
        Returns:
            bool: True si la carga fue exitosa
        """
        if not data:
            logger.warning("No hay datos para cargar en BigQuery")
            return True
        
        if not self.is_connected:
            await self.connect()
        
        if not self.client:
            raise RuntimeError("No hay conexión disponible a BigQuery")
        
        # Crear dataset si no existe
        await self.create_dataset_if_not_exists()
        
        table_name = table or self.table_id
        dataset_ref = self.client.dataset(self.dataset_id, project=self.project_id)
        table_ref = dataset_ref.table(table_name)
        
        try:
            loop = asyncio.get_event_loop()
            
            # Configurar el job de carga
            job_config = bigquery.LoadJobConfig(
                write_disposition=write_disposition,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                autodetect=True,  # Auto-detectar esquema si la tabla no existe
                create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED
            )
            
            logger.info(f"Intentando cargar en: {self.project_id}.{self.dataset_id}.{table_name}")
            logger.info(f"Location configurada: {self.location}")
            logger.info(f"Table ref completa: {table_ref}")
            
            # Cargar datos
            load_job = await loop.run_in_executor(
                None,
                lambda: self.client.load_table_from_json(
                    data, table_ref, job_config=job_config
                )
            )
            
            # Esperar a que termine el job
            await loop.run_in_executor(None, load_job.result)
            
            logger.info(f"Cargados {len(data)} registros en {table_ref}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando datos en BigQuery: {e}")
            return False
    
    async def create_table_if_not_exists(self, schema: List[bigquery.SchemaField], 
                                        table: Optional[str] = None) -> bool:
        """
        Crea una tabla si no existe.
        
        Args:
            schema: Esquema de la tabla
            table: Nombre de la tabla (opcional)
            
        Returns:
            bool: True si la tabla fue creada o ya existía
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.client:
            raise RuntimeError("No hay conexión disponible a BigQuery")
        
        table_name = table or self.table_id
        table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
        
        try:
            loop = asyncio.get_event_loop()
            
            # Verificar si la tabla existe
            try:
                await loop.run_in_executor(None, self.client.get_table, table_ref)
                logger.info(f"La tabla {table_ref} ya existe")
                return True
            except NotFound:
                pass
            
            # Crear la tabla
            table = bigquery.Table(table_ref, schema=schema)
            await loop.run_in_executor(None, self.client.create_table, table)
            
            logger.info(f"Tabla {table_ref} creada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error creando tabla en BigQuery: {e}")
            return False
    
    async def delete_table_data(self, table: Optional[str] = None, 
                               where_clause: Optional[str] = None) -> bool:
        """
        Elimina datos de una tabla.
        
        Args:
            table: Nombre de la tabla (opcional)
            where_clause: Cláusula WHERE para filtrar (opcional)
            
        Returns:
            bool: True si la eliminación fue exitosa
        """
        table_name = table or self.table_id
        table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
        
        query = f"DELETE FROM `{table_ref}`"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        try:
            await self.extract(query)
            logger.info(f"Datos eliminados de {table_ref}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando datos de BigQuery: {e}")
            return False
    
    async def get_table_info(self, table: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene información de una tabla.
        
        Args:
            table: Nombre de la tabla (opcional)
            
        Returns:
            Dict[str, Any]: Información de la tabla
        """
        if not self.is_connected:
            await self.connect()
        
        table_name = table or self.table_id
        table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
        
        try:
            loop = asyncio.get_event_loop()
            table_obj = await loop.run_in_executor(None, self.client.get_table, table_ref)
            
            return {
                "num_rows": table_obj.num_rows,
                "num_bytes": table_obj.num_bytes,
                "created": table_obj.created,
                "modified": table_obj.modified,
                "schema": [{"name": field.name, "type": field.field_type} for field in table_obj.schema]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información de tabla: {e}")
            raise
    
    async def create_dataset_if_not_exists(self) -> bool:
        """
        Crea el dataset si no existe.
        
        Returns:
            bool: True si el dataset fue creado o ya existía
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.client:
            raise RuntimeError("No hay conexión disponible a BigQuery")
        
        try:
            loop = asyncio.get_event_loop()
            
            # Verificar si el dataset existe
            dataset_ref = self.client.dataset(self.dataset_id, project=self.project_id)
            logger.info(f"Verificando dataset: {self.project_id}:{self.dataset_id} en ubicación {self.location}")
            
            try:
                dataset_obj = await loop.run_in_executor(None, self.client.get_dataset, dataset_ref)
                logger.info(f"Dataset encontrado: {dataset_obj.dataset_id} en {dataset_obj.location}")
                return True
            except NotFound:
                logger.info(f"Dataset no encontrado, creando uno nuevo...")
            except Exception as e:
                logger.warning(f"Error verificando dataset (continuando con creación): {e}")
            
            # Crear el dataset
            logger.info(f"Creando dataset {self.project_id}:{self.dataset_id} en ubicación {self.location}")
            try:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset.description = "Dataset creado automáticamente por el pipeline ETL"
                
                created_dataset = await loop.run_in_executor(None, self.client.create_dataset, dataset)
                logger.info(f"Dataset creado exitosamente: {created_dataset.dataset_id} en {created_dataset.location}")
                return True
                
            except Exception as create_error:
                if "already exists" in str(create_error).lower():
                    logger.info(f"Dataset ya existe (creación concurrente): {create_error}")
                    return True
                else:
                    logger.error(f"Error creando dataset: {create_error}")
                    # Intentar continuar de todos modos
                    return True
            
        except Exception as e:
            logger.error(f"Error creando dataset en BigQuery: {e}")
            return False
