"""
Tests de las filas de los Excel de salida (PP y TODOS). Datos ficticios.
"""
import os

os.environ.setdefault("SFTP_HOST", "sftp.test")
os.environ.setdefault("SFTP_USERNAME", "user")
os.environ.setdefault("SFTP_PASSWORD", "secret")
os.environ.setdefault("FIRESTORE_PROJECT_ID", "test")
os.environ.setdefault("FIRESTORE_COLLECTION", "registros_llamadas")

from src.pipeline import Pipeline  # noqa: E402


def _call(outcome: str, track_id: str = "track-1", **extra):
    return {
        "conversation_id": "conv_test0000001",
        "status": "done",
        "processed_at": "2026-09-23T15:30:00Z",
        "call_duration_secs": 75,
        "agent_id": "agent_test",
        "dynamic_variables": {
            "track_id": track_id,
            "name": "Juan Pérez",
            "rut_deudor": "11111111K",
            "deuda_cotizaciones": "84.249",
            "system__called_number": "+56912345678",
        },
        "analysis": {"data_collection_results": {"final_call_outcome": {"value": outcome}}},
        **extra,
    }


# Fila de registros_sftp tal como la guarda pipe-reading-csv desde el archivo del cliente
SOURCE = {
    "track-1": {
        "track_id": "track-1",
        "phone_number": "+56912345678",
        "metadata_user": {
            "rut_deudor": "11111111K",
            "nombre_deudor": "PÉREZ MUÑOZ JUAN ANDRÉS",
            "ciudad": "SANTIAGO",
            "deuda_cotizaciones": "84249",
            "n_periodos": "2",
            "menor_per_deuda": "06-2026",
            "mayor_per_deuda": "07-2026",
            "tipo_cartera": "2",
        },
    }
}


def _process(records, sources=SOURCE):
    pipeline = Pipeline.__new__(Pipeline)
    return pipeline.process_and_classify_documents(records, sources)


def test_excel_todos_trae_los_datos_del_archivo_del_cliente():
    _, todos, errors = _process([_call("TA", agendar_llamada="el viernes en la tarde")])

    assert errors == 0
    assert todos[0].to_row() == {
        "RUT Deudor": "11111111K",
        "Nombre Deudor": "PÉREZ MUÑOZ JUAN ANDRÉS",
        "Ciudad": "SANTIAGO",
        "Teléfono Gestionado": "912345678",
        "Monto Deuda ($)": 84249,
        "N° Períodos": "2",
        "Menor Período de Deuda": "06-2026",
        "Mayor Período de Deuda": "07-2026",
        "Tipo de Cartera": "2",
        "Fecha Gestión": "23-09-2026 12:30:00",
        "Resultado": "TA",
        "Descripción Resultado": "LLAMAR DESPUES",
        "Fecha Compromiso Pago": "",
        "Fecha/Hora Recontacto": "el viernes en la tarde",
        "Duración Llamada (s)": 75,
        "Agente": "ZNT_NMV",
        "ID Conversación": "conv_test0000001",
    }


def test_compromiso_de_pago_genera_fila_en_pp_y_en_todos():
    pp, todos, errors = _process([_call("PP", fecha_compromiso="el quince")])

    assert errors == 0
    assert len(todos) == 1
    assert pp[0].to_row() == {
        "RUT Deudor": "11111111K",
        "Nombre Deudor": "PÉREZ MUÑOZ JUAN ANDRÉS",
        "Teléfono Gestionado": "912345678",
        "Monto Deuda ($)": 84249,
        "Mayor Período de Deuda": "07-2026",
        "Fecha Gestión": "23-09-2026 12:30:00",
        "Fecha Compromiso Pago": "el quince",
        "Agente": "ZNT_NMV",
        "ID Conversación": "conv_test0000001",
    }


def test_sin_fila_de_origen_usa_las_variables_de_la_llamada():
    _, todos, errors = _process([_call("NC", track_id="no-existe")], sources={})

    row = todos[0].to_row()
    assert errors == 0
    assert row["RUT Deudor"] == "11111111K"
    assert row["Nombre Deudor"] == "Juan Pérez"
    assert row["Teléfono Gestionado"] == "912345678"
    assert row["Monto Deuda ($)"] == 84249
    assert row["Mayor Período de Deuda"] == ""
