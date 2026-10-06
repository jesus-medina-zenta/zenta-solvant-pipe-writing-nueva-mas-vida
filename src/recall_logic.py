"""
Reglas del re-llamado automático (sin acceso a servicios, para poder probarlas).

- Se re-llama una sola vez por persona: solo a quien tiene un único intento en el
  día y su resultado fue de "no contactado".
- Las filas del re-llamado son copias de las filas originales del archivo del
  cliente (registros_sftp) con carga y track_id nuevos.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from src.utils.day_report import normalize_rut

# NC no contactado, BV buzón de voz, ND no disponible.
# Quedan fuera: LI (corte técnico), TA (llamar después) y todo lo que ya es resuelto
# (PP, YC, DD, IN, ...).
DEFAULT_RESULTS = frozenset({"NC", "BV", "ND"})


def select_ruts_to_recall(rows: Iterable[Dict[str, Any]], results: Set[str] = DEFAULT_RESULTS) -> List[str]:
    """
    A partir de las filas del TODOS del día, devuelve los RUT (tal como vienen en
    el archivo) con un único intento cuyo resultado está en `results`.
    """
    by_rut: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = normalize_rut(row.get("RUT Deudor"))
        if key:
            by_rut.setdefault(key, []).append(row)

    selected = []
    for attempts in by_rut.values():
        if len(attempts) != 1:
            continue
        row = attempts[0]
        if str(row.get("Resultado") or "").strip().upper() in results:
            selected.append(str(row["RUT Deudor"]).strip())
    return selected


def _source_time(record: Dict[str, Any]) -> datetime:
    value = record.get("processed_at") or record.get("fecha")
    if not isinstance(value, datetime):
        try:
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_recall_records(
    ruts: Iterable[str],
    source_records: Dict[str, Dict[str, Any]],
    carga_uuid: str,
    day_prefix: str,
    now_iso: str,
    processed_at: Any,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Copia la fila original de cada RUT (la más antigua del día) como una carga nueva.

    Devuelve ({id_documento: datos}, ruts_sin_fila_o_sin_telefono). Los campos son
    los mismos que escribe pipe-reading-csv: fecha, id, phone_number, phone_number_2,
    metadata_user, track_id, track_status, processed_at y source_type.
    """
    by_rut: Dict[str, Dict[str, Any]] = {}
    for record in sorted(source_records.values(), key=_source_time):
        metadata = record.get("metadata_user") or {}
        key = normalize_rut(metadata.get("rut_deudor") or metadata.get("rut"))
        if key:
            by_rut.setdefault(key, record)

    documents: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for rut in ruts:
        record: Optional[Dict[str, Any]] = by_rut.get(normalize_rut(rut))
        if not record or not record.get("phone_number"):
            missing.append(rut)
            continue
        documents[f"{day_prefix}-{carga_uuid}_{len(documents) + 1}"] = {
            "fecha": now_iso,
            "id": carga_uuid,
            "phone_number": record["phone_number"],
            "phone_number_2": record.get("phone_number_2") or "",
            "metadata_user": record.get("metadata_user") or {},
            "track_id": str(uuid.uuid4()),
            "track_status": "queued_call",
            "processed_at": processed_at,
            "source_type": "recall",
        }
    return documents, missing
