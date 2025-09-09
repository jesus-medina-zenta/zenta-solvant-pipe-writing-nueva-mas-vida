"""
Modelos de datos usando Pydantic para validación.
"""
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class DataRecord(BaseModel):
    """
    Modelo base para registros de datos.
    Personaliza este modelo según tus necesidades específicas.
    """
    
    id: int = Field(..., description="Identificador único del registro")
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del registro")
    value: Optional[float] = Field(None, description="Valor numérico opcional")
    category: Optional[str] = Field(None, max_length=100, description="Categoría del registro")
    is_active: bool = Field(True, description="Indica si el registro está activo")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de creación")
    updated_at: Optional[datetime] = Field(None, description="Fecha de última actualización")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadatos adicionales en formato JSON")
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        """Valida que el nombre no esté vacío."""
        if not v or not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()
    
    @field_validator('value')
    @classmethod
    def value_must_be_positive_if_present(cls, v):
        """Valida que el valor sea positivo si está presente."""
        if v is not None and v < 0:
            raise ValueError('El valor debe ser positivo')
        return v
    
    @model_validator(mode='after')
    def validate_updated_at_after_created_at(self):
        """Valida que updated_at sea posterior a created_at."""
        if self.updated_at and self.created_at and self.updated_at < self.created_at:
            raise ValueError('La fecha de actualización debe ser posterior a la fecha de creación')
        return self
    
    def is_valid(self) -> bool:
        """
        Verifica si el registro es válido según reglas de negocio.
        
        Returns:
            bool: True si el registro es válido
        """
        # Implementa aquí reglas de validación específicas de tu negocio
        return (
            self.id > 0 and
            len(self.name.strip()) > 0 and
            (self.value is None or self.value >= 0)
        )
    
    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Registro de ejemplo",
                "value": 100.50,
                "category": "ejemplo",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "metadata": {"source": "api", "version": "1.0"}
            }
        }
    )


class ProcessingStats(BaseModel):
    """
    Modelo para estadísticas de procesamiento del pipeline.
    """
    
    total_records: int = Field(0, description="Total de registros procesados")
    successful_records: int = Field(0, description="Registros procesados exitosamente")
    failed_records: int = Field(0, description="Registros que fallaron")
    processing_time_seconds: float = Field(0.0, description="Tiempo total de procesamiento en segundos")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Tiempo de inicio")
    end_time: Optional[datetime] = Field(None, description="Tiempo de finalización")
    
    @property
    def success_rate(self) -> float:
        """Calcula la tasa de éxito del procesamiento."""
        if self.total_records == 0:
            return 0.0
        return (self.successful_records / self.total_records) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calcula la tasa de fallo del procesamiento."""
        return 100.0 - self.success_rate
    
    def add_success(self) -> None:
        """Incrementa el contador de registros exitosos."""
        self.successful_records += 1
        self.total_records += 1
    
    def add_failure(self) -> None:
        """Incrementa el contador de registros fallidos."""
        self.failed_records += 1
        self.total_records += 1
    
    def finish(self) -> None:
        """Marca el procesamiento como finalizado."""
        self.end_time = datetime.now(datetime.timezone.utc)
        if self.start_time:
            self.processing_time_seconds = (self.end_time - self.start_time).total_seconds()


class ErrorRecord(BaseModel):
    """
    Modelo para registrar errores durante el procesamiento.
    """
    
    record_id: Optional[str] = Field(None, description="ID del registro que causó el error")
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp del error")
    stage: str = Field(..., description="Etapa del pipeline donde ocurrió el error")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Datos en bruto que causaron el error")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record_id": "123",
                "error_type": "ValidationError",
                "error_message": "El campo 'name' es requerido",
                "timestamp": "2023-01-01T12:00:00Z",
                "stage": "transform",
                "raw_data": {"id": 123, "value": 100}
            }
        }
    )


class PipelineConfig(BaseModel):
    """
    Modelo para configuración específica del pipeline.
    """
    
    source_query: Optional[str] = Field(None, description="Consulta SQL para extraer datos")
    batch_size: int = Field(1000, gt=0, description="Tamaño del lote para procesamiento")
    max_retries: int = Field(3, ge=0, description="Máximo número de reintentos")
    enable_validation: bool = Field(True, description="Habilitar validación de datos")
    output_format: str = Field("json", description="Formato de salida")
    custom_filters: Optional[Dict[str, Any]] = Field(None, description="Filtros personalizados")
    
    @field_validator('output_format')
    @classmethod
    def validate_output_format(cls, v):
        """Valida que el formato de salida sea soportado."""
        supported_formats = ['json', 'csv', 'parquet']
        if v not in supported_formats:
            raise ValueError(f'Formato no soportado. Use uno de: {supported_formats}')
        return v
