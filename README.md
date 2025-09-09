# 🐍 Template de Pipeline ETL Python - Zenta

**Autor:** Marcos Valdés  
**Empresa:** Zenta  
**Versión:** 2.0  
**Estado:** Production Ready 🚀

Este es un template profesional para crear pipelines de datos ETL (Extract, Transform, Load) en Python, diseñado para ser desplegado en Google Cloud Run Jobs. Construido con las mejores prácticas de desarrollo y arquitectura moderna.

## 🎯 ¿Por qué usar este template?

- ✅ **Arquitectura probada**: Modular, escalable y mantenible
- ✅ **Tecnologías modernas**: Python 3.12+, Pydantic v2, async/await
- ✅ **Observabilidad completa**: Logging estructurado, métricas y trazabilidad
- ✅ **DevOps ready**: Docker, CI/CD, Cloud Run deployment
- ✅ **Calidad de código**: Tests automatizados, type hints, documentación
- ✅ **Listo para producción**: 23/23 tests pasando, validación completa

## 🏗️ Arquitectura del Template

### Diseño Modular

```
📦 znt-template-pipe-python/
├── 🐍 src/                     # Código fuente principal
│   ├── 📝 main.py             # Punto de entrada con manejo de errores
│   ├── ⚙️ config.py           # Configuración centralizada con Pydantic v2
│   ├── 🔄 pipeline.py         # Lógica ETL principal con async/await
│   ├── 📊 models/             # Modelos de datos con validación
│   │   └── data_models.py     # DataRecord, ProcessingStats, ErrorRecord
│   ├── 🔌 services/           # Conectores modulares para fuentes de datos
│   │   ├── base_service.py    # Servicio base abstracto
│   │   ├── postgres_service.py # Conector PostgreSQL con pool async
│   │   ├── bigquery_service.py # Conector Google BigQuery
│   │   └── file_service.py    # Manejo de archivos (CSV, JSON, Parquet, Excel)
│   └── 🛠️ utils/              # Utilidades del sistema
│       ├── logger.py          # Sistema de logging estructurado
│       └── validators.py      # Validadores personalizados
├── 🧪 tests/                   # Suite completa de pruebas
│   ├── test_pipeline.py       # Tests del pipeline principal
│   └── test_services.py       # Tests de servicios
├── 🎯 examples/                # Ejemplos listos para usar
│   ├── demo.py               # Demostración interactiva
│   ├── csv_to_bigquery_pipeline.py # Pipeline CSV → BigQuery
│   └── validation_examples.py # Ejemplos de validación
├── 📜 scripts/                 # Scripts de automatización
│   ├── setup.sh              # Configuración automática del entorno
│   ├── test.sh               # Ejecución de tests
│   └── deploy.sh             # Deployment a Cloud Run
├── 🐳 Dockerfile              # Containerización multi-stage
├── ☁️ cloudbuild.yaml         # CI/CD con Google Cloud Build
├── 🔧 pyproject.toml          # Configuración moderna de Python
└── 📖 README.md               # Esta documentación
```

### Componentes Clave

#### 🔌 **Servicios (src/services/)**
- **BaseService**: Clase abstracta con patrones comunes de conexión y gestión de errores
- **PostgresService**: Conector asíncrono con pool de conexiones y reconexión automática
- **BigQueryService**: Integración completa con Google BigQuery, manejo de datasets y tablas
- **FileService**: Soporte para múltiples formatos (CSV, JSON, Parquet, Excel)

#### 📊 **Modelos (src/models/)**
- **DataRecord**: Modelo base con validación Pydantic v2, campos datetime timezone-aware
- **ProcessingStats**: Métricas de rendimiento y estadísticas del pipeline
- **ErrorRecord**: Gestión estructurada de errores con contexto completo
- **PipelineConfig**: Configuración específica del pipeline

#### 🛠️ **Utilidades (src/utils/)**
- **Logger**: Sistema de logging estructurado con contexto y niveles configurables
- **Validators**: Validadores personalizados para casos de uso específicos

## 🚀 Inicio Rápido

### 1. Clonar y configurar

```bash
# Clonar el template
git clone <url-del-template> mi-pipeline-proyecto
cd mi-pipeline-proyecto

# Configurar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Para desarrollo
```

### 2. Configurar variables de entorno

```bash
# Copiar archivo de configuración
cp .env.example .env

# Editar con tus credenciales
nano .env
```

**Variables principales:**
```bash
# Configuración general
APP_NAME=mi-pipeline-proyecto
LOG_LEVEL=INFO
ENVIRONMENT=dev

# PostgreSQL
POSTGRES_HOST=tu-host-postgresql
POSTGRES_PORT=5432
POSTGRES_DATABASE=tu-database
POSTGRES_USER=tu-usuario
POSTGRES_PASSWORD=tu-password

# Google Cloud / BigQuery
BIGQUERY_PROJECT_ID=tu-proyecto-gcp
BIGQUERY_DATASET=tu-dataset
BIGQUERY_TABLE=tu-tabla
BIGQUERY_LOCATION=us-central1

# Autenticación Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=./tu-service-account.json
```

### 3. Ejecutar demo

```bash
# Demo interactivo con datos de ejemplo
python examples/demo.py

# Pipeline principal PostgreSQL → BigQuery
python -m src.main
```

## 📊 Ejemplos de Uso

### 1. Pipeline Básico (PostgreSQL → BigQuery)

```python
import asyncio
from src.pipeline import Pipeline

async def ejecutar_pipeline():
    pipeline = Pipeline()
    success = await pipeline.run()
    
    if success:
        print("✅ Pipeline ejecutado exitosamente")
    else:
        print("❌ Pipeline falló")

# Ejecutar
asyncio.run(ejecutar_pipeline())
```

### 2. Pipeline con Archivos CSV

```python
from src.services.file_service import FileService
from src.services.bigquery_service import BigQueryService

async def csv_to_bigquery():
    # Extracción
    file_service = FileService("./data")
    data = await file_service.extract("productos.csv", "csv")
    
    # Transformación (usar tus modelos)
    processed_data = [transform_record(row) for row in data]
    
    # Carga
    bq_service = BigQueryService()
    success = await bq_service.load(processed_data)
    
    return success
```

### 3. Validación de Datos Personalizada

```python
from src.models.data_models import DataRecord
from pydantic import ValidationError

def validar_datos(raw_data):
    valid_records = []
    errors = []
    
    for row in raw_data:
        try:
            # Validación automática con Pydantic
            record = DataRecord(**row)
            valid_records.append(record)
        except ValidationError as e:
            errors.append({"row": row, "error": str(e)})
    
    return valid_records, errors
```

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
python -m pytest

# Con cobertura de código
python -m pytest --cov=src --cov-report=html

# Tests específicos
python -m pytest tests/test_pipeline.py -v

# Tests con logging detallado
python -m pytest -s tests/test_services.py
```

### Suite de Tests Actual

- **✅ 23 tests pasando** (100% success rate)
- **✅ Tests unitarios**: Funcionalidad individual de componentes
- **✅ Tests de integración**: Pipeline completo end-to-end
- **✅ Tests asíncronos**: Validación de operaciones async/await
- **✅ Mocking avanzado**: Simulación de servicios externos

### Estructura de Tests

```
tests/
├── test_pipeline.py          # 11 tests del pipeline principal
│   ├── ✅ test_pipeline_init
│   ├── ✅ test_extract_success
│   ├── ✅ test_transform_valid_data
│   ├── ✅ test_transform_invalid_data
│   ├── ✅ test_load_success
│   └── ✅ test_run_complete_pipeline
└── test_services.py          # 12 tests de servicios
    ├── ✅ test_postgres_connection
    ├── ✅ test_bigquery_connection
    ├── ✅ test_file_service_csv
    └── ✅ test_data_validation
```

## 🔧 Personalización del Template

### 1. Modificar Modelos de Datos

```python
# src/models/data_models.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class MiModeloPersonalizado(BaseModel):
    """Modelo específico para mi caso de uso."""
    
    id: int = Field(..., description="ID único")
    nombre: str = Field(..., min_length=1, max_length=255)
    precio: Optional[float] = Field(None, ge=0)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Validadores personalizados
    @field_validator('nombre')
    @classmethod
    def validar_nombre(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip().title()
```

### 2. Añadir Nuevos Servicios

```python
# src/services/mi_nuevo_servicio.py
from .base_service import BaseService
from typing import List, Dict, Any

class MiNuevoServicio(BaseService):
    """Conector para mi fuente de datos específica."""
    
    async def connect(self) -> bool:
        """Implementar conexión específica."""
        try:
            # Tu lógica de conexión
            self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            return False
    
    async def extract(self, query: str) -> List[Dict[str, Any]]:
        """Extraer datos de tu fuente."""
        # Tu lógica de extracción
        pass
    
    async def load(self, data: List[Dict[str, Any]]) -> bool:
        """Cargar datos a tu destino."""
        # Tu lógica de carga
        pass
```

### 3. Personalizar Lógica del Pipeline

```python
# src/pipeline.py - Modificar métodos según tu caso de uso

async def extract(self) -> List[Dict[str, Any]]:
    """Personalizar extracción según tu fuente."""
    try:
        # Ejemplo: múltiples fuentes
        query = """
        SELECT id, nombre, precio, categoria, fecha_creacion
        FROM mi_tabla_especifica
        WHERE fecha_creacion >= CURRENT_DATE - INTERVAL '1 day'
        ORDER BY fecha_creacion DESC
        """
        
        data = await self.postgres_service.extract(query)
        logger.info(f"Extraídos {len(data)} registros de mi_tabla_especifica")
        return data
        
    except Exception as e:
        logger.error(f"Error en extracción personalizada: {e}")
        return []

async def transform(self, raw_data: List[Dict[str, Any]]) -> List[MiModeloPersonalizado]:
    """Transformación específica para tu caso de uso."""
    transformed_data = []
    
    for row in raw_data:
        try:
            # Aplicar transformaciones específicas
            row['precio'] = row.get('precio', 0) * 1.21  # Agregar IVA
            row['categoria'] = row.get('categoria', '').upper()
            
            # Validar con tu modelo
            record = MiModeloPersonalizado(**row)
            transformed_data.append(record)
            
        except Exception as e:
            logger.warning(f"Error transformando registro: {e}")
    
    return transformed_data
```

## 🚀 Deployment

### Google Cloud Run

```bash
# Usar script automático
./scripts/deploy.sh

# O manual paso a paso
gcloud builds submit --config cloudbuild.yaml .

# Deployment directo con Docker
docker build -t mi-pipeline .
docker tag mi-pipeline gcr.io/mi-proyecto/mi-pipeline
docker push gcr.io/mi-proyecto/mi-pipeline

gcloud run jobs create mi-pipeline-job \
    --image gcr.io/mi-proyecto/mi-pipeline \
    --region us-central1 \
    --set-env-vars LOG_LEVEL=INFO
```

### Variables de Entorno en Cloud Run

```bash
# Configurar secrets para credenciales sensibles
gcloud secrets create postgres-password --data-file=- <<< "tu-password"

# Configurar variables en el job
gcloud run jobs update mi-pipeline-job \
    --set-env-vars LOG_LEVEL=INFO,ENVIRONMENT=production \
    --set-secrets POSTGRES_PASSWORD=postgres-password:latest
```

### Configuración de CI/CD

El archivo `cloudbuild.yaml` incluye:
- ✅ **Build automatizado**: Construcción de imagen Docker
- ✅ **Tests en pipeline**: Ejecución automática de tests
- ✅ **Deploy condicional**: Deployment solo si tests pasan
- ✅ **Versionado**: Tags automáticos por commit

## 📈 Monitoreo y Observabilidad

### Logging Estructurado

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Logs con contexto
logger.info("Iniciando procesamiento", extra={
    "batch_size": 1000,
    "source": "postgresql",
    "destination": "bigquery"
})

# Métricas automáticas
logger.info(f"Procesados {len(data)} registros en {duration:.2f} segundos")
```

### Métricas Incluidas

- **✅ Tiempos de ejecución**: Por etapa (extract, transform, load)
- **✅ Contadores**: Registros procesados, errores, éxitos
- **✅ Calidad de datos**: Porcentaje de validación exitosa
- **✅ Recursos**: Uso de memoria y conexiones

## 🔒 Mejores Prácticas Incluidas

### Seguridad
- ✅ **Variables de entorno** para credenciales
- ✅ **Google Secrets Manager** integration
- ✅ **No hardcoding** de passwords
- ✅ **Logging seguro** (sin exponer credenciales)

### Performance
- ✅ **Async/await** para operaciones I/O
- ✅ **Pool de conexiones** para PostgreSQL
- ✅ **Procesamiento por lotes** configurable
- ✅ **Gestión de memoria** eficiente

### Mantenibilidad
- ✅ **Type hints** completos en Python
- ✅ **Docstrings** en español
- ✅ **Separación de responsabilidades**
- ✅ **Configuración centralizada**

### Robustez
- ✅ **Retry logic** con backoff exponencial
- ✅ **Manejo de errores** granular
- ✅ **Validación de datos** automática
- ✅ **Logging de errores** con contexto

## 🆘 Troubleshooting

### Errores Comunes

**1. Error de importación relativa**
```bash
# ❌ Incorrecto
python src/main.py

# ✅ Correcto
python -m src.main
```

**2. Error de datetime serialization**
```python
# ❌ Problema: Object of type datetime is not JSON serializable
# ✅ Solución: Ya implementada con model_dump(mode='json')
```

**3. Error de conexión BigQuery**
```bash
# Verificar credenciales
export GOOGLE_APPLICATION_CREDENTIALS="./tu-service-account.json"

# Verificar permisos del service account
gcloud projects get-iam-policy tu-proyecto
```

**4. Tests fallando**
```bash
# Ejecutar con más detalle
python -m pytest -v -s tests/

# Verificar dependencias
pip install -r requirements-dev.txt
```

## 📚 Recursos Adicionales

### Documentación Interna
- 📝 **examples/demo.py**: Demostración interactiva paso a paso
- 🎯 **examples/validation_examples.py**: Casos de validación avanzada
- 🧪 **tests/**: Tests como documentación de uso

### Enlaces Útiles
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [Google Cloud BigQuery Python Client](https://cloud.google.com/bigquery/docs/reference/libraries)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/current/)
- [Google Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)

## 🤝 Contribuir al Template

### Para mejorar este template:

1. **Fork** el repositorio
2. **Crea una rama** para tu feature (`git checkout -b feature/mi-mejora`)
3. **Implementa** tu mejora con tests
4. **Ejecuta tests** (`python -m pytest`)
5. **Commit** tus cambios (`git commit -am 'Añadir mi mejora'`)
6. **Push** a la rama (`git push origin feature/mi-mejora`)
7. **Abre un Pull Request**

### Estándares de contribución:
- ✅ **Tests obligatorios** para nueva funcionalidad
- ✅ **Documentación** actualizada
- ✅ **Type hints** en todo el código nuevo
- ✅ **Logging apropiado** para debugging

## 📄 Licencia

Este proyecto está bajo la **Licencia MIT**. Ver el archivo `LICENSE` para más detalles.

---

## 👨‍💻 Créditos

**Desarrollado por:** Marcos Valdés  
**Empresa:** Zenta  
**Fecha:** Junio 2025  

**Template optimizado para pipelines ETL de producción con Python 3.12+, Pydantic v2 y Google Cloud Platform.**

---

*¿Tienes preguntas o necesitas ayuda? Consulta los ejemplos en `examples/` o revisa los tests en `tests/` para ver casos de uso específicos.*
