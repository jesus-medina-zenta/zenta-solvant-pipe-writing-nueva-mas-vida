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

    # Guardado por el webhook de post-call directamente en la raíz del documento
    fecha_compromiso: Optional[str] = None
    
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
        rut = self.dynamic_variables.get('rut_deudor')
        if rut:
            # Convertir a string y limpiar
            rut_clean = str(rut).replace('.', '').replace('-', '').replace(' ', '')
            
            # Si tiene 9 dígitos, quitar el último (dígito verificador)
            if len(rut_clean) == 9:
                rut_clean = rut_clean[:-1]  # Quitar último dígito → 8 dígitos
            # Si tiene 8 dígitos, dejar tal cual (ya es el formato esperado)
            elif len(rut_clean) == 8:
                rut_clean = rut_clean[:-1]
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
        """Extrae la fecha de compromiso de pago (guardada por el webhook post-call)."""
        return self.fecha_compromiso or None

    def get_amount_due(self) -> Optional[int]:
        """Extrae el monto adeudado."""
        amount = self.dynamic_variables.get('deuda_cotizaciones')
        if amount:
            # Convertir a entero si es string
            return int(str(amount).replace(',', '').replace('.', ''))
        return None
    
    def get_phone_number(self) -> Optional[str]:
        """Extrae el número de teléfono."""
        return self.dynamic_variables.get('system__called_number')
    
    def get_agent_name(self) -> str:
        """Extrae el nombre del agente."""
        #agent_name = self.dynamic_variables.get('agent_name', 'ZNT_NMV')
        agent_name = "ZNT_NMV"
        return str(agent_name)[:8]  # Máximo 8 caracteres

def _format_phone(phone_number: Optional[str]) -> str:
    """Limpia el formato internacional del teléfono: +56930012345 → 30012345."""
    if not phone_number or not str(phone_number).strip():
        return ""
    telefono_limpio = str(phone_number).strip().replace('+', '').replace('-', '').replace(' ', '')
    if telefono_limpio.startswith('56'):
        telefono_limpio = telefono_limpio[2:]
    if telefono_limpio.startswith('9'):
        telefono_limpio = telefono_limpio[1:]
    return telefono_limpio


class Document600(BaseModel):
    """Fila para el Excel de Promesas de Pago (PP)."""

    rut: str
    agent_id: str
    processed_at: datetime
    due_date: str
    amount_due: int

    def to_row(self) -> Dict[str, Any]:
        """Construye una fila del Excel de Promesas de Pago (PP)."""
        chile_tz = pytz.timezone('America/Santiago')
        processed_chile = self.processed_at.replace(microsecond=0).astimezone(chile_tz)

        return {
            "RUT": self.rut,
            "Agente": self.agent_id,
            "Fecha Procesada": processed_chile.strftime("%d-%m-%Y %H:%M:%S"),
            "Fecha Compromiso": self.due_date,
            "Monto Adeudado": self.amount_due,
        }


class Document200(BaseModel):
    """Fila para el Excel con todos los resultados de gestión."""

    rut: str
    processed_at: datetime
    codigo_resultado: str
    agent_name: str
    phone_number: Optional[str] = None
    call_duration: int = 0

    def to_row(self) -> Dict[str, Any]:
        """Construye una fila del Excel con todos los resultados."""
        chile_tz = pytz.timezone('America/Santiago')
        processed_chile = self.processed_at.replace(microsecond=0).astimezone(chile_tz)

        return {
            "RUT": self.rut,
            "Agente": self.agent_name,
            "Fecha Procesada": processed_chile.strftime("%d-%m-%Y %H:%M:%S"),
            "Resultado": self.codigo_resultado,
            "Descripción Resultado": OutcomeMapping.get_description(self.codigo_resultado),
            "Teléfono": _format_phone(self.phone_number),
            "Duración Llamada (s)": self.call_duration,
        }