#!/usr/bin/env python3
"""
Script para crear el dataset de BigQuery necesario para el pipeline.
"""
import asyncio
from google.cloud import bigquery
from google.cloud.exceptions import Conflict

from src.config import get_bigquery_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def create_dataset():
    """Crea el dataset de BigQuery si no existe."""
    bq_config = get_bigquery_config()
    
    try:
        # Crear cliente de BigQuery
        client = bigquery.Client(project=bq_config.project_id, location=bq_config.location)
        
        # Crear el dataset
        dataset_id = f"{bq_config.project_id}.{bq_config.dataset}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = bq_config.location
        
        # Intentar crear el dataset
        dataset = client.create_dataset(dataset, timeout=30)
        logger.info(f"Dataset {dataset_id} creado exitosamente")
        
    except Conflict:
        logger.info(f"Dataset {dataset_id} ya existe")
    except Exception as e:
        logger.error(f"Error creando dataset: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_dataset())
