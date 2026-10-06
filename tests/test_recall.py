"""
Tests del flujo del job de re-llamado con servicios simulados. Datos ficticios.
"""
import os
from datetime import datetime, timezone

import pandas as pd
import pytest

os.environ.setdefault("SFTP_HOST", "sftp.test")
os.environ.setdefault("SFTP_PORT", "22")
os.environ.setdefault("SFTP_USERNAME", "user")
os.environ.setdefault("SFTP_PASSWORD", "secret")
os.environ.setdefault("FIRESTORE_PROJECT_ID", "test")
os.environ.setdefault("FIRESTORE_COLLECTION", "registros_llamadas")

from src import recall  # noqa: E402

T = datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)
SOURCES = {
    "a1": {"track_id": "a1", "phone_number": "+56911111111", "processed_at": T,
           "metadata_user": {"rut_deudor": "11111111K", "nombre_deudor": "UNO"}},
    "a2": {"track_id": "a2", "phone_number": "+56922222222", "processed_at": T,
           "metadata_user": {"rut_deudor": "22222222K", "nombre_deudor": "DOS"}},
    "a3": {"track_id": "a3", "phone_number": "+56933333333", "processed_at": T,
           "metadata_user": {"rut_deudor": "33333333K", "nombre_deudor": "TRES"}},
}
TODOS = pd.DataFrame([
    {"RUT Deudor": "11111111K", "Resultado": "NC", "N° Intento": 1},
    {"RUT Deudor": "22222222K", "Resultado": "PP", "N° Intento": 1},
    {"RUT Deudor": "33333333K", "Resultado": "BV", "N° Intento": 1},
])


class FakeFirestore:
    instances = []

    def __init__(self):
        self.claimed = {}
        self.saved = {}
        self.updates = []
        self.claim_ok = True
        FakeFirestore.instances.append(self)

    def connect(self):
        return True

    def get_source_records_by_day(self, start, end):
        return SOURCES

    def claim_recall(self, collection, key, data):
        if self.claim_ok:
            self.claimed[key] = data
        return self.claim_ok

    def save_source_records(self, docs):
        self.saved.update(docs)

    def update_recall(self, collection, key, data):
        self.updates.append(data)


@pytest.fixture
def env(monkeypatch, tmp_path):
    FakeFirestore.instances.clear()
    monkeypatch.setenv("RECALL_DATE", "2026-09-30")
    monkeypatch.setenv("EXPORT_SFTP_TXT_PATH", "/zentagrp/Reportes")
    monkeypatch.delenv("RECALL_DRY_RUN", raising=False)
    monkeypatch.setattr(recall, "FirestoreService", FakeFirestore)
    monkeypatch.setattr(recall, "_wait_for_todos", lambda path, minutes: True)
    monkeypatch.setattr(recall, "_download_todos", lambda remote, local: TODOS.to_excel(local, index=False) or True)
    sent = []
    monkeypatch.setattr(recall, "_send_batch_calling", lambda carga_id, day: sent.append(carga_id) or {"id": "btcal_1"})
    return sent


def test_re_llama_a_los_no_contactados_y_registra_el_dia(env):
    assert recall.run() == 0

    fs = FakeFirestore.instances[0]
    assert len(fs.saved) == 2  # 11111111K (NC) y 33333333K (BV); 22222222K ya es PP
    assert {d["metadata_user"]["rut_deudor"] for d in fs.saved.values()} == {"11111111K", "33333333K"}
    assert list(fs.claimed) == ["20260930"]
    assert env == [fs.claimed["20260930"]["carga_id"]]
    assert fs.updates[-1]["status"] == "enviado"
    assert fs.updates[-1]["batch_call_id"] == "btcal_1"


def test_dry_run_no_escribe_ni_llama(env, monkeypatch):
    monkeypatch.setenv("RECALL_DRY_RUN", "true")

    assert recall.run() == 0

    fs = FakeFirestore.instances[0]
    assert not fs.saved and not fs.claimed and not fs.updates
    assert env == []


def test_no_se_repite_si_el_dia_ya_fue_reservado(env, monkeypatch):
    original_init = FakeFirestore.__init__

    def init(self):
        original_init(self)
        self.claim_ok = False

    monkeypatch.setattr(FakeFirestore, "__init__", init)

    assert recall.run() == 0

    fs = FakeFirestore.instances[0]
    assert not fs.saved
    assert env == []


def test_si_falla_el_envio_queda_en_error_y_el_job_falla(env, monkeypatch):
    def boom(carga_id, day):
        raise RuntimeError("backend 500")

    monkeypatch.setattr(recall, "_send_batch_calling", boom)

    assert recall.run() == 1

    fs = FakeFirestore.instances[0]
    assert fs.updates[-1]["status"] == "error"
    assert "backend 500" in fs.updates[-1]["error"]


def test_sin_a_quien_re_llamar_termina_sin_tocar_nada(env, monkeypatch):
    monkeypatch.setenv("RECALL_RESULTS", "ZZ")

    assert recall.run() == 0

    assert not FakeFirestore.instances  # ni siquiera se conecta a Firestore
    assert env == []


def test_si_no_aparece_el_todos_se_cancela_sin_llamar_a_nadie(monkeypatch):
    FakeFirestore.instances.clear()
    monkeypatch.setenv("RECALL_DATE", "2026-09-30")
    monkeypatch.setenv("EXPORT_SFTP_TXT_PATH", "/zentagrp/Reportes")
    monkeypatch.setattr(recall, "FirestoreService", FakeFirestore)
    monkeypatch.setattr(recall, "_wait_for_todos", lambda path, minutes: False)

    assert recall.run() == 0
    assert not FakeFirestore.instances


class FakeSftp:
    checks = []
    present_from_check = None  # número de revisión desde el que el archivo existe

    def __init__(self, config):
        pass

    def connect(self):
        return True

    def disconnect(self):
        pass

    def file_exists(self, path):
        FakeSftp.checks.append(path)
        return FakeSftp.present_from_check is not None and len(FakeSftp.checks) >= FakeSftp.present_from_check


@pytest.mark.parametrize("present_from_check, expected_found, expected_checks, expected_sleeps", [
    (1, True, 1, []),           # ya está: no espera
    (2, True, 2, [1800.0]),     # aparece durante los 30 minutos
    (None, False, 2, [1800.0]),  # nunca aparece: espera una vez y cancela
])
def test_espera_30_minutos_una_sola_vez(monkeypatch, present_from_check, expected_found, expected_checks, expected_sleeps):
    FakeSftp.checks = []
    FakeSftp.present_from_check = present_from_check
    sleeps = []
    monkeypatch.setattr(recall, "SFTPService", FakeSftp)
    monkeypatch.setattr(recall.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert recall._wait_for_todos("/zentagrp/Reportes/30092026/20260930_TODOS.xlsx", 30) is expected_found
    assert len(FakeSftp.checks) == expected_checks
    assert sleeps == expected_sleeps
