"""
Lógica principal del pipeline ETL.
"""
import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

#models
from src.models.firestore_records import (
    ClientData,
    Document200,
    Document600,
    FirestoreCallRecord,
    format_phone_9_digits,
)

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
        # Si viene, el reporte se arma solo con esa carga (ej. "24092026-f5231027-...")
        self.report_carga_id = os.getenv("REPORT_CARGA_ID", "").strip()

    async def run(self) -> bool:
        """
        Ejecuta el pipeline completo.
        
        Returns:
            bool: True si el pipeline fue exitoso, False en caso contrario
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info("Iniciando ejecución del pipeline")
        
        try:
            if self.report_carga_id:
                # Reporte de una sola carga: todas sus personas, contestaran o no
                logger.info(f"Reporte por carga: {self.report_carga_id}")
                if not self.firestore_service.connect():
                    logger.error("No se pudo conectar a Firestore")
                    return False
                source_records = await asyncio.to_thread(
                    self.firestore_service.get_source_records_by_carga, self.report_carga_id)
                if not source_records:
                    logger.warning(f"La carga {self.report_carga_id} no tiene registros")
                    return True
                firestore_data = await asyncio.to_thread(
                    self.firestore_service.get_calls_by_track_ids, list(source_records))
            else:
                # Paso 1: Extract
                logger.info("Iniciando extracción de Firestore")
                firestore_data = await self.extract_from_firestore()
                logger.debug(f"Datos extraídos: {len(firestore_data) if firestore_data else 0} registros")
                if not firestore_data:
                    logger.warning("No se encontraron datos en Firestore")
                    return True

                # Paso 2: Filas originales del archivo del cliente, para cruzar el reporte con su base
                source_records = await asyncio.to_thread(
                    self.firestore_service.get_source_records,
                    [(r.get('dynamic_variables') or {}).get('track_id') for r in firestore_data],
                )

            # Paso 3: Transform
            logger.info("Procesando y clasificando documentos...")
            doc_600_list, doc_200_list, errors = self.process_and_classify_documents(firestore_data, source_records)
            if self.report_carga_id:
                doc_200_list += self.build_not_contacted_rows(firestore_data, source_records)

            success = True
            if doc_600_list:
                logger.info(f"Generando Excel PP con {len(doc_600_list)} registros...")
                success_pp = await self.generate_excel_pp(doc_600_list)
                success = success and success_pp

            if doc_200_list:
                logger.info(f"Generando Excel de todos los resultados con {len(doc_200_list)} registros...")
                success_todos = await self.generate_excel_todos(doc_200_list)
                success = success and success_todos
            
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
    
    def build_not_contacted_rows(
        self,
        calls: List[Dict[str, Any]],
        source_records: Dict[str, Dict[str, Any]],
    ) -> List[Document200]:
        """
        Filas NC para las personas de la carga sin llamada registrada: ElevenLabs
        no avisa de las llamadas que no se contestan, así que no quedan en
        registros_llamadas.
        """
        called = {(c.get('dynamic_variables') or {}).get('track_id') for c in calls}
        rows = []
        for track_id, source in source_records.items():
            if track_id in called:
                continue
            cliente = self.build_client_data(None, source)
            if not cliente:
                continue
            processed = str(source.get('processed_at') or source.get('fecha') or '')
            try:
                processed_at = datetime.fromisoformat(processed.replace('Z', '+00:00'))
            except ValueError:
                processed_at = datetime.now(timezone.utc)
            rows.append(Document200(
                cliente=cliente,
                processed_at=processed_at,
                codigo_resultado="NC",
                agent_name="ZNT_NMV",
                conversation_id="",
            ))
        logger.info(f"{len(rows)} personas de la carga sin llamada contestada (NC)")
        return rows

    @staticmethod
    def build_client_data(call_record: Optional[FirestoreCallRecord], source: Optional[Dict[str, Any]]) -> Optional[ClientData]:
        """
        Datos del deudor tal como venían en el archivo del cliente. Si la fila de
        origen no se encuentra (llamadas antiguas o sueltas), usa las variables
        dinámicas de la llamada.
        """
        metadata = (source or {}).get('metadata_user') or {}
        variables = call_record.dynamic_variables if call_record else {}

        rut = str(metadata.get('rut_deudor') or metadata.get('rut') or variables.get('rut_deudor') or '').strip()
        if not rut:
            return None

        monto_digits = ''.join(ch for ch in str(metadata.get('deuda_cotizaciones') or '') if ch.isdigit())
        return ClientData(
            rut=rut,
            nombre=str(metadata.get('nombre_deudor') or variables.get('name') or ''),
            ciudad=str(metadata.get('ciudad') or ''),
            telefono=format_phone_9_digits(
                (source or {}).get('phone_number') or (call_record.get_phone_number() if call_record else '')),
            monto_deuda=int(monto_digits) if monto_digits else (call_record.get_amount_due() if call_record else None),
            n_periodos=str(metadata.get('n_periodos') or ''),
            menor_periodo=str(metadata.get('menor_per_deuda') or ''),
            mayor_periodo=str(metadata.get('mayor_per_deuda') or ''),
            tipo_cartera=str(metadata.get('tipo_cartera') or ''),
        )

    def process_and_classify_documents(
        self,
        raw_records: List[Dict[str, Any]],
        source_records: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[List[Document600], List[Document200], int]:
        """
        Procesa registros y los clasifica para archivos 600 y 200.
        PP ahora genera AMBOS archivos (600 Y 200).
        """
        doc_600_list = []
        doc_200_list = []
        errors = 0
        source_records = source_records or {}

        for record in raw_records:
            try:
                call_record = FirestoreCallRecord(**record)
                cliente = self.build_client_data(call_record, source_records.get(call_record.get_track_id()))

                if not cliente:
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

                    if due_date and cliente.monto_deuda:
                        doc_600 = Document600(
                            cliente=cliente,
                            agent_id=call_record.get_agent_name(),
                            processed_at=call_record.get_processed_datetime(),
                            due_date=due_date,
                            conversation_id=call_record.conversation_id,
                        )
                        doc_600_list.append(doc_600)
                        logger.debug(f"Documento 600 creado para: {call_record.conversation_id}")
                    else:
                        logger.warning(f"Promesa de pago sin datos completos: {call_record.conversation_id}")
                        errors += 1

                # TODOS los outcomes (incluyendo PP) generan documento 200
                doc_200 = Document200(
                    cliente=cliente,
                    processed_at=call_record.get_processed_datetime(),
                    codigo_resultado=final_outcome,
                    agent_name=call_record.get_agent_name(),
                    conversation_id=call_record.conversation_id,
                    call_duration=call_record.call_duration_secs,
                    due_date=call_record.get_due_date(),
                    agendar_llamada=call_record.get_agendar_llamada()
                )
                doc_200_list.append(doc_200)
                logger.debug(f"Documento 200 ({final_outcome}) creado para: {call_record.conversation_id}")
                    
            except Exception as e:
                logger.error(f"Error procesando registro {record.get('conversation_id', 'unknown')}: {e}")
                errors += 1
        
        logger.info(f"Procesamiento completado: {len(doc_600_list)} archivo 600, {len(doc_200_list)} archivo 200, {errors} errores")
        return doc_600_list, doc_200_list, errors
    
    async def generate_excel_pp(self, documents: List[Document600]) -> bool:
        """
        Genera el Excel de Promesas de Pago (PP) y lo sube a SFTP en una
        subcarpeta con la fecha del día (igual que los audios).
        """
        return await self._generate_and_upload_excel(
            rows=[doc.to_row() for doc in documents],
            filename_suffix="PP",
        )

    async def generate_excel_todos(self, documents: List[Document200]) -> bool:
        """
        Genera el Excel con todos los resultados de gestión y lo sube a SFTP
        en una subcarpeta con la fecha del día (igual que los audios).
        """
        return await self._generate_and_upload_excel(
            rows=[doc.to_row() for doc in documents],
            filename_suffix="TODOS",
        )

    async def _generate_and_upload_excel(self, rows: List[Dict[str, Any]], filename_suffix: str) -> bool:
        """
        Genera un Excel a partir de filas ya construidas y lo sube al SFTP
        dentro de una subcarpeta con la fecha del día (ddmmyyyy).
        """
        try:
            await self.file_service.connect()
            timestamp = datetime.now().strftime("%Y%m%d")
            # En modo carga se agrega el inicio del id de la carga para no pisar el reporte del día
            carga_tag = f"_lote-{self.report_carga_id.split('-')[1]}" if '-' in self.report_carga_id else ""
            filename = f"{timestamp}{carga_tag}_{filename_suffix}.xlsx"

            success_write = await self.file_service.load(rows, filename, file_type="xlsx")
            if not success_write:
                logger.error(f"Error generando Excel: {filename}")
                return False

            logger.info(f"Excel generado: {filename} con {len(rows)} filas")

            # Subir al SFTP en una subcarpeta con la fecha del día (ddmmyyyy)
            temp_path = self.file_service.base_path / filename
            date_folder = datetime.now().strftime("%d%m%Y")
            remote_path = f"{self.export_config.sftp_txt_path}/{date_folder}/{filename}"
            success = await self._upload_to_sftp(str(temp_path), remote_path)

            # Limpiar archivo temporal
            if temp_path.exists():
                temp_path.unlink()

            return success

        except Exception as e:
            logger.error(f"Error generando Excel {filename_suffix}: {e}")
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