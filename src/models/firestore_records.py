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
    agendar_llamada: Optional[str] = None
    
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

    def get_agendar_llamada(self) -> Optional[str]:
        """Extrae la fecha/hora de recontacto (guardada por el webhook post-call)."""
        return self.agendar_llamada or None

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

    def get_track_id(self) -> Optional[str]:
        """track_id enlaza la llamada con su fila original del archivo (registros_sftp)."""
        return self.dynamic_variables.get('track_id') or None
    
    def get_agent_name(self) -> str:
        """Extrae el nombre del agente."""
        #agent_name = self.dynamic_variables.get('agent_name', 'ZNT_NMV')
        agent_name = "ZNT_NMV"
        return str(agent_name)[:8]  # Máximo 8 caracteres

def format_phone_9_digits(phone_number: Optional[str]) -> str:
    """+56973788338 → 973788338 (mismo formato que la columna de teléfono del archivo del cliente)."""
    digits = ''.join(ch for ch in str(phone_number or '') if ch.isdigit())
    if len(digits) == 11 and digits.startswith('56'):
        digits = digits[2:]
    return digits


class ClientData(BaseModel):
    """
    Datos del deudor tal como venían en el archivo del cliente (registros_sftp),
    para que el reporte se pueda cruzar con la base que enviaron.
    """

    rut: str
    nombre: str = ""
    ciudad: str = ""
    telefono: str = ""
    monto_deuda: Optional[int] = None
    n_periodos: str = ""
    menor_periodo: str = ""
    mayor_periodo: str = ""
    tipo_cartera: str = ""


def _fecha_chile(value: datetime) -> str:
    chile_tz = pytz.timezone('America/Santiago')
    return value.replace(microsecond=0).astimezone(chile_tz).strftime("%d-%m-%Y %H:%M:%S")


class Document600(BaseModel):
    """Fila para el Excel de Promesas de Pago (PP)."""

    cliente: ClientData
    agent_id: str
    processed_at: datetime
    due_date: str
    conversation_id: str

    def to_row(self) -> Dict[str, Any]:
        """Construye una fila del Excel de Promesas de Pago (PP)."""
        return {
            "RUT Deudor": self.cliente.rut,
            "Nombre Deudor": self.cliente.nombre,
            "Teléfono Gestionado": self.cliente.telefono,
            "Monto Deuda ($)": self.cliente.monto_deuda,
            "Mayor Período de Deuda": self.cliente.mayor_periodo,
            "Fecha Gestión": _fecha_chile(self.processed_at),
            "Fecha Compromiso Pago": self.due_date,
            "Agente": self.agent_id,
            "ID Conversación": self.conversation_id,
        }


class Document200(BaseModel):
    """Fila para el Excel con todos los resultados de gestión."""

    cliente: ClientData
    processed_at: datetime
    codigo_resultado: str
    agent_name: str
    conversation_id: str
    call_duration: int = 0
    due_date: Optional[str] = None
    agendar_llamada: Optional[str] = None

    def to_row(self) -> Dict[str, Any]:
        """Construye una fila del Excel con todos los resultados."""
        return {
            "RUT Deudor": self.cliente.rut,
            "Nombre Deudor": self.cliente.nombre,
            "Ciudad": self.cliente.ciudad,
            "Teléfono Gestionado": self.cliente.telefono,
            "Monto Deuda ($)": self.cliente.monto_deuda,
            "N° Períodos": self.cliente.n_periodos,
            "Menor Período de Deuda": self.cliente.menor_periodo,
            "Mayor Período de Deuda": self.cliente.mayor_periodo,
            "Tipo de Cartera": self.cliente.tipo_cartera,
            "Fecha Gestión": _fecha_chile(self.processed_at),
            "Resultado": self.codigo_resultado,
            "Descripción Resultado": OutcomeMapping.get_description(self.codigo_resultado),
            "Fecha Compromiso Pago": self.due_date or "",
            "Fecha/Hora Recontacto": self.agendar_llamada or "",
            "Duración Llamada (s)": self.call_duration,
            "Agente": self.agent_name,
            "ID Conversación": self.conversation_id,
        }