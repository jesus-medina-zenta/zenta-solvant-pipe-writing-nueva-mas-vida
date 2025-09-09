"""
Ejemplo de uso de validadores personalizados.
"""
from src.utils.validators import DataValidator, CommonValidators, SchemaValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


def ejemplo_validador_basico():
    """Ejemplo de uso del validador básico."""
    print("🔍 Ejemplo: Validador Básico")
    
    # Crear validador
    validator = DataValidator()
    
    # Añadir reglas personalizadas
    validator.add_rule("email", CommonValidators.is_valid_email, "Email inválido")
    validator.add_rule("edad", CommonValidators.is_positive_number, "Edad debe ser positiva")
    validator.add_rule("nombre", CommonValidators.not_empty_string, "Nombre no puede estar vacío")
    
    # Datos de prueba
    datos = [
        {"email": "usuario@example.com", "edad": 25, "nombre": "Juan"},
        {"email": "email_invalido", "edad": -5, "nombre": ""},  # Inválido
        {"email": "maria@test.com", "edad": 30, "nombre": "María"}
    ]
    
    # Validar
    resultado = validator.validate_batch(datos)
    
    print(f"📊 Registros totales: {resultado['total_records']}")
    print(f"✅ Registros válidos: {resultado['valid_count']}")
    print(f"❌ Registros inválidos: {resultado['invalid_count']}")
    print(f"📈 Tasa de éxito: {resultado['success_rate']:.1f}%")
    
    if resultado['all_errors']:
        print("🚨 Errores encontrados:")
        for error in resultado['all_errors']:
            print(f"  - {error}")


def ejemplo_validador_esquema():
    """Ejemplo de uso del validador de esquema."""
    print("\n🏗️ Ejemplo: Validador de Esquema")
    
    # Definir esquema
    esquema = {
        "id": {
            "type": int,
            "required": True,
            "validators": [CommonValidators.is_positive_number]
        },
        "nombre": {
            "type": str,
            "required": True,
            "validators": [
                CommonValidators.not_empty_string,
                CommonValidators.min_length(2),
                CommonValidators.max_length(100)
            ]
        },
        "categoria": {
            "type": str,
            "required": False,
            "validators": [CommonValidators.is_in_choices(["A", "B", "C"])]
        },
        "precio": {
            "type": float,
            "required": True,
            "nullable": False,
            "validators": [CommonValidators.is_in_range(0.0, 1000.0)]
        }
    }
    
    validator = SchemaValidator(esquema)
    
    # Datos de prueba
    datos_prueba = [
        {
            "id": 1,
            "nombre": "Producto A",
            "categoria": "A",
            "precio": 99.99
        },
        {
            "id": -1,  # Inválido: negativo
            "nombre": "",  # Inválido: vacío
            "categoria": "X",  # Inválido: no está en opciones
            "precio": 1500.0  # Inválido: fuera de rango
        },
        {
            # Falta "id" requerido
            "nombre": "Producto C",
            "precio": 50.0
        }
    ]
    
    for i, datos in enumerate(datos_prueba):
        print(f"\n📋 Validando registro {i + 1}: {datos}")
        es_valido = validator.validate(datos)
        
        if es_valido:
            print("✅ Registro válido")
        else:
            print("❌ Registro inválido:")
            for error in validator.get_errors():
                print(f"  - {error}")


def ejemplo_validadores_personalizados():
    """Ejemplo de creación de validadores personalizados."""
    print("\n🛠️ Ejemplo: Validadores Personalizados")
    
    # Validador personalizado para códigos de producto
    def validar_codigo_producto(valor):
        """Valida que el código tenga formato PRD-XXXX."""
        if not isinstance(valor, str):
            return False
        import re
        patron = r'^PRD-\d{4}$'
        return re.match(patron, valor) is not None
    
    # Validador personalizado para rangos de fecha
    def validar_fecha_reciente(valor):
        """Valida que la fecha sea de los últimos 30 días."""
        from datetime import datetime, timedelta
        if not isinstance(valor, str):
            return False
        try:
            fecha = datetime.fromisoformat(valor.replace('Z', '+00:00'))
            hace_30_dias = datetime.now() - timedelta(days=30)
            return fecha >= hace_30_dias
        except:
            return False
    
    # Crear validador con reglas personalizadas
    validator = DataValidator()
    validator.add_rule("codigo", validar_codigo_producto, "Código debe tener formato PRD-XXXX")
    validator.add_rule("fecha", validar_fecha_reciente, "Fecha debe ser de los últimos 30 días")
    
    # Datos de prueba
    from datetime import datetime, timedelta
    fecha_valida = datetime.now().isoformat() + 'Z'
    fecha_antigua = (datetime.now() - timedelta(days=45)).isoformat() + 'Z'
    
    datos = [
        {"codigo": "PRD-1234", "fecha": fecha_valida},  # Válido
        {"codigo": "INVALID", "fecha": fecha_antigua},  # Inválido
        {"codigo": "PRD-5678", "fecha": fecha_valida}   # Válido
    ]
    
    resultado = validator.validate_batch(datos)
    
    print(f"📊 Resultado de validación personalizada:")
    print(f"✅ Válidos: {resultado['valid_count']}/{resultado['total_records']}")
    
    if resultado['all_errors']:
        print("🚨 Errores:")
        for error in resultado['all_errors']:
            print(f"  - {error}")


if __name__ == "__main__":
    ejemplo_validador_basico()
    ejemplo_validador_esquema()
    ejemplo_validadores_personalizados()
    print("\n🎉 ¡Ejemplos de validación completados!")
