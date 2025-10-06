"""
Lógica principal del pipeline ETL.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

#models
from src.models.firestore_records import FirestoreCallRecord, CallOutcome, Document600, Document200

#Services
from src.services.firestore_service import FirestoreService
from src.services.sftp_service import SFTPService
from src.services.file_service import FileService

from .config import (
    get_sftp_config, 
    get_firestore_config, 
    get_file_export_config,
    init_config
)
from .models.data_models import DataRecord
from .utils.logger import get_logger

logger = get_logger(__name__)


class Pipeline:
    """
    Pipeline principal para procesamiento ETL.
    """
    
    def __init__(self):
        #Configs
        self.sftp_config = get_sftp_config()
        self.firestore_config = get_firestore_config()
        #Services
        self.sftp_service = SFTPService(self.sftp_config)
        self.firestore_service = FirestoreService()
        self.file_service = FileService("./temp")
        self.export_config = get_file_export_config()
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
            logger.info("Iniciando extracción de Firestore")
            firestore_data = await self.extract_from_firestore()
            logger.debug(f"Datos extraídos: {len(firestore_data) if firestore_data else 0} registros")
            if not firestore_data:
                logger.warning("No se encontraron datos en Firestore")
                return True
            
            # Paso 2: Transform
            logger.info("Procesando y clasificando documentos...")
            doc_600_list, doc_200_list, errors = self.process_and_classify_documents(firestore_data)

            success = True
            if doc_600_list:
                logger.info(f"Generando archivo 600 con {len(doc_600_list)} registros...")
                success_600 = await self.generate_file_600(doc_600_list)
                success = success and success_600
            
            if doc_200_list:
                logger.info(f"Generando archivo 200 con {len(doc_200_list)} registros...")
                success_200 = await self.generate_file_200(doc_200_list)
                success = success and success_200
            
            if success:
                logger.info("Pipeline completado exitosamente")
            else:
                logger.error("Pipeline completado con errores")
            
            return success
                
        except Exception as e:
            logger.exception(f"Error en el pipeline: {e}")
            return False
        finally:
            self.end_time = datetime.now(timezone.utc)
            duration = (self.end_time - self.start_time).total_seconds()
            logger.info(f"Pipeline finalizado. Duración: {duration:.2f} segundos")
    
    async def extract_from_firestore(self) -> List[Dict[str, Any]]:
        """
        Extrae registros de llamadas desde Firestore.
        SIEMPRE aplica filtros por:
        - Fecha del día actual
        - Agente específico configurado
        """
        try:
            # Validar que tenemos el agent_id
            if not self.firestore_config.agent_id:
                raise ValueError("FIRESTORE_AGENT_ID debe estar configurado")
            
            # Conectar al servicio
            if not self.firestore_service.connect():
                logger.error("No se pudo conectar a Firestore")
                return []
            
            # Extraer con filtros automáticos (día actual + agente)
            documents = await asyncio.to_thread(
                self.firestore_service.extract, 
                get_firestore_config().collection
            )
            
            logger.info(f"Extracción completada: {len(documents)} registros del día actual para agente {self.firestore_config.agent_id}")
            
            return documents
            
        except Exception as e:
            logger.error(f"Error en extracción de Firestore: {e}")
            return []
    
    def process_and_classify_documents(self, raw_records: List[Dict[str, Any]]) -> tuple[List[Document600], List[Document200], int]:
        """
        Procesa registros y los clasifica para archivos 600 y 200.
        PP ahora genera AMBOS archivos (600 Y 200).
        """
        doc_600_list = []
        doc_200_list = []
        errors = 0
        
        for record in raw_records:
            try:
                call_record = FirestoreCallRecord(**record)
                rut = call_record.get_rut()
                
                if not rut:
                    logger.warning(f"Registro sin RUT válido: {call_record.conversation_id}")
                    errors += 1
                    continue
                
                # Obtener outcome final
                final_outcome = call_record.get_final_call_outcome()
                
                if not final_outcome:
                    logger.warning(f"Registro sin outcome: {call_record.conversation_id}")
                    errors += 1
                    continue
                
                # PP genera AMBOS archivos
                if final_outcome == "PP":
                    # 1. Crear documento 600 (Promesa de Pago)
                    due_date = call_record.get_due_date()
                    amount_due = call_record.get_amount_due()
                    
                    if due_date and amount_due:
                        doc_600 = Document600(
                            rut=rut,
                            agent_id=call_record.get_agent_name(),
                            processed_at=call_record.get_processed_datetime(),
                            due_date=due_date,
                            amount_due=amount_due
                        )
                        doc_600_list.append(doc_600)
                        logger.debug(f"Documento 600 creado para: {call_record.conversation_id}")
                    else:
                        logger.warning(f"Promesa de pago sin datos completos: {call_record.conversation_id}")
                        errors += 1
                
                # TODOS los outcomes (incluyendo PP) generan documento 200
                doc_200 = Document200(
                    rut=rut,
                    processed_at=call_record.get_processed_datetime(),
                    codigo_resultado=final_outcome,
                    agent_name=call_record.get_agent_name(),
                    phone_number=call_record.get_phone_number(),
                    call_duration=call_record.call_duration_secs
                )
                doc_200_list.append(doc_200)
                logger.debug(f"Documento 200 ({final_outcome}) creado para: {call_record.conversation_id}")
                    
            except Exception as e:
                logger.error(f"Error procesando registro {record.get('conversation_id', 'unknown')}: {e}")
                errors += 1
        
        logger.info(f"Procesamiento completado: {len(doc_600_list)} archivo 600, {len(doc_200_list)} archivo 200, {errors} errores")
        return doc_600_list, doc_200_list, errors
    
    async def generate_file_600(self, documents: List[Document600]) -> bool:
        """
        Genera archivo 600 con estructura de posiciones fijas.
        """
        try:
            await self.file_service.connect()
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{timestamp}_600zenta.txt"
            
            # Generar contenido con posiciones fijas
            content_lines = [doc.build_line() for doc in documents]
            
            # Crear archivo temporal
            temp_path = self.file_service.base_path / filename
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))
            
            logger.info(f"Archivo 600 generado: {filename} con {len(content_lines)} líneas")
            
            # Subir al SFTP
            remote_path = f"{self.export_config.sftp_txt_path}/{filename}"
            success = await self._upload_to_sftp(str(temp_path), remote_path)
            
            # Limpiar archivo temporal
            if temp_path.exists():
                temp_path.unlink()
            
            return success
            
        except Exception as e:
            logger.error(f"Error generando archivo 600: {e}")
            return False

    async def generate_file_200(self, documents: List[Document200]) -> bool:
        """
        Genera archivo 200 con estructura de posiciones fijas.
        """
        try:
            await self.file_service.connect()
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{timestamp}_200zenta.txt"
            
            # Generar contenido con posiciones fijas
            content_lines = [doc.build_line() for doc in documents]
            
            # Crear archivo temporal
            temp_path = self.file_service.base_path / filename
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))
            
            logger.info(f"Archivo 200 generado: {filename} con {len(content_lines)} líneas")
            
            # Subir al SFTP
            remote_path = f"{self.export_config.sftp_txt_path}/{filename}"
            success = await self._upload_to_sftp(str(temp_path), remote_path)
            
            # Limpiar archivo temporal
            if temp_path.exists():
                temp_path.unlink()
            
            return success
            
        except Exception as e:
            logger.error(f"Error generando archivo 200: {e}")
            return False

    async def _upload_to_sftp(self, local_path: str, remote_path: str) -> bool:
        """
        Sube un archivo al SFTP.
        """
        try:
            # Ejecutar las operaciones SFTP síncronas en un thread separado
            success = await asyncio.to_thread(self._sync_upload_to_sftp, local_path, remote_path)
            
            if success:
                logger.info(f"Archivo subido exitosamente: {remote_path}")
            else:
                logger.error(f"Error subiendo archivo: {remote_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en _upload_to_sftp: {e}")
            return False
    
    def _sync_upload_to_sftp(self, local_path: str, remote_path: str) -> bool:
        """
        Operación síncrona de subida a SFTP.
        """
        try:
            if not self.sftp_service.connect():
                logger.error("No se pudo conectar al servidor SFTP")
                return False
            
            success = self.sftp_service.upload_file(local_path, remote_path)
            return success
            
        except Exception as e:
            logger.error(f"Error en _sync_upload_to_sftp: {e}")
            return False
        finally:
            self.sftp_service.disconnect()