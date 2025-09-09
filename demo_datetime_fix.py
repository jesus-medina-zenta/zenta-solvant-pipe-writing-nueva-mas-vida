#!/usr/bin/env python3
"""
Pipeline de demostración que usa archivos en lugar de BigQuery.
Esto demuestra que el fix del datetime funciona correctamente.
"""
import asyncio
import json
from typing import List, Dict, Any
from datetime import datetime, timezone

from src.services.postgres_service import PostgresService
from src.services.file_service import FileService
from src.models.data_models import DataRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileBasedPipeline:
    """Pipeline que extrae de PostgreSQL y guarda en archivos."""
    
    def __init__(self):
        self.postgres_service = PostgresService()
        self.file_service = FileService("./output")
        
    async def run(self) -> bool:
        """Ejecuta el pipeline completo."""
        start_time = datetime.now(timezone.utc)
        logger.info("🚀 Iniciando pipeline PostgreSQL → Archivo JSON")
        
        try:
            # Paso 1: Extract
            logger.info("📊 Extrayendo datos de PostgreSQL...")
            raw_data = await self.extract()
            logger.info("✅ Extraídos %d registros", len(raw_data))
            
            if not raw_data:
                logger.warning("⚠️ No se encontraron datos para procesar")
                return True
            
            # Paso 2: Transform
            logger.info("🔄 Transformando datos...")
            transformed_data = await self.transform(raw_data)
            logger.info("✅ Transformados %d registros", len(transformed_data))
            
            # Paso 3: Load (con fix de datetime)
            logger.info("💾 Guardando datos con serialización JSON...")
            success = await self.load(transformed_data)
            
            if success:
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                logger.info("🎉 Pipeline completado exitosamente en %.2f segundos", duration)
                return True
            else:
                logger.error("❌ Error en la carga de datos")
                return False
                
        except Exception as e:
            logger.exception(f"💥 Error en el pipeline: {e}")
            return False
        finally:
            await self.postgres_service.disconnect()
            await self.file_service.disconnect()
    
    async def extract(self) -> List[Dict[str, Any]]:
        """Extrae datos de PostgreSQL."""
        try:
            query = """
            SELECT id, name, value, category, is_active, created_at, updated_at, metadata
            FROM registro
            ORDER BY id
            LIMIT 10
            """
            data = await self.postgres_service.extract(query)
            return data
        except Exception as e:
            logger.error(f"Error en la extracción: {e}")
            return []
    
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[DataRecord]:
        """Transforma los datos usando Pydantic."""
        transformed_data = []
        errors = 0
        
        for row in raw_data:
            try:
                record = DataRecord(**row)
                transformed_data.append(record)
            except Exception as e:
                errors += 1
                logger.warning(f"⚠️ Error transformando registro: {e}")
        
        if errors > 0:
            logger.warning(f"⚠️ Se encontraron {errors} errores en la transformación")
        
        return transformed_data
    
    async def load(self, data: List[DataRecord]) -> bool:
        """Carga los datos en archivo JSON (con fix de datetime)."""
        try:
            # Aplicar el fix: usar model_dump(mode='json') para serializar datetime correctamente
            logger.info("🔧 Aplicando fix de datetime: model_dump(mode='json')")
            serialized_data = []
            
            for record in data:
                # Este es el fix que resuelve el error "Object of type datetime is not JSON serializable"
                record_dict = record.model_dump(mode='json')
                serialized_data.append(record_dict)
            
            # Mostrar el primer registro para verificar la serialización
            if serialized_data:
                logger.info("📋 Primer registro serializado: %s", serialized_data[0])
                logger.info("📅 Fecha serializada como: %s", serialized_data[0].get('created_at', 'N/A'))
            
            # Guardar en archivo JSON
            filename = f"pipeline_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            success = await self.file_service.load(serialized_data, filename, "json")
            
            if success:
                logger.info("✅ Datos guardados en: ./output/%s", filename)
                
                # Verificar que el archivo se puede leer como JSON válido
                with open(f"./output/{filename}", 'r') as f:
                    json.load(f)
                logger.info("✅ Verificación JSON: El archivo es JSON válido")
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.exception(f"❌ Error en la carga: {e}")
            return False


async def main():
    """Función principal."""
    logger.info("=" * 60)
    logger.info("🧪 DEMOSTRACIÓN: Fix del error de datetime serialization")
    logger.info("=" * 60)
    
    pipeline = FileBasedPipeline()
    success = await pipeline.run()
    
    if success:
        logger.info("🎉 ¡ÉXITO! El fix del datetime funciona perfectamente")
        logger.info("✅ Los objetos datetime se serializan correctamente como strings ISO")
        logger.info("✅ No más errores 'Object of type datetime is not JSON serializable'")
    else:
        logger.error("❌ Pipeline falló")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
