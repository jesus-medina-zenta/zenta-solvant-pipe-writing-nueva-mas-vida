"""
Tests del reporte consolidado del día y del re-llamado. Datos ficticios.
"""
import asyncio
import os
from datetime import date, datetime, timezone

import pandas as pd

os.environ.setdefault("SFTP_HOST", "sftp.test")
os.environ.setdefault("SFTP_PORT", "22")
os.environ.setdefault("SFTP_USERNAME", "user")
os.environ.setdefault("SFTP_PASSWORD", "secret")
os.environ.setdefault("FIRESTORE_PROJECT_ID", "test")
os.environ.setdefault("FIRESTORE_COLLECTION", "registros_llamadas")

from src.pipeline import Pipeline  # noqa: E402
from src.recall_logic import build_recall_records, select_ruts_to_recall  # noqa: E402
from src.utils.day_report import chile_day_bounds_utc  # noqa: E402


def _source(track_id, rut, phone, processed_at, **meta):
    return {
        "track_id": track_id,
        "phone_number": phone,
        "phone_number_2": "",
        "processed_at": processed_at,
        "metadata_user": {"rut_deudor": rut, "nombre_deudor": f"PERSONA {rut}", "deuda_cotizaciones": "10000", **meta},
    }


def _call(track_id, rut, outcome, at, conv, **extra):
    return {
        "conversation_id": conv,
        "status": "done",
        "processed_at": at,
        "call_duration_secs": 30,
        "agent_id": "agent_test",
        "dynamic_variables": {"track_id": track_id, "rut_deudor": rut, "system__called_number": "+56911111111"},
        "analysis": {"data_collection_results": {"final_call_outcome": {"value": outcome}}},
        **extra,
    }


T_CARGA_1 = datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)   # 11:00 Chile
T_CARGA_2 = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)   # 15:00 Chile

SOURCES = {
    # carga de la mañana
    "a1": _source("a1", "11111111K", "+56911111111", T_CARGA_1),  # NC y luego PP
    "a2": _source("a2", "22222222K", "+56922222222", T_CARGA_1),  # PP sin fecha
    "a3": _source("a3", "33333333K", "+56933333333", T_CARGA_1),  # NC, no contesta nunca
    "a4": _source("a4", "44444444K", "+56944444444", T_CARGA_1),  # corte técnico
    # re-llamado de la tarde
    "b1": _source("b1", "11111111K", "+56911111111", T_CARGA_2),
    "b3": _source("b3", "33333333K", "+56933333333", T_CARGA_2),
}
CALLS = [
    _call("a1", "11111111K", "NC", "2026-09-30T14:05:00Z", "conv_a1"),
    _call("a2", "22222222K", "PP", "2026-09-30T14:06:00Z", "conv_a2"),   # sin fecha_compromiso
    _call("a4", "44444444K", "LI", "2026-09-30T14:07:00Z", "conv_a4"),
    _call("b1", "11111111K", "PP", "2026-09-30T18:05:00Z", "conv_b1", fecha_compromiso="el viernes"),
    # a3 y b3: no hay llamada registrada -> NC
]


def _day_rows():
    pipeline = Pipeline.__new__(Pipeline)
    pp, todos, _ = pipeline.process_and_classify_documents(CALLS, SOURCES)
    todos += pipeline.build_not_contacted_rows(CALLS, SOURCES)
    return pp, todos


def test_todos_deja_constancia_de_cada_intento_en_orden():
    from src.utils.day_report import build_todos_rows

    _, todos = _day_rows()
    rows = build_todos_rows(todos)

    persona_1 = [(r["Resultado"], r["N° Intento"]) for r in rows if r["RUT Deudor"] == "11111111K"]
    assert persona_1 == [("NC", 1), ("PP", 2)]
    persona_3 = [(r["Resultado"], r["N° Intento"], r["ID Conversación"]) for r in rows if r["RUT Deudor"] == "33333333K"]
    assert persona_3 == [("NC", 1, ""), ("NC", 2, "")]
    persona_4 = [r["N° Intento"] for r in rows if r["RUT Deudor"] == "44444444K"]
    assert persona_4 == [1]
    assert len(rows) == 6  # 4 llamadas + 2 personas que no contestaron


def test_pp_incluye_promesas_sin_fecha_y_una_fila_por_persona():
    from src.utils.day_report import build_pp_rows

    pp, _ = _day_rows()
    rows = build_pp_rows(pp)

    assert {r["RUT Deudor"] for r in rows} == {"11111111K", "22222222K"}
    sin_fecha = next(r for r in rows if r["RUT Deudor"] == "22222222K")
    assert sin_fecha["Fecha Compromiso Pago"] == ""
    con_fecha = next(r for r in rows if r["RUT Deudor"] == "11111111K")
    assert con_fecha["Fecha Compromiso Pago"] == "el viernes"


def test_limites_del_dia_chileno_en_utc():
    start, end = chile_day_bounds_utc(date(2026, 9, 30))
    # En septiembre Chile ya cambió a horario de verano (UTC-3)
    assert start == datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)


def test_pipeline_sube_archivos_con_nombre_fijo_a_la_carpeta_del_dia(tmp_path):
    class FakeFirestore:
        def connect(self):
            return True

        def get_source_records_by_day(self, start, end):
            assert start == datetime(2026, 9, 30, 3, 0, tzinfo=timezone.utc)
            return SOURCES

        def get_calls_by_track_ids(self, ids):
            return CALLS

    uploads = {}

    async def fake_upload(local_path, remote_path):
        uploads[remote_path] = pd.read_excel(local_path, dtype=str)
        return True

    from src.services.file_service import FileService

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.firestore_service = FakeFirestore()
    pipeline.file_service = FileService(str(tmp_path))
    pipeline.export_config = type("Cfg", (), {"sftp_txt_path": "/zentagrp/Reportes"})()
    pipeline.report_date = "2026-09-30"
    pipeline._upload_to_sftp = fake_upload

    assert asyncio.run(pipeline.run()) is True

    assert sorted(uploads) == [
        "/zentagrp/Reportes/30092026/20260930_PP.xlsx",
        "/zentagrp/Reportes/30092026/20260930_TODOS.xlsx",
    ]
    todos = uploads["/zentagrp/Reportes/30092026/20260930_TODOS.xlsx"]
    assert list(todos.columns)[:17] == [
        "RUT Deudor", "Nombre Deudor", "Ciudad", "Teléfono Gestionado", "Monto Deuda ($)", "N° Períodos",
        "Menor Período de Deuda", "Mayor Período de Deuda", "Tipo de Cartera", "Fecha Gestión", "Resultado",
        "Descripción Resultado", "Fecha Compromiso Pago", "Fecha/Hora Recontacto", "Duración Llamada (s)",
        "Agente", "ID Conversación",
    ]
    assert list(todos.columns)[17] == "N° Intento"
    assert len(todos) == 6
    assert len(uploads["/zentagrp/Reportes/30092026/20260930_PP.xlsx"]) == 2
    assert not list(tmp_path.glob("*.xlsx")), "no deben quedar archivos temporales"


def test_re_llamado_toma_solo_no_contactados_con_un_intento():
    from src.utils.day_report import build_todos_rows

    # Estado a las 15:00, antes del re-llamado: solo la carga de la mañana
    pipeline = Pipeline.__new__(Pipeline)
    sources = {k: v for k, v in SOURCES.items() if k.startswith("a")}
    calls = [c for c in CALLS if c["dynamic_variables"]["track_id"].startswith("a")]
    _, todos, _ = pipeline.process_and_classify_documents(calls, sources)
    todos += pipeline.build_not_contacted_rows(calls, sources)
    rows = build_todos_rows(todos)

    # a1 NC y a3 NC (sin llamada) se re-llaman; a2 es PP y a4 es LI (corte técnico)
    assert sorted(select_ruts_to_recall(rows)) == ["11111111K", "33333333K"]

    # Con el re-llamado ya hecho (2 intentos) no se vuelve a llamar a nadie
    assert select_ruts_to_recall(build_todos_rows(_day_rows()[1])) == []


def test_re_llamado_excluye_ta_y_li_aunque_tengan_un_solo_intento():
    rows = [
        {"RUT Deudor": "1", "Resultado": "TA"},
        {"RUT Deudor": "2", "Resultado": "LI"},
        {"RUT Deudor": "3", "Resultado": "BV"},
        {"RUT Deudor": "4", "Resultado": "ND"},
        {"RUT Deudor": "5", "Resultado": "YC"},
    ]
    assert select_ruts_to_recall(rows) == ["3", "4"]


def test_copia_de_filas_para_la_carga_de_re_llamado():
    docs, missing = build_recall_records(
        ["11111111K", "33333333K", "99999999K"], SOURCES, "uuid-nuevo", "30092026", "2026-09-30T18:00:00Z", "TS",
    )

    assert missing == ["99999999K"]
    assert list(docs) == ["30092026-uuid-nuevo_1", "30092026-uuid-nuevo_2"]
    primero = docs["30092026-uuid-nuevo_1"]
    assert primero["id"] == "uuid-nuevo"
    assert primero["phone_number"] == "+56911111111"
    assert primero["metadata_user"] == SOURCES["a1"]["metadata_user"]
    assert primero["track_status"] == "queued_call"
    assert primero["source_type"] == "recall"
    assert primero["track_id"] not in {"a1", "b1"}
    assert docs["30092026-uuid-nuevo_2"]["track_id"] != primero["track_id"]
