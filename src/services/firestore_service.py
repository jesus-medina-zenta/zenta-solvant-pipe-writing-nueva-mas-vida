from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from google.cloud import firestore
from src.models.data_models import DataRecord
from src.utils.logger import get_logger
from src.config import get_firestore_config
import os
from dotenv import load_dotenv
load_dotenv()

logger = get_logger(__name__)

class FirestoreService:
    def __init__(self):
        self.client: Optional[firestore.Client] = None
        self.firestore_config = get_firestore_config()
        self.project_id = self.firestore_config.project_id
        self.collection = self.firestore_config.collection
        self.database = self.firestore_config.database
        self.agent_id = self.firestore_config.agent_id
        self.is_connected = False

    def connect(self) -> bool:
        if self.is_connected and self.client:
            return True
            
        try:
            if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS no está configurado.")
            
            logger.info("Conectando a Firestore")
            self.client = firestore.Client(
                project=self.project_id, 
                database=self.database
            )
            
            # Validar conexión real
            self.client.collection(self.collection).limit(1).get()
            
            self.is_connected = True
            logger.info("Conexión establecida exitosamente")
            return True
        except Exception as e:
            logger.error("Error conectando a Firestore: %s", e, exc_info=True)
            self.is_connected = False
            return False

    def get_source_records(self, track_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Busca las filas originales del archivo del cliente (registros_sftp) por
        track_id. Devuelve {track_id: documento}. Firestore acepta hasta 30
        valores por consulta 'in', así que se consulta por bloques.
        """
        unique_ids = [t for t in dict.fromkeys(track_ids) if t]
        records: Dict[str, Dict[str, Any]] = {}
        if not unique_ids:
            return records

        collection_ref = self.client.collection(self.firestore_config.source_collection)
        for start in range(0, len(unique_ids), 30):
            chunk = unique_ids[start:start + 30]
            for doc in collection_ref.where("track_id", "in", chunk).stream():
                data = doc.to_dict() or {}
                if data.get("track_id"):
                    records[data["track_id"]] = data

        logger.info(f"{len(records)}/{len(unique_ids)} registros de origen encontrados en '{self.firestore_config.source_collection}'")
        return records

    def disconnect(self) -> None:
        if self.client:
            self.client = None
            self.is_connected = False
            logger.info("Conexión a Firestore cerrada")

    def save_transformed_records(self, records: list, carga_id: str):
        collection_ref = self.client.collection(self.collection)
        for idx, record in enumerate(records):
            if isinstance(record, DataRecord):
                record_dict = record.model_dump(mode="json")
            else:
                record_dict = record
            doc_id = f"{carga_id}_{idx+1}"
            collection_ref.document(doc_id).set(record_dict)
        logger.info(f"{len(records)} registros guardados en la colección '{self.collection}'")

    def extract(self, collection: str, **kwargs) -> list[dict]:
        if not self.is_connected or not self.client:
            raise RuntimeError("No hay conexión activa a Firestore. Llama a connect() primero.")
        
        try:
            #obtener colección
            collection_ref = self.client.collection(collection)

            #construir query hacia la colección
            query = collection_ref

            #filtro: agent_id
            query = self._apply_agent_filter(query)

            #filtro 2: fecha actual
            #query = self._apply_today_filter(query)

            #ordenar por fecha
            #query = query.order_by("processed_at", direction=firestore.Query.DESCENDING)

            docs = query.stream()
            
            documents = []
            today = datetime.now(timezone.utc).date()
            logger.info(f"Filtrando registros del día: {today.isoformat()}")
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data['document_id'] = doc.id
                if self._is_today_record(doc_data, today):
                    documents.append(doc_data)
            
            logger.info(f"{len(documents)} documentos extraídos de la colección '{collection}' para el agente '{self.agent_id}'")
            return documents
        except Exception as e:
            logger.error("Error extrayendo datos de Firestore: %s", e, exc_info=True)
            return []
    
    def _is_today_record(self, doc_data: Dict[str, Any], today: datetime.date) -> bool:
        """
        Verifica si un registro es del día actual.
        """
        try:
            processed_at_str = doc_data.get('processed_at')
            if not processed_at_str:
                logger.warning(f"Documento {doc_data.get('document_id')} sin campo 'processed_at'")
                return False
            
            # Manejar diferentes formatos de fecha
            processed_at_str = str(processed_at_str)
            
            # Formato: "2025-09-22T17:14:53.316Z"
            if processed_at_str.endswith('Z'):
                processed_at_str = processed_at_str.replace('Z', '+00:00')
            
            # Convertir a datetime
            processed_dt = datetime.fromisoformat(processed_at_str)
            
            # Convertir a UTC si no tiene timezone
            if processed_dt.tzinfo is None:
                processed_dt = processed_dt.replace(tzinfo=timezone.utc)
            
            # Comparar solo la fecha (sin hora)
            processed_date = processed_dt.date()
            
            is_today = processed_date == today
            
            if is_today:
                logger.debug(f"Registro del día actual: {processed_at_str}")
            
            return is_today
        except Exception as e:
            logger.warning(f"Error procesando fecha 'processed_at' en documento {doc_data.get('document_id')}: {e}")
            return False

    def _apply_agent_filter(self, query):
        """
        Aplica filtro OBLIGATORIO por ID de agente.
        """
        try:
            logger.info(f"FILTRO OBLIGATORIO - Agente: {self.agent_id}")
            
            # Filtrar por agent_id
            query = query.where(
                "agent_id", "==", self.agent_id
            )
            
            return query
            
        except Exception as e:
            logger.error(f"Error aplicando filtro de agente: {e}")
            raise e  # Re-lanzar error porque es filtro obligatorio