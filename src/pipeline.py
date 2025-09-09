"""
Lógica principal del pipeline ETL.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .config import init_config, get_database_config, get_bigquery_config
from .services.postgres_service import PostgresService
from .services.bigquery_service import BigQueryService
from .models.data_models import DataRecord
from .utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline:
    """
    Pipeline principal para procesamiento ETL.
    """
    
    def __init__(self):
        """Inicializa el pipeline con los servicios necesarios."""
        self.postgres_service = PostgresService()
        self.bigquery_service = BigQueryService()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
    async def run(self) -> bool:
        """
        Ejecuta el pipeline completo.
        
        Returns:
            bool: True si el pipeline fue exitoso, False en caso contrario
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info("Iniciando ejecución del pipeline")
        
        try:
            # Paso 1: Extract
            logger.info("Iniciando extracción de datos")
            raw_data = await self.extract()
            logger.info(f"Extraídos {len(raw_data)} registros")
            
            if not raw_data:
                logger.warning("No se encontraron datos para procesar")
                return True
            
            # Paso 2: Transform
            logger.info("Iniciando transformación de datos")
            transformed_data = await self.transform(raw_data)
            
            logger.info(f"Transformados {len(transformed_data)} registros")
            
            # Paso 3: Load
            logger.info("Iniciando carga de datos")
            success = await self.load(transformed_data)
            
            if success:
                logger.info("Pipeline completado exitosamente")
                return True
            else:
                logger.error("Error en la carga de datos")
                return False
                
        except Exception as e:
            logger.exception(f"Error en el pipeline: {e}")
            return False
        finally:
            self.end_time = datetime.now(timezone.utc)
            duration = (self.end_time - self.start_time).total_seconds()
            logger.info(f"Pipeline finalizado. Duración: {duration:.2f} segundos")
    
    async def extract(self) -> List[Dict[str, Any]]:
        """
        Extrae datos de la fuente.
        
        Returns:
            List[Dict[str, Any]]: Datos extraídos
        """
        try:
            # Aquí puedes personalizar la consulta según tus necesidades
            query = """
            SELECT *
            FROM registro
            """
            
            data = await self.postgres_service.extract(query)
            return data
            
        except Exception as e:
            logger.error(f"Error en la extracción: {e}")
            return []
    
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[DataRecord]:
        """
        Transforma los datos extraídos.
        
        Args:
            raw_data: Datos en bruto extraídos
            
        Returns:
            List[DataRecord]: Datos transformados y validados
        """
        transformed_data = []
        errors = 0
        
        for row in raw_data:
            try:
                # Validar y transformar usando Pydantic
                record = DataRecord(**row)
                transformed_data.append(record)
                
            except Exception as e:
                errors += 1
                logger.warning(f"Error transformando registro: {e}")
                
                # Si TODOS los registros son inválidos, no continuar
                if errors == len(raw_data) and len(raw_data) > 0:
                    logger.error(f"Todos los registros son inválidos ({errors} errores)")
                    return []
        
        if errors > 0:
            logger.warning(f"Se encontraron {errors} errores en la transformación")
        
        return transformed_data
    
    async def load(self, data: List[DataRecord]) -> bool:
        """
        Carga los datos transformados al destino.
        
        Args:
            data: Datos transformados para cargar
            
        Returns:
            bool: True si la carga fue exitosa
        """
        try:
            # Procesar en lotes para mejorar rendimiento
            app_config = init_config()
            batch_size = app_config.batch_size
            total_batches = (len(data) + batch_size - 1) // batch_size
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                logger.info(f"Procesando lote {batch_num}/{total_batches} ({len(batch)} registros)")
                
                # Convertir a diccionarios para BigQuery (serializando fechas como ISO strings)
                batch_dicts = [record.model_dump(mode='json') for record in batch]
                
                success = await self.bigquery_service.load(batch_dicts)
                if not success:
                    logger.error(f"Error cargando lote {batch_num}")
                    return False
            
            logger.info("Todos los lotes cargados exitosamente")
            return True
            
        except Exception as e:
            logger.exception(f"Error en la carga: {e}")
            return False
    
    async def validate_data_quality(self, data: List[DataRecord]) -> bool:
        """
        Valida la calidad de los datos transformados.
        
        Args:
            data: Datos a validar
            
        Returns:
            bool: True si los datos pasan las validaciones
        """
        if not data:
            logger.warning("No hay datos para validar")
            return False
        
        # Validaciones básicas
        null_count = sum(1 for record in data if not record.is_valid())
        null_percentage = (null_count / len(data)) * 100
        
        if null_percentage > 5:  # Más del 5% de registros inválidos
            logger.error(f"Demasiados registros inválidos: {null_percentage:.2f}%")
            return False
        
        logger.info(f"Validación de calidad pasada. Registros inválidos: {null_percentage:.2f}%")
        return True
