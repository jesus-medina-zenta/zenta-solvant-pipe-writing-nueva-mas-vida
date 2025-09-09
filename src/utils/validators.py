"""
Validadores de datos para el pipeline.
"""
from typing import List, Dict, Any, Optional, Callable
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Excepción personalizada para errores de validación."""
    pass


class DataValidator:
    """
    Validador de datos con reglas personalizables.
    """
    
    def __init__(self):
        """Inicializa el validador con reglas básicas."""
        self.rules = {}
        self.errors = []
    
    def add_rule(self, field: str, rule: Callable[[Any], bool], 
                 error_message: str) -> None:
        """
        Añade una regla de validación para un campo.
        
        Args:
            field: Nombre del campo
            rule: Función que retorna True si es válido
            error_message: Mensaje de error si la validación falla
        """
        if field not in self.rules:
            self.rules[field] = []
        
        self.rules[field].append({
            'rule': rule,
            'message': error_message
        })
    
    def validate_record(self, record: Dict[str, Any]) -> bool:
        """
        Valida un registro individual.
        
        Args:
            record: Registro a validar
            
        Returns:
            bool: True si el registro es válido
        """
        is_valid = True
        record_errors = []
        
        for field, rules in self.rules.items():
            value = record.get(field)
            
            for rule_config in rules:
                try:
                    if not rule_config['rule'](value):
                        error_msg = f"{field}: {rule_config['message']}"
                        record_errors.append(error_msg)
                        is_valid = False
                except Exception as e:
                    error_msg = f"{field}: Error en validación - {str(e)}"
                    record_errors.append(error_msg)
                    is_valid = False
        
        if record_errors:
            self.errors.extend(record_errors)
        
        return is_valid
    
    def validate_batch(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Valida un lote de registros.
        
        Args:
            records: Lista de registros a validar
            
        Returns:
            Dict con estadísticas de validación
        """
        self.errors.clear()
        valid_records = []
        invalid_records = []
        
        for i, record in enumerate(records):
            if self.validate_record(record):
                valid_records.append(record)
            else:
                invalid_records.append({
                    'index': i,
                    'record': record,
                    'errors': self.errors[-len([e for e in self.errors if str(i) in e]):]
                })
        
        return {
            'total_records': len(records),
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'valid_count': len(valid_records),
            'invalid_count': len(invalid_records),
            'success_rate': (len(valid_records) / len(records)) * 100 if records else 0,
            'all_errors': self.errors
        }
    
    def clear_errors(self) -> None:
        """Limpia la lista de errores."""
        self.errors.clear()


# Validadores predefinidos comunes
class CommonValidators:
    """Colección de validadores comunes."""
    
    @staticmethod
    def not_null(value: Any) -> bool:
        """Valida que el valor no sea None."""
        return value is not None
    
    @staticmethod
    def not_empty_string(value: Any) -> bool:
        """Valida que el string no esté vacío."""
        return isinstance(value, str) and len(value.strip()) > 0
    
    @staticmethod
    def is_positive_number(value: Any) -> bool:
        """Valida que el número sea positivo."""
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def is_valid_email(value: Any) -> bool:
        """Valida formato de email."""
        if not isinstance(value, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, value) is not None
    
    @staticmethod
    def is_valid_date(value: Any, date_format: str = "%Y-%m-%d") -> bool:
        """Valida formato de fecha."""
        if not isinstance(value, str):
            return False
        
        try:
            datetime.strptime(value, date_format)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def min_length(min_len: int) -> Callable[[Any], bool]:
        """Retorna validador de longitud mínima."""
        def validator(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            return len(value) >= min_len
        return validator
    
    @staticmethod
    def max_length(max_len: int) -> Callable[[Any], bool]:
        """Retorna validador de longitud máxima."""
        def validator(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            return len(value) <= max_len
        return validator
    
    @staticmethod
    def is_in_range(min_val: float, max_val: float) -> Callable[[Any], bool]:
        """Retorna validador de rango numérico."""
        def validator(value: Any) -> bool:
            try:
                num_value = float(value)
                return min_val <= num_value <= max_val
            except (TypeError, ValueError):
                return False
        return validator
    
    @staticmethod
    def is_in_choices(choices: List[Any]) -> Callable[[Any], bool]:
        """Retorna validador de opciones válidas."""
        def validator(value: Any) -> bool:
            return value in choices
        return validator
    
    @staticmethod
    def matches_pattern(pattern: str) -> Callable[[Any], bool]:
        """Retorna validador de expresión regular."""
        compiled_pattern = re.compile(pattern)
        
        def validator(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            return compiled_pattern.match(value) is not None
        return validator


class SchemaValidator:
    """
    Validador basado en esquema para estructuras de datos complejas.
    """
    
    def __init__(self, schema: Dict[str, Dict[str, Any]]):
        """
        Inicializa el validador con un esquema.
        
        Args:
            schema: Definición del esquema
                    Formato: {
                        'campo': {
                            'type': str|int|float|bool|datetime,
                            'required': True|False,
                            'validators': [list of validators],
                            'nullable': True|False
                        }
                    }
        """
        self.schema = schema
        self.errors = []
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Valida datos contra el esquema.
        
        Args:
            data: Datos a validar
            
        Returns:
            bool: True si los datos son válidos
        """
        self.errors.clear()
        is_valid = True
        
        # Validar campos requeridos
        for field, config in self.schema.items():
            if config.get('required', False) and field not in data:
                self.errors.append(f"Campo requerido faltante: {field}")
                is_valid = False
                continue
            
            if field not in data:
                continue
            
            value = data[field]
            
            # Validar nullabilidad
            if value is None:
                if not config.get('nullable', False):
                    self.errors.append(f"Campo {field} no puede ser null")
                    is_valid = False
                continue
            
            # Validar tipo
            expected_type = config.get('type')
            if expected_type and not isinstance(value, expected_type):
                self.errors.append(f"Campo {field} debe ser de tipo {expected_type.__name__}")
                is_valid = False
                continue
            
            # Validar con validadores personalizados
            validators = config.get('validators', [])
            for validator in validators:
                if callable(validator):
                    try:
                        if not validator(value):
                            self.errors.append(f"Validación fallida para campo {field}")
                            is_valid = False
                    except Exception as e:
                        self.errors.append(f"Error en validación de {field}: {str(e)}")
                        is_valid = False
        
        return is_valid
    
    def get_errors(self) -> List[str]:
        """Retorna la lista de errores de validación."""
        return self.errors.copy()


def create_default_validator() -> DataValidator:
    """
    Crea un validador con reglas comunes predefinidas.
    
    Returns:
        DataValidator: Validador configurado
    """
    validator = DataValidator()
    
    # Reglas comunes para IDs
    validator.add_rule(
        'id',
        CommonValidators.not_null,
        'ID no puede ser null'
    )
    
    validator.add_rule(
        'id',
        CommonValidators.is_positive_number,
        'ID debe ser un número positivo'
    )
    
    # Reglas comunes para nombres
    validator.add_rule(
        'name',
        CommonValidators.not_empty_string,
        'Nombre no puede estar vacío'
    )
    
    validator.add_rule(
        'name',
        CommonValidators.max_length(255),
        'Nombre no puede exceder 255 caracteres'
    )
    
    return validator
