"""
Servicio para manejo de archivos (CSV, JSON, Parquet, etc.).
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from .base_service import BaseService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FileService(BaseService):
    """
    Servicio para manejar operaciones con archivos.
    Soporta CSV, JSON, Parquet y Excel.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Inicializa el servicio de archivos.
        
        Args:
            base_path: Ruta base para operaciones de archivos
        """
        super().__init__()
        self.base_path = Path(base_path) if base_path else Path.cwd()
    
    
    async def disconnect(self) -> None:
        """Desconecta el servicio (no hay recursos que cerrar)."""
        self.is_connected = False
        logger.info("Servicio de archivos desconectado")
    
    async def extract(self, file_path: str, file_type: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrae datos de un archivo.
        
        Args:
            file_path: Ruta del archivo relativa al base_path
            file_type: Tipo de archivo (csv, json, parquet, excel). Auto-detecta si no se especifica
            **kwargs: Parámetros adicionales para pandas
            
        Returns:
            List[Dict[str, Any]]: Datos extraídos
        """
        if not self.is_connected:
            await self.connect()
        
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {full_path}")
        
        # Auto-detectar tipo de archivo
        if not file_type:
            file_type = full_path.suffix.lower().lstrip('.')
        
        try:
            loop = asyncio.get_event_loop()
            
            if file_type == 'csv':
                df = await loop.run_in_executor(None, pd.read_csv, str(full_path), **kwargs)
            elif file_type == 'json':
                df = await loop.run_in_executor(None, pd.read_json, str(full_path), **kwargs)
            elif file_type == 'parquet':
                df = await loop.run_in_executor(None, pd.read_parquet, str(full_path), **kwargs)
            elif file_type in ['xlsx', 'xls', 'excel']:
                df = await loop.run_in_executor(None, pd.read_excel, str(full_path), **kwargs)
            else:
                raise ValueError(f"Tipo de archivo no soportado: {file_type}")
            
            # Convertir a lista de diccionarios
            data = df.to_dict('records')
            logger.info("Extraídos %d registros de %s", len(data), full_path)
            return data
            
        except Exception as e:
            logger.error(f"Error extrayendo datos de archivo: {e}")
            raise

    async def connect(self) -> bool:
        """
        Verifica que el directorio base existe y es accesible.
        
        Returns:
            bool: True si el directorio es accesible
        """
        try:
            # Crear directorio si no existe
            self.base_path.mkdir(parents=True, exist_ok=True)
            
            # Verificar que es accesible
            if self.base_path.exists() and self.base_path.is_dir():
                self.is_connected = True
                logger.info(f"Directorio de archivos accesible: {self.base_path}")
                return True
            else:
                logger.error(f"Directorio no accesible: {self.base_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error verificando directorio de archivos: {e}")
            self.is_connected = False
            return False

    async def extract(self, file_path: str, file_type: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrae datos de un archivo.
        
        Args:
            file_path: Ruta del archivo
            file_type: Tipo de archivo (csv, json, etc.)
            
        Returns:
            List[Dict[str, Any]]: Datos extraídos
        """
        try:
            full_path = self.base_path / file_path
            
            if not full_path.exists():
                logger.error(f"Archivo no encontrado: {full_path}")
                return []
            
            # Determinar tipo de archivo si no se especifica
            if not file_type:
                file_type = full_path.suffix.lower().lstrip('.')
            
            if file_type == 'csv':
                import pandas as pd
                df = pd.read_csv(full_path)
                return df.to_dict('records')
            elif file_type == 'json':
                import json
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
            else:
                logger.error(f"Tipo de archivo no soportado: {file_type}")
                return []
                
        except Exception as e:
            logger.error(f"Error extrayendo archivo: {e}")
            return []

    async def load(self, data: List[Dict[str, Any]], file_path: str, 
                   file_type: Optional[str] = None, **kwargs) -> bool:
        """
        Carga datos en un archivo.
        
        Args:
            data: Datos a cargar
            file_path: Ruta del archivo
            file_type: Tipo de archivo
            
        Returns:
            bool: True si fue exitoso
        """
        try:
            full_path = self.base_path / file_path
            
            # Crear directorio padre si no existe
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Determinar tipo de archivo si no se especifica
            if not file_type:
                file_type = full_path.suffix.lower().lstrip('.')
            
            if file_type == 'csv':
                import pandas as pd
                df = pd.DataFrame(data)
                df.to_csv(full_path, index=False, encoding='utf-8')
            elif file_type == 'json':
                import json
                with open(full_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                logger.error(f"Tipo de archivo no soportado: {file_type}")
                return False
            
            logger.info(f"Archivo creado exitosamente: {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creando archivo: {e}")
            return False

    
    async def load(self, data: List[Dict[str, Any]], file_path: str, 
                   file_type: Optional[str] = None, **kwargs) -> bool:
        """
        Carga datos en un archivo.
        
        Args:
            data: Datos a cargar
            file_path: Ruta del archivo relativa al base_path
            file_type: Tipo de archivo (csv, json, parquet, excel)
            **kwargs: Parámetros adicionales para pandas
            
        Returns:
            bool: True si la carga fue exitosa
        """
        if not data:
            logger.warning("No hay datos para cargar en archivo")
            return True
        
        if not self.is_connected:
            await self.connect()
        
        full_path = self.base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Auto-detectar tipo de archivo
        if not file_type:
            file_type = full_path.suffix.lower().lstrip('.')
        
        try:
            loop = asyncio.get_event_loop()
            df = pd.DataFrame(data)
            
            if file_type == 'csv':
                await loop.run_in_executor(
                    None, 
                    lambda: df.to_csv(str(full_path), index=False, **kwargs)
                )
            elif file_type == 'json':
                await loop.run_in_executor(
                    None,
                    lambda: df.to_json(str(full_path), orient='records', **kwargs)
                )
            elif file_type == 'parquet':
                await loop.run_in_executor(
                    None,
                    lambda: df.to_parquet(str(full_path), **kwargs)
                )
            elif file_type in ['xlsx', 'excel']:
                await loop.run_in_executor(
                    None,
                    lambda: df.to_excel(str(full_path), index=False, **kwargs)
                )
            else:
                raise ValueError(f"Tipo de archivo no soportado: {file_type}")
            
            logger.info("Cargados %d registros en %s", len(data), full_path)
            return True
            
        except Exception as e:
            logger.error(f"Error cargando datos en archivo: {e}")
            return False
    
    async def append_to_file(self, data: List[Dict[str, Any]], file_path: str, 
                            file_type: Optional[str] = None) -> bool:
        """
        Añade datos a un archivo existente.
        
        Args:
            data: Datos a añadir
            file_path: Ruta del archivo
            file_type: Tipo de archivo
            
        Returns:
            bool: True si fue exitoso
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            return await self.load(data, file_path, file_type)
        
        # Auto-detectar tipo de archivo
        if not file_type:
            file_type = full_path.suffix.lower().lstrip('.')
        
        try:
            if file_type == 'csv':
                loop = asyncio.get_event_loop()
                df = pd.DataFrame(data)
                await loop.run_in_executor(
                    None,
                    lambda: df.to_csv(str(full_path), mode='a', header=False, index=False)
                )
            elif file_type == 'json':
                # Para JSON, necesitamos leer, combinar y reescribir
                existing_data = await self.extract(file_path, file_type)
                combined_data = existing_data + data
                return await self.load(combined_data, file_path, file_type)
            else:
                logger.warning(f"Append no soportado para tipo {file_type}, usando load")
                return await self.load(data, file_path, file_type)

            logger.info("Añadidos %d registros a %s", len(data), full_path)
            return True
            
        except Exception as e:
            logger.error(f"Error añadiendo datos a archivo: {e}")
            return False
    
    async def list_files(self, pattern: str = "*", recursive: bool = False) -> List[str]:
        """
        Lista archivos en el directorio base.
        
        Args:
            pattern: Patrón de archivos a buscar
            recursive: Si buscar recursivamente
            
        Returns:
            List[str]: Lista de rutas de archivos
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if recursive:
                files = list(self.base_path.rglob(pattern))
            else:
                files = list(self.base_path.glob(pattern))
            
            # Convertir a rutas relativas
            relative_paths = [str(f.relative_to(self.base_path)) for f in files if f.is_file()]
            
            logger.info("Encontrados %d archivos", len(relative_paths))
            return relative_paths

        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            raise
    
    async def delete_file(self, file_path: str) -> bool:
        """
        Elimina un archivo.
        
        Args:
            file_path: Ruta del archivo a eliminar
            
        Returns:
            bool: True si fue eliminado exitosamente
        """
        full_path = self.base_path / file_path
        
        try:
            if full_path.exists():
                full_path.unlink()
                logger.info("Archivo eliminado: %s", full_path)
            else:
                logger.warning("Archivo no existe: %s", full_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Obtiene información de un archivo.
        
        Args:
            file_path: Ruta del archivo
            
        Returns:
            Dict[str, Any]: Información del archivo
        """
        full_path = self.base_path / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {full_path}")
        
        stat = full_path.stat()
        
        return {
            "size_bytes": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "is_file": full_path.is_file(),
            "suffix": full_path.suffix,
            "name": full_path.name
        }
