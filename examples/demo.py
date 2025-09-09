#!/usr/bin/env python3
"""
Script de demostración del template de pipeline Python.
Este script muestra cómo usar el template para crear un pipeline personalizado.
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path para las importaciones
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import init_config
from src.services.file_service import FileService
from src.models.data_models import DataRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def demo_csv_processing():
    """
    Demostración de procesamiento de archivos CSV.
    """
    print("🚀 Iniciando demostración del template de pipeline Python")
    print("=" * 60)
    
    # Inicializar configuración
    config = init_config()
    logger.info("Configuración cargada: %s", config.app_name)
    
    # Crear servicio de archivos
    data_dir = Path(__file__).parent / "data"
    file_service = FileService(str(data_dir))
    
    try:
        # Conectar al servicio
        await file_service.connect()
        logger.info("✅ Conexión al servicio de archivos exitosa")
        
        # Extraer datos del CSV
        csv_file = "productos.csv"
        if not (data_dir / csv_file).exists():
            print(f"❌ Archivo {csv_file} no encontrado en {data_dir}")
            print("Por favor, asegúrate de que el archivo exista antes de continuar.")
            return
        
        raw_data = await file_service.extract(csv_file, "csv")
        logger.info("📊 Extraídos %d registros del archivo %s", len(raw_data), csv_file)
        
        # Procesar y validar datos
        valid_records = []
        errors = 0
        
        for i, row in enumerate(raw_data, 1):
            try:
                # Adaptar datos al modelo
                record_data = {
                    "id": int(row.get("id", 0)),
                    "name": str(row.get("name", "")),
                    "value": float(row.get("value", 0.0)) if row.get("value") else None,
                    "category": row.get("category", ""),
                    "is_active": str(row.get("is_active", "true")).lower() == "true"
                }
                
                # Validar usando Pydantic
                record = DataRecord(**record_data)
                valid_records.append(record)
                
                print(f"✅ Registro {i}: {record.name} - ${record.value}")
                
            except Exception as e:
                errors += 1
                logger.warning(f"❌ Error en registro {i}: {e}")
        
        print("\n📈 Resumen del procesamiento:")
        print(f"   • Total de registros: {len(raw_data)}")
        print(f"   • Registros válidos: {len(valid_records)}")
        print(f"   • Errores: {errors}")
        print(f"   • Tasa de éxito: {(len(valid_records)/len(raw_data)*100):.1f}%")
        
        # Guardar resultados procesados
        output_file = "productos_procesados.json"
        processed_data = [record.model_dump() for record in valid_records]
        await file_service.load(processed_data, output_file, "json")
        
        print(f"\n💾 Datos procesados guardados en: {data_dir / output_file}")
        
        # Mostrar estadísticas por categoría
        categories = {}
        for record in valid_records:
            cat = record.category
            if cat not in categories:
                categories[cat] = {"count": 0, "total_value": 0}
            categories[cat]["count"] += 1
            if record.value:
                categories[cat]["total_value"] += record.value
        
        print("\n📊 Estadísticas por categoría:")
        for cat, stats in categories.items():
            avg_value = stats["total_value"] / stats["count"] if stats["count"] > 0 else 0
            print(f"   • {cat}: {stats['count']} productos, valor promedio: ${avg_value:.2f}")
        
    except Exception as e:
        logger.exception(f"Error en la demostración: {e}")
        print(f"❌ Error: {e}")
    
    finally:
        if file_service.is_connected:
            await file_service.disconnect()
            logger.info("🔌 Conexión cerrada")
    
    print("\n🎉 Demostración completada!")


async def demo_validation():
    """
    Demostración de validación de datos.
    """
    print("\n" + "=" * 60)
    print("🔍 Demostración de validación de datos")
    print("=" * 60)
    
    # Datos de prueba con algunos errores
    test_data = [
        {"id": 1, "name": "Producto Válido", "value": 100.0, "category": "test"},
        {"id": "invalid", "name": "", "value": -50, "category": "test"},  # Errores múltiples
        {"id": 2, "name": "Otro Producto", "value": None, "category": "test"},  # Válido
    ]
    
    for i, data in enumerate(test_data, 1):
        try:
            record = DataRecord(**data)
            print(f"✅ Registro {i} válido: {record.name}")
        except Exception as e:
            print(f"❌ Registro {i} inválido: {e}")


if __name__ == "__main__":
    print("🐍 Template de Pipeline Python - Demostración")
    print("Este script muestra las capacidades del template")
    
    asyncio.run(demo_csv_processing())
    asyncio.run(demo_validation())
    
    print("\n📝 Para crear tu propio pipeline:")
    print("1. Copia este template a un nuevo proyecto")
    print("2. Modifica src/models/data_models.py para tus datos")
    print("3. Ajusta src/pipeline.py para tu lógica específica")
    print("4. Configura variables de entorno en .env")
    print("5. Ejecuta con: python src/main.py")
