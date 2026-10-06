"""
Re-llamado automático de las personas no contactadas del día (un solo reintento).

Se ejecuta como Cloud Run Job (python -m src.recall), por ejemplo a las 15:00 hora
de Chile:

1. Busca en el SFTP el TODOS de hoy (<EXPORT_SFTP_TXT_PATH>/ddmmyyyy/AAAAMMDD_TODOS.xlsx).
   Si no está, espera RECALL_WAIT_MINUTES y vuelve a mirar; si sigue sin estar,
   cancela sin llamar a nadie.
2. Se queda con quienes tienen un único intento y resultado NC, BV o ND.
3. Copia sus filas de registros_sftp como una carga nueva y pide al backend que
   la envíe a ElevenLabs (mismo camino que usa pipe-reading-csv).
4. Cuando ElevenLabs termina el lote, el backend (exportar-lotes-terminados) vuelve
   a ejecutar pipe-writing, que reemplaza el TODOS y el PP del día.

RECALL_DRY_RUN=true calcula y registra cuántas personas se llamarían, sin escribir
en Firestore ni llamar al backend.
"""
import os
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import requests
import google.auth.transport.requests
from google.cloud import firestore
from google.oauth2 import id_token

from src.config import get_file_export_config, get_sftp_config
from src.recall_logic import DEFAULT_RESULTS, build_recall_records, select_ruts_to_recall
from src.services.firestore_service import FirestoreService
from src.services.sftp_service import SFTPService
from src.utils.day_report import chile_day_bounds_utc, chile_today
from src.utils.logger import get_logger

logger = get_logger(__name__)

RECALL_COLLECTION = os.getenv("RECALL_COLLECTION", "registro_recalls")
BACKEND_TIMEOUT_SECONDS = 60


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "si", "sí")


def _wait_for_todos(remote_path: str, wait_minutes: float) -> bool:
    """Busca el TODOS de hoy; si no está espera y busca una vez más."""
    for attempt in (1, 2):
        sftp = SFTPService(get_sftp_config())
        try:
            if not sftp.connect():
                logger.error("No se pudo conectar al SFTP")
                exists = False
            else:
                exists = sftp.file_exists(remote_path)
        finally:
            sftp.disconnect()
        if exists:
            return True
        if attempt == 1:
            logger.warning(f"No está {remote_path}; se vuelve a buscar en {wait_minutes:g} minutos")
            time.sleep(wait_minutes * 60)
    return False


def _download_todos(remote_path: str, local_path: Path) -> bool:
    sftp = SFTPService(get_sftp_config())
    try:
        return sftp.connect() and sftp.download_file(remote_path, str(local_path))
    finally:
        sftp.disconnect()


def _send_batch_calling(carga_id: str, day: date) -> Dict[str, Any]:
    """Pide al backend enviar la carga a ElevenLabs. Mismo payload que pipe-reading-csv."""
    backend_url = os.environ["BACKEND_SERVICE_URL"]
    endpoint = f"{backend_url}/{os.environ['BACKEND_ENDPOINT_BATCH_CALLING']}"
    token = id_token.fetch_id_token(google.auth.transport.requests.Request(), audience=backend_url)
    payload = {
        "carga_id": carga_id,
        "agent_id": os.environ["BACKEND_PAYLOAD_AGENT"],
        "call_name": f"{day:%d%m%Y}_{os.getenv('RECALL_CALL_NAME', 'SFTP_RECALL')}",
        "agent_phone_number_id": os.environ["BACKEND_PAYLOAD_AGENT_PHONE_NUMBER_ID"],
    }
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "Zenta-Pipeline/1.0"},
        timeout=BACKEND_TIMEOUT_SECONDS,
    )
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"El backend respondió {response.status_code}: {response.text[:300]}")
    return response.json()


def run() -> int:
    dry_run = _env_bool("RECALL_DRY_RUN")
    wait_minutes = float(os.getenv("RECALL_WAIT_MINUTES", "30"))
    results = frozenset(
        code.strip().upper() for code in os.getenv("RECALL_RESULTS", ",".join(sorted(DEFAULT_RESULTS))).split(",") if code.strip()
    )
    override = os.getenv("RECALL_DATE", "").strip()
    day = date.fromisoformat(override) if override else chile_today()
    key = f"{day:%Y%m%d}"
    logger.info(f"Re-llamado del {day.isoformat()} (resultados {sorted(results)}, dry_run={dry_run})")

    remote_path = f"{get_file_export_config().sftp_txt_path}/{day:%d%m%Y}/{key}_TODOS.xlsx"
    if not _wait_for_todos(remote_path, wait_minutes):
        logger.error(f"CANCELADO: no se encontró {remote_path}; no se re-llama a nadie")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        local_path = Path(tmp) / f"{key}_TODOS.xlsx"
        if not _download_todos(remote_path, local_path):
            logger.error("No se pudo descargar el TODOS")
            return 1
        rows = pd.read_excel(local_path, dtype=str).fillna("").to_dict("records")

    ruts = select_ruts_to_recall(rows, results)
    logger.info(f"TODOS del día: {len(rows)} intentos; a re-llamar: {len(ruts)} personas")
    if not ruts:
        logger.info("No hay a quién re-llamar")
        return 0

    firestore_service = FirestoreService()
    if not firestore_service.connect():
        logger.error("No se pudo conectar a Firestore")
        return 1
    start_utc, end_utc = chile_day_bounds_utc(day)
    source_records = firestore_service.get_source_records_by_day(start_utc, end_utc)

    carga_uuid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    documents, missing = build_recall_records(
        ruts, source_records, carga_uuid, f"{day:%d%m%Y}",
        now.isoformat().replace("+00:00", "Z"), firestore.SERVER_TIMESTAMP,
    )
    if missing:
        logger.warning(f"{len(missing)} personas sin fila de origen o sin teléfono; no se re-llaman")
    if not documents:
        logger.error("Ninguna persona a re-llamar tiene fila de origen")
        return 1

    if dry_run:
        logger.info(f"DRY RUN: se re-llamaría a {len(documents)} personas (carga {carga_uuid}); no se escribe ni se llama")
        return 0

    # Reserva el día: aunque el job se reintente, no se vuelve a llamar a nadie.
    claimed = firestore_service.claim_recall(RECALL_COLLECTION, key, {
        "status": "iniciado", "carga_id": carga_uuid, "total": len(documents), "started_at": now.isoformat(),
    })
    if not claimed:
        logger.warning(f"El re-llamado del {day.isoformat()} ya se ejecutó (documento {RECALL_COLLECTION}/{key}); no se repite")
        return 0

    try:
        firestore_service.save_source_records(documents)
        response = _send_batch_calling(carga_uuid, day)
    except Exception as e:
        logger.exception(f"Falló el envío del re-llamado: {e}")
        firestore_service.update_recall(RECALL_COLLECTION, key, {"status": "error", "error": str(e)[:500]})
        return 1

    firestore_service.update_recall(RECALL_COLLECTION, key, {
        "status": "enviado", "batch_call_id": (response or {}).get("id"), "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"Re-llamado enviado: {len(documents)} personas, carga {carga_uuid}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        logger.exception(f"Error inesperado en el re-llamado: {exc}")
        sys.exit(1)
