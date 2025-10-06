# Agregar al inicio del archivo, después de CallOutcome
class OutcomeMapping:
    """Mapeo de códigos de resultado a descripciones."""
    
    OUTCOME_CODES = {
        "TA": "LLAMAR DESPUES",
        "PP": "COMPROMISO PAGO", 
        "CL": "CORTO LLAMADA",
        "DD": "NO RECONOCE",
        "YC": "YA PAGO",
        "DE": "SIN EMPLEO",
        "NC": "NO CONTACTADO",
        "LI": "CORTE TECNICO", 
        "IN": "NUMERO ERRONEO",
        "BV": "BUZON VOZ",
        "FO": "FALLECIDO"
    }
    
    @classmethod
    def get_description(cls, code: str) -> str:
        """Obtiene la descripción del código."""
        return cls.OUTCOME_CODES.get(code, "GESTION REALIZADA")