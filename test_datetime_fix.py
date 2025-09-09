#!/usr/bin/env python3
"""
Script para probar que la serialización de datetime funciona correctamente.
Extrae datos con campos datetime y los serializa usando model_dump(mode='json').
"""
import asyncio
import json

from src.services.postgres_service import PostgresService
from src.models.data_models import DataRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_datetime_serialization():
    """Prueba que los datos con datetime se serializan correctamente."""
    postgres_service = PostgresService()
    
    try:
        # Extraer datos de PostgreSQL
        logger.info("Extrayendo datos de PostgreSQL...")
        query = "SELECT * FROM registro LIMIT 5"
        raw_data = await postgres_service.extract(query)
        
        if not raw_data:
            logger.warning("No se encontraron datos")
            return
        
        logger.info("Extraídos %d registros", len(raw_data))
        
        # Transformar a DataRecord
        transformed_data = []
        for row in raw_data:
            try:
                record = DataRecord(**row)
                transformed_data.append(record)
            except Exception as e:
                logger.warning(f"Error transformando registro: {e}")
        
        logger.info("Transformados %d registros", len(transformed_data))
        
        # Serializar usando model_dump(mode='json')
        logger.info("Probando serialización con mode='json'...")
        serialized_data = []
        for record in transformed_data:
            # Esto es lo que se envía a BigQuery
            serialized = record.model_dump(mode='json')
            serialized_data.append(serialized)
        
        # Convertir a JSON para verificar que no hay errores
        json_string = json.dumps(serialized_data, indent=2)
        
        logger.info("✅ Serialización JSON exitosa!")
        logger.info("Primer registro serializado: %s", serialized_data[0])
        
        # Guardar en archivo para inspección
        with open('/tmp/test_datetime_serialization.json', 'w') as f:
            f.write(json_string)
        
        logger.info("📝 Datos guardados en /tmp/test_datetime_serialization.json")
        
    except Exception as e:
        logger.error(f"❌ Error en la prueba: {e}")
        raise
    finally:
        await postgres_service.disconnect()


if __name__ == "__main__":
    asyncio.run(test_datetime_serialization())
