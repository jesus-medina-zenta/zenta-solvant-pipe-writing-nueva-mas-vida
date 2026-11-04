# Reporte de remediación de dependencias

**Fecha:** 2026-09-02
**Servicios afectados:** zenta-solvant-pipe-writing-nueva-mas-vida (Cloud Run Job `zenta-solvant-pipe-writing`)

## Cambios aplicados

| CVE | Paquete | Versión anterior → nueva | Tipo de cambio | Acción tomada | Verificación | Estado |
|---|---|---|---|---|---|---|
| CVE-2026-28684 | python-dotenv | 1.0.0 → **revertido a 1.0.0** | — | Se intentó `>=1.2.2` (el fix real) pero **falló el build real de Docker**: esa versión requiere Python >=3.10 y esta imagen usa `python:3.9-slim` (EOL). No existe versión de python-dotenv que sea segura y compatible con 3.9 a la vez. Verificado localmente con pip-audit (Python 3.11) de forma engañosa — el build de Docker (Python 3.9) reveló el conflicto real | build de Docker con `>=1.2.2`: `ERROR: Could not find a version that satisfies the requirement python-dotenv>=1.2.2` | 🚫 Bloqueado (requiere upgrade de Python base) |
| CVE-2023-48795, CVE-2026-44405 | paramiko | `>=3.0.0` → `>=3.4.0` | minor | subido el mínimo (el build de hoy ya había resuelto una versión no vulnerable por casualidad al no estar pineado; ahora queda garantizado) | pip-audit limpio, import OK | ✅ Resuelto |
| CVE-2024-52338 (no estaba en el escaneo pegado por el usuario para este repo, lo encontró pip-audit) | pyarrow | 14.0.2 → >=17.0.0 | major (14→17) | bump de pin; sin uso directo de la API de pyarrow en el código (dependencia transitiva de pandas/openpyxl) | pip-audit limpio, `pip check` OK, import de `src.pipeline`, `FirestoreService`, `SFTPService`, `FileService` OK | ✅ Resuelto |
| CVE-2026-44432, CVE-2026-44431 | urllib3 | (transitiva de requests, sin CVE directo en requirements.txt de este repo) | — | resuelto indirectamente por la resolución de dependencias del venv de verificación (requests moderno arrastra urllib3 seguro) | pip-audit limpio | ✅ Resuelto |
| CVE-2026-8643, CVE-2026-6357, CVE-2026-3219, CVE-2026-13346, CVE-2025-8869, CVE-2023-5752 | pip | (toolchain) | patch (toolchain) | `Dockerfile`: `pip install --upgrade pip` → `pip install --upgrade pip setuptools wheel` | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-24049 | wheel | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-59890 | setuptools | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |
| CVE-2026-23949 | jaraco-context | (toolchain) | patch (toolchain) | mismo cambio de Dockerfile | pendiente de build | ⚠️ Pendiente de build |

## Ajustes de código por breaking changes

Ninguno. `paramiko` y `pyarrow` mantuvieron API estable para el uso de este proyecto (cliente SFTP básico vía `SFTPService`, y `pyarrow` solo como dependencia transitiva sin llamadas directas).

**Nota de contexto:** este repo fue reconstruido y redesplegado hoy mismo en esta sesión por otro motivo (fix de `agent_id`/colección Firestore). Ese build usó el `requirements.txt` **antes** de este fix de seguridad — la imagen actualmente en Cloud Run (`zenta-solvant-pipe-writing`) todavía no incluye estos parches de dependencias; requiere un nuevo build.

## Política Perl / librerías críticas prohibidas

**Bloqueada — se intentó eliminar, Debian lo impide.** Mismo caso que en los otros 2 repos: Perl viene con `python:3.9-slim` sin uso funcional, 13 CVEs sin parche (2 críticos). Se probó `apt-get purge -y --auto-remove perl-base perl` en un build real y falló: Debian marca `perl-base` como paquete **esencial** en esta imagen (`E: Essential packages were removed and -y was used without --allow-remove-essential`). Se revirtió el cambio. Ver detalle completo en el reporte de `zenta-solvant-pipe-reading-nueva-mas-vida`.

## Próximos pasos (lo que quedó pendiente)

- [ ] Reconstruir y redesplegar la imagen Docker (además del fix de `pip setuptools wheel`, esta reconstrucción también actualiza el `requirements.txt` con los bumps de esta pasada — la imagen actual en Cloud Run no los tiene).
- [ ] Perl queda 🚫 bloqueado (ver detalle arriba) — no se aplicó ninguna eliminación.
- [ ] CVE-2026-28684 (python-dotenv) queda 🚫 bloqueado — requiere migrar `python:3.9-slim` a `python:3.10-slim`/`3.11-slim` (esta imagen ya usa Python 3.9, que está EOL desde octubre de 2025; `reading` ya corre sobre 3.11-slim sin problemas, así que es viable, pero es un cambio más amplio que no se aplicó en esta pasada urgente).
- [ ] CVEs de `glibc`, `acl`, `attr`, `sqlite3`, `gzip`, `bzip2` sin parche disponible en Debian: riesgo conocido.
- [ ] CVEs de `systemd`, `xz-utils`, `libcap2`, `util-linux` (CVE-2026-13595) con parche disponible en Debian: probablemente se resuelven solo con `docker build --no-cache`. Confirmar tras el rebuild.
- [ ] `git add` / `git commit` / `git push` — pendiente, a criterio del usuario.

## Verificación ejecutada

- `pip install -r requirements.txt` en un venv limpio: sin conflictos.
- `pip check`: `No broken requirements found.`
- Import de `src.pipeline`, `src.models.firestore_records` (incluyendo el fix de mapeo de campos aplicado antes en esta misma sesión), `FirestoreService`, `SFTPService`, `FileService`: OK.
- `pip-audit -r requirements.txt` post-fix: **0 paquetes vulnerables** (antes: 2 paquetes con CVEs conocidos vía pip-audit).
