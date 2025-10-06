"""
Modelos de datos específicos para la estructura de Firestore.
"""
from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import pytz

from src.utils.outcome_mapper import OutcomeMapping

class CallOutcome(str, Enum):
    """Resultados posibles de llamadas."""
    PP = "PP"  # Promesa de Pago
    NC = "NC"  # No Contacto
    CT = "Contacto"
    EE = "Vigente"

class FirestoreCallRecord(BaseModel):
    """Modelo para la estructura completa de registros de llamadas desde Firestore."""
    
    # Campos principales
    conversation_id: str
    status: str
    processed_at: str  # ISO datetime string
    call_duration_secs: int
    agent_id: str
    
    # Variables dinámicas
    dynamic_variables: Dict[str, Any]
    
    # Análisis de resultados
    analysis: Optional[Dict[str, Any]] = None
    evaluation_criteria_results: Optional[Dict[str, Any]] = None
    
    @validator('processed_at')
    def validate_processed_at(cls, v):
        """Valida que processed_at sea una fecha válida."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Fecha inválida: {v}")
    
    def get_rut(self) -> Optional[str]:
        """Extrae el RUT desde dynamic_variables."""
        rut = self.dynamic_variables.get('rut')
        if rut:
            # Convertir a string y limpiar
            rut_clean = str(rut).replace('.', '').replace('-', '').replace(' ', '')
            
            # Si tiene 9 dígitos, quitar el último (dígito verificador)
            if len(rut_clean) == 9:
                rut_clean = rut_clean[:-1]  # Quitar último dígito → 8 dígitos
            # Si tiene 8 dígitos, dejar tal cual (ya es el formato esperado)
            elif len(rut_clean) == 8:
                pass  # Ya tiene la longitud correcta
            # Si tiene menos de 8 dígitos, completar con ceros al inicio
            elif len(rut_clean) < 8:
                rut_clean = rut_clean.zfill(8)
            
            return rut_clean
        return None
    
    def get_final_call_outcome(self) -> Optional[str]:
        """Extrae el resultado final de la llamada con mapeo completo."""
        
        # Primero buscar en analysis
        if self.analysis and 'data_collection_results' in self.analysis:
            final_outcome = self.analysis['data_collection_results'].get('final_call_outcome', {})
            outcome_value = final_outcome.get('value')
            if outcome_value:
                return outcome_value
        
        # Buscar en evaluation_criteria_results
        if self.evaluation_criteria_results:
            # Buscar el campo 'analysis' que contiene el outcome
            analysis_data = self.evaluation_criteria_results.get('analysis', {})
            if isinstance(analysis_data, dict):
                outcome_value = analysis_data.get('value')
                if outcome_value:
                    return outcome_value
            
            # Fallback: Si hay criterios exitosos, asumir PP
            for criteria in self.evaluation_criteria_results.values():
                if isinstance(criteria, dict) and criteria.get('result') == 'success':
                    return "PP"
        
        return "NC"  # Por defecto No Contacto
    
    def get_processed_datetime(self) -> datetime:
        """Convierte processed_at a datetime."""
        return datetime.fromisoformat(self.processed_at.replace('Z', '+00:00'))
    
    def get_due_date(self) -> Optional[str]:
        """Extrae la fecha de vencimiento."""
        return self.dynamic_variables.get('overdue_date1')
    
    def get_amount_due(self) -> Optional[int]:
        """Extrae el monto adeudado."""
        amount = self.dynamic_variables.get('overdue_amount1')
        if amount:
            # Convertir a entero si es string
            return int(str(amount).replace(',', '').replace('.', ''))
        return None
    
    def get_phone_number(self) -> Optional[str]:
        """Extrae el número de teléfono."""
        return self.dynamic_variables.get('system__called_number')
    
    def get_agent_name(self) -> str:
        """Extrae el nombre del agente."""
        #agent_name = self.dynamic_variables.get('agent_name', 'ZNT_TRI')
        agent_name = "ZNT_TRI"
        return str(agent_name)[:8]  # Máximo 8 caracteres

class Document600(BaseModel):
    """Estructura para archivo 600 - Promesas de Pago."""
    
    rut: str
    agent_id: str
    processed_at: datetime
    due_date: str
    amount_due: int
    
    def build_line(self) -> str:
        """Construye una línea del archivo 600 con el formato exacto."""
        # Construir línea de exactamente 87 caracteres
        line = ""
        
        # Pos 1-3: "600"
        line += "600"
        
        # Pos 4: "6"
        line += "6"
        
        # Pos 5-29: Número de cuenta (25 caracteres, completar con espacios al final)
        numero_cuenta = f"TRI{self.rut}"
        line += numero_cuenta.ljust(25)[:25]
        
        # Pos 30-37: ID del gestor (8 caracteres, completar con espacios al final)
        gestor_id = str(self.agent_id)
        line += gestor_id.ljust(8)[:8]
        
        # Pos 38-39: Código de acción (2 espacios)
        line += "  "
        
        # Pos 40-41: Código de resultado "PP"
        line += "PP"
        
        # Pos 42-58: Fecha elaboración (17 caracteres, formato mmddyyyy hh:mm:ss)
        # Convertir a zona horaria de Chile (UTC-3)
        chile_tz = pytz.timezone('America/Santiago')
        processed_chile = self.processed_at.replace(microsecond=0).astimezone(chile_tz)
        fecha_elab = processed_chile.strftime("%m%d%Y %H:%M:%S")
        line += fecha_elab
        
        # Pos 59-61: (3 caracteres con espacios)
        line += "  "
        
        # Pos 62-64: Valor fijo "1" (3 caracteres con espacios)  
        line += "1  "
        #Pos 64: Espacio (1 carácter)
        line += "1"
        # Pos 65-72: Fecha vencimiento (8 caracteres, formato mmddyyyy)
        try:
            due_dt = datetime.strptime(self.due_date, "%d-%m-%Y")
            fecha_venc = due_dt.strftime("%m%d%Y")
            line += fecha_venc
        except:
            from datetime import timedelta
            fecha_venc = (self.processed_at + timedelta(days=30)).strftime("%m%d%Y")
            line += fecha_venc
        
        # Pos 73-87: Monto promesa (15 caracteres, completar con ceros al inicio)
        monto_str = str(self.amount_due).zfill(15)[:15]
        line += monto_str
        
        return line

class Document200(BaseModel):
    """Estructura para archivo 200 - Actividades de Gestión."""
    
    rut: str
    processed_at: datetime
    codigo_resultado: str
    agent_name: str
    phone_number: Optional[str] = None
    call_duration: int = 0
    
    def build_line(self) -> str:
        """Construye una línea del archivo 200 con el formato exacto."""
        # Construir línea de exactamente 175 caracteres
        line = ""
        
        # Pos 1-3: "200"
        line += "200"
        
        # Pos 4: "6"
        line += "6"
        
        # Pos 5-29: Número de cuenta (25 caracteres)
        numero_cuenta = f"TRI{self.rut}"
        line += numero_cuenta.ljust(25)[:25]
        
        # Pos 30-46: Fecha y hora de actividad (17 caracteres)
        # Convertir a zona horaria de Chile (UTC-3)
        chile_tz = pytz.timezone('America/Santiago')
        processed_chile = self.processed_at.replace(microsecond=0).astimezone(chile_tz)
        fecha_actividad = processed_chile.strftime("%m%d%Y %H:%M:%S")
        line += fecha_actividad
        
        # Pos 47-49: Vacío (3 espacios)
        line += "   "
        
        # Pos 50-51: Código de Acción (2 caracteres)
        codigo_accion = "EE"
        line += codigo_accion
        
        # Pos 52-53: Código de Resultado (2 caracteres)
        codigo_resultado = self.codigo_resultado.ljust(2)[:2]
        line += codigo_resultado
        
        # Pos 54-55: Código de Carta (2 espacios)
        line += "  "
        
        # Pos 56-63: Id Agente (8 caracteres)
        agente_id = self.agent_name.ljust(8)[:8]
        line += agente_id
        
        # Pos 64-119: Comentario (56 caracteres)
        comentario = OutcomeMapping.get_description(self.codigo_resultado)
        line += comentario.ljust(56)[:56]
        
        # Pos 120-132: Nro Teléfono (13 caracteres con ceros al inicio)
        if self.phone_number and str(self.phone_number).strip():
            # Limpiar formato internacional: +56930012345 → 30012345
            telefono_limpio = str(self.phone_number).strip()
            
            # Remover prefijos internacionales y caracteres especiales
            telefono_limpio = telefono_limpio.replace('+', '').replace('-', '').replace(' ', '')
            
            # Si empieza con 56 (código de Chile), removerlo
            if telefono_limpio.startswith('56'):
                telefono_limpio = telefono_limpio[2:]
            
            # Si empieza con 9, removerlo (código móvil)
            if telefono_limpio.startswith('9'):
                telefono_limpio = telefono_limpio[1:]
            
            # Completar con ceros al inicio hasta 13 dígitos
            telefono = telefono_limpio.zfill(13)[:13]
        else:
            telefono = "0".zfill(13)
        line += telefono
        
        # Pos 133-137: Cod Área (5 caracteres con ceros al inicio)
        if self.phone_number and str(self.phone_number).strip():
            # Extraer el primer dígito del número original
            telefono_original = str(self.phone_number).strip()
            telefono_original = telefono_original.replace('+', '').replace('-', '').replace(' ', '')
            
            # Si empieza con 56, tomar el primer dígito después del 56
            if telefono_original.startswith('56'):
                telefono_sin_codigo = telefono_original[2:]
                primer_digito = telefono_sin_codigo[0] if telefono_sin_codigo else "9"
            else:
                primer_digito = telefono_original[0] if telefono_original else "9"
        else:
            primer_digito = "9"
        
        cod_area = primer_digito.zfill(5)[:5]
        line += cod_area
        
        return line