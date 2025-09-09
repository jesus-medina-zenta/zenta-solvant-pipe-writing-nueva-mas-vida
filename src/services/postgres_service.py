"""
Servicio para conexiones a PostgreSQL.
"""
import asyncio
from typing import List, Dict, Any, Optional
import asyncpg
from asyncpg import Pool

from ..config import get_database_config
from .base_service import BaseService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PostgresService(BaseService):
    """
    Servicio para manejar conexiones y operaciones con PostgreSQL.
    """
    
    def __init__(self):
        """Inicializa el servicio de PostgreSQL."""
        super().__init__()
        self.pool: Optional[Pool] = None
        self.db_config = get_database_config()
        self.connection_string = self.db_config.connection_string
        
    async def connect(self) -> bool:
        """
        Establece el pool de conexiones a PostgreSQL.
        
        Returns:
            bool: True si la conexión fue exitosa
        """
        try:
            logger.info("Conectando a PostgreSQL...")
            
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60,
                server_settings={
                    'jit': 'off'  # Mejora rendimiento para consultas simples
                }
            )
            
            # Verificar conexión
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            self.is_connected = True
            logger.info("Conexión a PostgreSQL establecida exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a PostgreSQL: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """Cierra el pool de conexiones."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.is_connected = False
            logger.info("Conexión a PostgreSQL cerrada")
    
    async def extract(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extrae datos de PostgreSQL usando una consulta.
        
        Args:
            query: Consulta SQL a ejecutar
            parameters: Parámetros para la consulta
            
        Returns:
            List[Dict[str, Any]]: Resultados de la consulta
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.pool:
            raise RuntimeError("No hay conexión disponible a PostgreSQL")
        
        try:
            async with self.pool.acquire() as conn:
                if parameters:
                    rows = await conn.fetch(query, *parameters.values())
                else:
                    rows = await conn.fetch(query)
                
                # Convertir a lista de diccionarios
                result = [dict(row) for row in rows]
                logger.info(f"Extraídos {len(result)} registros de PostgreSQL")
                return result
                
        except Exception as e:
            logger.error(f"Error extrayendo datos de PostgreSQL: {e}")
            raise
    
    async def load(self, data: List[Dict[str, Any]], table: str, 
                   schema: str = "public", on_conflict: str = "REPLACE") -> bool:
        """
        Carga datos en una tabla de PostgreSQL.
        
        Args:
            data: Datos a insertar
            table: Nombre de la tabla
            schema: Esquema de la tabla
            on_conflict: Estrategia para conflictos (REPLACE, IGNORE)
            
        Returns:
            bool: True si la carga fue exitosa
        """
        if not data:
            logger.warning("No hay datos para cargar en PostgreSQL")
            return True
        
        if not self.is_connected:
            await self.connect()
        
        if not self.pool:
            raise RuntimeError("No hay conexión disponible a PostgreSQL")
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Obtener columnas de la primera fila
                    columns = list(data[0].keys())
                    table_name = f"{schema}.{table}"
                    
                    # Preparar la consulta de inserción
                    placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
                    columns_str = ", ".join(columns)
                    
                    if on_conflict == "REPLACE":
                        conflict_clause = f"ON CONFLICT DO UPDATE SET {', '.join([f'{col} = EXCLUDED.{col}' for col in columns])}"
                    else:
                        conflict_clause = "ON CONFLICT DO NOTHING"
                    
                    query = f"""
                        INSERT INTO {table_name} ({columns_str})
                        VALUES ({placeholders})
                        {conflict_clause}
                    """
                    
                    # Insertar datos en lotes
                    batch_size = 1000
                    for i in range(0, len(data), batch_size):
                        batch = data[i:i + batch_size]
                        
                        # Preparar valores para el lote
                        values = [[row[col] for col in columns] for row in batch]
                        
                        await conn.executemany(query, values)
                        logger.debug(f"Insertado lote de {len(batch)} registros")
            
            logger.info(f"Cargados {len(data)} registros en {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error cargando datos en PostgreSQL: {e}")
            return False
    
    async def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Ejecuta una consulta que no retorna datos (INSERT, UPDATE, DELETE).
        
        Args:
            query: Consulta SQL a ejecutar
            parameters: Parámetros para la consulta
            
        Returns:
            bool: True si la ejecución fue exitosa
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.pool:
            raise RuntimeError("No hay conexión disponible a PostgreSQL")
        
        try:
            async with self.pool.acquire() as conn:
                if parameters:
                    await conn.execute(query, *parameters.values())
                else:
                    await conn.execute(query)
            
            logger.info("Consulta ejecutada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            return False
    
    async def get_table_schema(self, table: str, schema: str = "public") -> List[Dict[str, str]]:
        """
        Obtiene el esquema de una tabla.
        
        Args:
            table: Nombre de la tabla
            schema: Esquema de la tabla
            
        Returns:
            List[Dict[str, str]]: Información de columnas
        """
        query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """
        
        return await self.extract(query, {"schema": schema, "table": table})
