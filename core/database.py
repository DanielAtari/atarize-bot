import logging
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config.settings import Config

logger = logging.getLogger(__name__)

class ChromaDBManager:
    def __init__(self):
        self.embedding_func = OpenAIEmbeddingFunction(
            api_key=Config.OPENAI_API_KEY,
            model_name="text-embedding-3-large"
        )
        self.client = PersistentClient(path=Config.CHROMA_DB_PATH)
        self.knowledge_collection = None
        self.intents_collection = None
        self._initialize_collections()
        self._health_check()
    
    def _initialize_collections(self):
        """Initialize ChromaDB collections"""
        try:
            self.knowledge_collection = self.client.get_or_create_collection(
                "atarize_knowledge", 
                embedding_function=self.embedding_func
            )
            logger.info("[CHROMA] Knowledge collection initialized")
        except Exception as e:
            logger.error(f"[CHROMA] Failed to initialize knowledge collection: {e}")
        
        try:
            self.intents_collection = self.client.get_or_create_collection(
                "atarize_intents", 
                embedding_function=self.embedding_func
            )
            logger.info("[CHROMA] Intents collection initialized")
        except Exception as e:
            logger.warning(f"[CHROMA] Could not load intents collection: {e}")
    
    def _health_check(self):
        """Check collection health and log status"""
        try:
            knowledge_count = self.knowledge_collection.count() if self.knowledge_collection else 0
            intents_count = self.intents_collection.count() if self.intents_collection else 0
            
            logger.info(f"[STARTUP] Knowledge collection: {knowledge_count} docs")
            logger.info(f"[STARTUP] Intents collection: {intents_count} docs")
            
            if knowledge_count == 0:
                logger.warning("⚠️ Knowledge collection is empty!")
            if intents_count == 0:
                logger.warning("⚠️ Intents collection is empty!")
                
        except Exception as e:
            logger.error(f"❌ ChromaDB health check failed: {e}")
    
    def get_knowledge_collection(self):
        """Get the knowledge collection"""
        return self.knowledge_collection
    
    def get_intents_collection(self):
        """Get the intents collection"""
        return self.intents_collection
    
    def get_client(self):
        """Get the ChromaDB client"""
        return self.client
    
    def get_embedding_function(self):
        """Get the embedding function"""
        return self.embedding_func