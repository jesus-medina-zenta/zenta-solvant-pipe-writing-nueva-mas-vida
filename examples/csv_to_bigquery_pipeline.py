"""
Ejemplo de pipeline personalizado para extraer datos de CSV y cargar a BigQuery.
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime

from src.config import init_config
from src.services.file_service import FileService
from src.services.bigquery_service import BigQueryService
from src.models.data_models import DataRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CSVToBigQueryPipeline:
    """
    Pipeline personalizado que extrae datos de CSV y los carga en BigQuery.
    """
    
    def __init__(self, csv_path: str, table_name: str):
        """
        Inicializa el pipeline.
        
        Args:
            csv_path: Ruta al archivo CSV
            table_name: Nombre de la tabla de destino en BigQuery
        """
        self.csv_path = csv_path
        self.table_name = table_name
        self.file_service = FileService("./data")
        self.bigquery_service = BigQueryService()
        
    async def run(self) -> bool:
        """
        Ejecuta el pipeline completo.
        
        Returns:
            bool: True si fue exitoso
        """
        try:
            logger.info(f"Iniciando pipeline CSV -> BigQuery para {self.csv_path}")
            
            # Extraer datos del CSV
            raw_data = await self.file_service.extract(self.csv_path, "csv")
            logger.info(f"Extraídos {len(raw_data)} registros del CSV")
            
            if not raw_data:
                logger.warning("No hay datos para procesar")
                return True
            
            # Transformar y validar datos
            transformed_data = []
            for row in raw_data:
                try:
                    # Adaptar los datos al modelo
                    record_data = {
                        "id": int(row.get("id", 0)),
                        "name": str(row.get("name", "")),
                        "value": float(row.get("value", 0.0)) if row.get("value") else None,
                        "category": row.get("category"),
                        "is_active": bool(row.get("is_active", True)),
                        "created_at": datetime.now(datetime.timezone.utc)
                    }
                    
                    record = DataRecord(**record_data)
                    transformed_data.append(record)
                    
                except Exception as e:
                    logger.warning(f"Error transformando registro: {e}")
                    continue
            
            logger.info(f"Transformados {len(transformed_data)} registros válidos")
            
            # Cargar a BigQuery
            data_dicts = [record.model_dump() for record in transformed_data]
            success = await self.bigquery_service.load(data_dicts, self.table_name)
            
            if success:
                logger.info("Pipeline completado exitosamente")
                return True
            else:
                logger.error("Error cargando datos a BigQuery")
                return False
                
        except Exception as e:
            logger.exception(f"Error en pipeline: {e}")
            return False


async def main():
    """Función principal de ejemplo."""
    pipeline = CSVToBigQueryPipeline("ventas.csv", "ventas_procesadas")
    success = await pipeline.run()
    
    if success:
        print("✅ Pipeline ejecutado exitosamente")
    else:
        print("❌ Pipeline falló")


if __name__ == "__main__":
    asyncio.run(main())
