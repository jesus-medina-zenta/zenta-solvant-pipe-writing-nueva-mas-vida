from typing import Optional
from google.cloud import firestore
from src.models.data_models import DataRecord
from src.utils.logger import get_logger
from ..config import get_firestore_config
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

    async def extract(self, collection: str, filters: Optional[list] = None, order_by: Optional[str] = None) -> list[dict]:
        if not self.is_connected or not self.client:
            raise RuntimeError("No hay conexión activa a Firestore. Llama a connect() primero.")
        
        try:
            collection_ref = self.client.collection(collection)
            query = collection_ref
            
            if filters:
                for f in filters:
                    query = query.where(f["field"], f["operator"], f["value"])
            
            if order_by:
                query = query.order_by(order_by)
            
            docs = query.stream()
            results = [doc.to_dict() for doc in docs]
            return results
        except Exception as e:
            logger.error("Error extrayendo datos de Firestore: %s", e, exc_info=True)
            return []