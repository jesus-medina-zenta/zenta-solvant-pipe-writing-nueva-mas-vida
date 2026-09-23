"""
Lógica principal del pipeline ETL.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

#models
from src.models.firestore_records import FirestoreCallRecord
from src.utils.outcome_mapper import OutcomeMapping

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

REPORT_COLUMNS = [
    "Fecha gestion", "Nombre cliente", "RUT deudor", "Telefono", "Correo",
    "Monto deuda", "Periodo deuda", "Resultado gestion", "Fecha compromiso pago",
    "Duracion llamada (seg)", "Agente ejecutivo", "ID conversacion",
]

CHILE_TZ = timezone(timedelta(hours=-3))


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
            logger.info("Procesando registros para el reporte...")
            report_rows, errors = self.build_report_rows(firestore_data)

            if not report_rows:
                logger.warning("No hay registros válidos para generar el reporte")
                return True

            # Paso 3: Load
            logger.info(f"Generando reporte Excel con {len(report_rows)} registros...")
            success = await self.generate_excel_report(report_rows)

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
    
    def build_report_rows(self, raw_records: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], int]:
        """
        Convierte los registros de Firestore en filas para el reporte Excel.
        """
        rows = []
        errors = 0

        for record in raw_records:
            try:
                call_record = FirestoreCallRecord(**record)
                rut = call_record.get_rut()

                if not rut:
                    logger.warning(f"Registro sin RUT válido: {call_record.conversation_id}")
                    errors += 1
                    continue

                final_outcome = call_record.get_final_call_outcome()
                dv = call_record.dynamic_variables

                # Excel no admite datetimes con tzinfo: se convierte a hora de
                # Chile y se descarta el tzinfo antes de escribirla.
                fecha_gestion = call_record.get_processed_datetime().astimezone(CHILE_TZ).replace(tzinfo=None)

                rows.append({
                    "Fecha gestion": fecha_gestion,
                    "Nombre cliente": dv.get("name") or "",
                    "RUT deudor": rut,
                    "Telefono": call_record.get_phone_number() or "",
                    "Correo": dv.get("correo") or "",
                    "Monto deuda": call_record.get_amount_due(),
                    "Periodo deuda": dv.get("periodo_deuda") or "",
                    "Resultado gestion": OutcomeMapping.get_description(final_outcome) if final_outcome else "",
                    "Fecha compromiso pago": call_record.get_due_date() or "",
                    "Duracion llamada (seg)": call_record.call_duration_secs,
                    "Agente ejecutivo": dv.get("Agente") or "",
                    "ID conversacion": call_record.conversation_id,
                })
                logger.debug(f"Fila de reporte creada para: {call_record.conversation_id}")

            except Exception as e:
                logger.error(f"Error procesando registro {record.get('conversation_id', 'unknown')}: {e}")
                errors += 1

        logger.info(f"Procesamiento completado: {len(rows)} filas de reporte, {errors} errores")
        return rows, errors

    async def generate_excel_report(self, rows: List[Dict[str, Any]]) -> bool:
        """
        Genera el reporte Excel del dia con las gestiones de cobranza y lo sube al SFTP.
        """
        try:
            await self.file_service.connect()
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{timestamp}.xlsx"
            temp_path = self.file_service.base_path / filename

            self._write_excel_report(rows, temp_path)
            logger.info(f"Reporte Excel generado: {filename} con {len(rows)} filas")

            remote_path = f"{self.export_config.sftp_txt_path}/{filename}"
            success = await self._upload_to_sftp(str(temp_path), remote_path)

            if temp_path.exists():
                temp_path.unlink()

            return success

        except Exception as e:
            logger.error(f"Error generando reporte Excel: {e}")
            return False

    def _write_excel_report(self, rows: List[Dict[str, Any]], out_path: Path) -> None:
        """
        Escribe las filas del reporte a un .xlsx con formato legible para el cliente.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Gestiones de cobranza"

        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        thin = Side(style="thin", color="D9D9D9")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for col_idx, col_name in enumerate(REPORT_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border

        for r_idx, row in enumerate(rows, start=2):
            for c_idx, col_name in enumerate(REPORT_COLUMNS, start=1):
                value = row.get(col_name)
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                cell.border = border
                if col_name == "Fecha gestion" and value:
                    cell.number_format = "dd/mm/yyyy hh:mm"
                if col_name == "Monto deuda" and value:
                    cell.number_format = "#,##0"

        widths = {
            "Fecha gestion": 18, "Nombre cliente": 16, "RUT deudor": 12, "Telefono": 15,
            "Correo": 26, "Monto deuda": 13, "Periodo deuda": 14, "Resultado gestion": 20,
            "Fecha compromiso pago": 20, "Duracion llamada (seg)": 12,
            "Agente ejecutivo": 14, "ID conversacion": 30,
        }
        for col_idx, col_name in enumerate(REPORT_COLUMNS, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(col_name, 15)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        out_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)

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