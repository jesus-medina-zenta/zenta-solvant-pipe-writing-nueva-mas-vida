"""
Reporte consolidado del día: fechas en horario de Chile y armado de las filas de
los Excel TODOS (un renglón por intento) y PP (una promesa por persona).
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

import pytz

from src.models.firestore_records import Document200, Document600

CHILE_TZ = pytz.timezone("America/Santiago")
ATTEMPT_COLUMN = "N° Intento"


def chile_today() -> date:
    return datetime.now(CHILE_TZ).date()


def chile_day_bounds_utc(day: date) -> Tuple[datetime, datetime]:
    """Inicio (incluido) y fin (excluido) del día chileno, expresados en UTC."""
    start = CHILE_TZ.localize(datetime.combine(day, time.min))
    end = CHILE_TZ.localize(datetime.combine(day + timedelta(days=1), time.min))
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def normalize_rut(rut: Any) -> str:
    return str(rut or "").strip().upper().replace(".", "").replace("-", "").lstrip("0")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_todos_rows(docs: Iterable[Document200]) -> List[Dict[str, Any]]:
    """
    Una fila por intento, en orden cronológico. "N° Intento" cuenta, por RUT, la
    posición de la llamada en el día (1 = primera llamada, 2 = el re-llamado).
    """
    attempts: Dict[str, int] = {}
    rows = []
    for doc in sorted(docs, key=lambda d: _aware(d.processed_at)):
        key = normalize_rut(doc.cliente.rut)
        attempts[key] = attempts.get(key, 0) + 1
        row = doc.to_row()
        row[ATTEMPT_COLUMN] = attempts[key]
        rows.append(row)
    return rows


def build_pp_rows(docs: Iterable[Document600]) -> List[Dict[str, Any]]:
    """Una promesa por persona (la más reciente), en orden cronológico."""
    latest: Dict[str, Document600] = {}
    for doc in sorted(docs, key=lambda d: _aware(d.processed_at)):
        latest[normalize_rut(doc.cliente.rut)] = doc
    return [doc.to_row() for doc in sorted(latest.values(), key=lambda d: _aware(d.processed_at))]
