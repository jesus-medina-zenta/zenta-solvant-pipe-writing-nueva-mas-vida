"""
Modelos de datos específicos para la estructura de Firestore.
"""
from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

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
            # Remover dígito verificador y normalizar
            rut_clean = str(rut).split('-')[0].replace('.', '')
            # Si tiene menos de 8 dígitos, anteponer 0
            if len(rut_clean) < 8:
                rut_clean = rut_clean.zfill(8)
            return rut_clean
        return None
    
    def get_final_call_outcome(self) -> Optional[str]:
        """Extrae el resultado final de la llamada."""
        if self.analysis and 'data_collection_results' in self.analysis:
            final_outcome = self.analysis['data_collection_results'].get('final_call_outcome', {})
            return final_outcome.get('value')
        
        # Fallback: buscar en evaluation_criteria_results
        if self.evaluation_criteria_results:
            for criteria in self.evaluation_criteria_results.values():
                if isinstance(criteria, dict) and criteria.get('result') == 'success':
                    return "PP"  # Si hay éxito en criterios, es promesa de pago
        
        return "NC"  # Por defecto No Contacto
    
    def get_processed_datetime(self) -> datetime:
        """Convierte processed_at a datetime."""
        return datetime.fromisoformat(self.processed_at.replace('Z', '+00:00'))
    
    def get_due_date(self) -> Optional[str]:
        """Extrae la fecha de vencimiento."""
        return self.dynamic_variables.get('due_date')
    
    def get_amount_due(self) -> Optional[int]:
        """Extrae el monto adeudado."""
        amount = self.dynamic_variables.get('amount_due')
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
        fecha_elab = self.processed_at.strftime("%m%d%Y %H:%M:%S")
        line += fecha_elab.ljust(17)[:17]
        
        # Pos 59-61: Valor fijo "1" (3 caracteres con espacios)
        line += "1  "
        
        # Pos 62-64: Valor fijo "1" (3 caracteres con espacios)  
        line += "1  "
        
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
        fecha_actividad = self.processed_at.strftime("%m%d%Y %H:%M:%S")
        line += fecha_actividad.ljust(17)[:17]
        
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
        comentario_map = {
            "NC": "SIN CONTACTO",
            "PP": "PROMESA DE PAGO REALIZADA",
            "CT": "CONTACTO REALIZADO",
            "TC": "UBICABLE SIN COMPROMISO",
            "IN": "INUBICABLE",
            "AT": "SE DEJA RECADO"
        }
        comentario = comentario_map.get(self.codigo_resultado, "GESTION REALIZADA")
        line += comentario.ljust(56)[:56]
        
        # Pos 120-132: Nro Teléfono (13 caracteres con ceros al inicio)
        if self.phone_number:
            telefono = str(self.phone_number).lstrip('9')
            telefono = telefono.zfill(13)[:13]
        else:
            telefono = "0".zfill(13)
        line += telefono
        
        # Pos 133-137: Cod Área (5 caracteres con ceros al inicio)
        if self.phone_number:
            primer_digito = str(self.phone_number)[0] if self.phone_number else "9"
        else:
            primer_digito = "9"
        cod_area = primer_digito.zfill(5)[:5]
        line += cod_area
        
        return line