"""
Lógica principal del pipeline ETL.
"""
import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timezone
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
from .utils.day_report import (
    build_pp_rows,
    build_todos_rows,
    chile_day_bounds_utc,
    chile_today,
)
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
        # Opcional (AAAA-MM-DD): reconstruye el reporte de otro día. Por defecto, hoy en horario de Chile.
        self.report_date = os.getenv("REPORT_DATE", "").strip()

    async def run(self) -> bool:
        """
        Genera el reporte consolidado del día: todas las cargas de hoy (la primera
        y el re-llamado) y todas sus llamadas, en un solo TODOS y un solo PP con
        nombre fijo, de modo que cada ejecución reemplaza al archivo anterior.

        Returns:
            bool: True si el pipeline fue exitoso, False en caso contrario
        """
        self.start_time = datetime.now(timezone.utc)
        logger.info("Iniciando ejecución del pipeline")

        try:
            day = date.fromisoformat(self.report_date) if self.report_date else chile_today()
            logger.info(f"Reporte consolidado del día {day.isoformat()}")

            if not self.firestore_service.connect():
                logger.error("No se pudo conectar a Firestore")
                return False

            start_utc, end_utc = chile_day_bounds_utc(day)
            source_records = await asyncio.to_thread(
                self.firestore_service.get_source_records_by_day, start_utc, end_utc)
            if not source_records:
                logger.warning(f"No hay cargas el {day.isoformat()}; no se genera reporte")
                return True
            firestore_data = await asyncio.to_thread(
                self.firestore_service.get_calls_by_track_ids, list(source_records))

            logger.info("Procesando y clasificando documentos...")
            doc_600_list, doc_200_list, errors = self.process_and_classify_documents(firestore_data, source_records)
            # ElevenLabs no avisa de las llamadas que no se contestan: quedan como NC
            doc_200_list += self.build_not_contacted_rows(firestore_data, source_records)

            success = True
            pp_rows = build_pp_rows(doc_600_list)
            if pp_rows:
                logger.info(f"Generando Excel PP con {len(pp_rows)} registros...")
                success = await self.generate_excel_pp(pp_rows, day) and success

            todos_rows = build_todos_rows(doc_200_list)
            if todos_rows:
                logger.info(f"Generando Excel de todos los resultados con {len(todos_rows)} registros...")
                success = await self.generate_excel_todos(todos_rows, day) and success

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

    def build_not_contacted_rows(
        self,
        calls: List[Dict[str, Any]],
        source_records: Dict[str, Dict[str, Any]],
    ) -> List[Document200]:
        """
        Filas NC para las personas cargadas sin llamada registrada: ElevenLabs
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
            processed = source.get('processed_at') or source.get('fecha') or ''
            if isinstance(processed, datetime):
                processed_at = processed
            else:
                try:
                    processed_at = datetime.fromisoformat(str(processed).replace('Z', '+00:00'))
                except ValueError:
                    processed_at = datetime.now(timezone.utc)
            if processed_at.tzinfo is None:
                processed_at = processed_at.replace(tzinfo=timezone.utc)
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
                    # 1. Crear documento 600 (Promesa de Pago). Va al archivo PP aunque
                    #    el deudor no haya dicho una fecha de compromiso.
                    doc_600 = Document600(
                        cliente=cliente,
                        agent_id=call_record.get_agent_name(),
                        processed_at=call_record.get_processed_datetime(),
                        due_date=call_record.get_due_date(),
                        conversation_id=call_record.conversation_id,
                    )
                    doc_600_list.append(doc_600)
                    logger.debug(f"Documento 600 creado para: {call_record.conversation_id}")

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
    
    async def generate_excel_pp(self, rows: List[Dict[str, Any]], day: date) -> bool:
        """
        Sube el Excel de Promesas de Pago (PP) del día al SFTP, en la subcarpeta
        con la fecha del día (igual que los audios).
        """
        return await self._generate_and_upload_excel(rows, "PP", day)

    async def generate_excel_todos(self, rows: List[Dict[str, Any]], day: date) -> bool:
        """
        Sube el Excel con todos los intentos del día al SFTP, en la subcarpeta
        con la fecha del día (igual que los audios).
        """
        return await self._generate_and_upload_excel(rows, "TODOS", day)

    async def _generate_and_upload_excel(self, rows: List[Dict[str, Any]], filename_suffix: str, day: date) -> bool:
        """
        Genera un Excel con nombre fijo AAAAMMDD_<sufijo>.xlsx y lo sube al SFTP
        dentro de la subcarpeta ddmmyyyy del día. Como el nombre no cambia, cada
        ejecución reemplaza el archivo anterior.
        """
        filename = f"{day:%Y%m%d}_{filename_suffix}.xlsx"
        try:
            await self.file_service.connect()

            success_write = await self.file_service.load(rows, filename, file_type="xlsx")
            if not success_write:
                logger.error(f"Error generando Excel: {filename}")
                return False

            logger.info(f"Excel generado: {filename} con {len(rows)} filas")

            temp_path = self.file_service.base_path / filename
            remote_path = f"{self.export_config.sftp_txt_path}/{day:%d%m%Y}/{filename}"
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