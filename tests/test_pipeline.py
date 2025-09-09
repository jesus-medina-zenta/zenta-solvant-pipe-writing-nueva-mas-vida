"""
Tests para el pipeline principal.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.pipeline import Pipeline
from src.models.data_models import DataRecord


class TestPipeline:
    """Tests para la clase Pipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Fixture que retorna una instancia del pipeline."""
        return Pipeline()
    
    @pytest.fixture
    def sample_data(self):
        """Fixture con datos de muestra."""
        return [
            {
                "id": 1,
                "name": "Test Record 1",
                "value": 100.0,
                "category": "test",
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "id": 2,
                "name": "Test Record 2",
                "value": 200.0,
                "category": "test",
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
        ]
    
    @pytest.mark.asyncio
    async def test_extract_success(self, pipeline, sample_data):
        """Test de extracción exitosa."""
        # Mock del servicio de PostgreSQL
        pipeline.postgres_service.extract = AsyncMock(return_value=sample_data)
        
        result = await pipeline.extract()
        
        assert result == sample_data
        pipeline.postgres_service.extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_failure(self, pipeline):
        """Test de fallo en extracción."""
        # Mock que lanza excepción
        pipeline.postgres_service.extract = AsyncMock(side_effect=Exception("Database error"))
        
        result = await pipeline.extract()
        
        assert result == []
        pipeline.postgres_service.extract.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transform_success(self, pipeline, sample_data):
        """Test de transformación exitosa."""
        result = await pipeline.transform(sample_data)
        
        assert len(result) == len(sample_data)
        assert all(isinstance(record, DataRecord) for record in result)
    
    @pytest.mark.asyncio
    async def test_transform_invalid_data(self, pipeline):
        """Test de transformación con datos inválidos."""
        invalid_data = [
            {
                "id": "not_a_number",  # ID debe ser número
                "name": None,  # Name no puede ser None
                "value": "not_a_float",  # Value debe ser float
                "category": "",  # Category no puede estar vacío
                "is_active": "not_a_bool",  # is_active debe ser bool
                "created_at": "not_a_datetime"  # created_at debe ser datetime
            }
        ]
        
        result = await pipeline.transform(invalid_data)
        
        # Debe retornar lista vacía cuando todos los datos son inválidos
        assert result == []
    
    @pytest.mark.asyncio
    async def test_load_success(self, pipeline):
        """Test de carga exitosa."""
        # Crear registros válidos
        valid_records = []
        for i in range(3):
            record = Mock(spec=DataRecord)
            record.is_valid.return_value = True
            record.model_dump.return_value = {
                "id": i + 1,
                "name": f"Test Record {i + 1}",
                "value": (i + 1) * 100.0,
                "category": "test",
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
            valid_records.append(record)
        
        # Mock del servicio de BigQuery
        pipeline.bigquery_service.load = AsyncMock(return_value=True)
        
        result = await pipeline.load(valid_records)
        
        assert result is True
        # Verificar que se llamó al servicio de BigQuery (verificamos que se llamó, no los argumentos exactos)
        pipeline.bigquery_service.load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_failure(self, pipeline):
        """Test de fallo en carga."""
        # Crear registros válidos
        valid_records = []
        for i in range(2):
            record = Mock(spec=DataRecord)
            record.is_valid.return_value = True
            record.model_dump.return_value = {
                "id": i + 1,
                "name": f"Test Record {i + 1}",
                "value": (i + 1) * 100.0,
                "category": "test",
                "is_active": True,
                "created_at": datetime.now(timezone.utc)
            }
            valid_records.append(record)
        
        # Mock que falla
        pipeline.bigquery_service.load = AsyncMock(side_effect=Exception("BigQuery error"))
        
        result = await pipeline.load(valid_records)
        
        assert result is False
        # Verificar que se llamó al servicio de BigQuery
        pipeline.bigquery_service.load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, pipeline, sample_data):
        """Test del pipeline completo exitoso."""
        # Mock de todos los servicios
        pipeline.postgres_service.extract = AsyncMock(return_value=sample_data)
        pipeline.bigquery_service.load = AsyncMock(return_value=True)
        
        result = await pipeline.run()
        
        assert result is True
        assert pipeline.start_time is not None
        assert pipeline.end_time is not None
    
    @pytest.mark.asyncio
    async def test_pipeline_with_no_data(self, pipeline):
        """Test del pipeline cuando no hay datos."""
        # Mock que retorna lista vacía
        pipeline.postgres_service.extract = AsyncMock(return_value=[])
        
        result = await pipeline.run()
        
        assert result is True  # Pipeline exitoso aunque no haya datos
        assert pipeline.start_time is not None
        assert pipeline.end_time is not None
    
    @pytest.mark.asyncio
    async def test_validate_data_quality_success(self, pipeline):
        """Test de validación de calidad exitosa."""
        # Crear registros válidos
        valid_records = []
        for i in range(5):
            record = Mock(spec=DataRecord)
            record.is_valid.return_value = True
            valid_records.append(record)
        
        result = await pipeline.validate_data_quality(valid_records)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_data_quality_failure(self, pipeline):
        """Test de validación de calidad con fallo."""
        # Crear registros inválidos
        invalid_records = []
        for i in range(10):
            record = Mock(spec=DataRecord)
            record.is_valid.return_value = False
            invalid_records.append(record)
        
        result = await pipeline.validate_data_quality(invalid_records)
        
        assert result is False
    
    def test_pipeline_initialization(self, pipeline):
        """Test de inicialización del pipeline."""
        assert pipeline.postgres_service is not None
        assert pipeline.bigquery_service is not None
        assert pipeline.start_time is None
        assert pipeline.end_time is None
