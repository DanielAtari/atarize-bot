import os
import logging
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config.settings import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.chroma_db_path = os.path.join(self.base_dir, "chroma_db")
        
        # Initialize embedding function
        self.embedding_func = self.get_embedding_function()
        
        # Initialize ChromaDB client
        self.client = self.get_client()
        
        # Initialize collections
        self.knowledge_collection = None
        self.intents_collection = None
        self._initialize_collections()
        
        # Health check
        self._health_check()
    
    def get_embedding_function(self):
        """Get OpenAI embedding function"""
        try:
            return OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-large"
            )
        except Exception as e:
            logger.error(f"Failed to initialize embedding function: {e}")
            raise
    
    def get_client(self):
        """Get ChromaDB client"""
        try:
            return PersistentClient(path=self.chroma_db_path)
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    def _initialize_collections(self):
        """Initialize knowledge and intents collections"""
        try:
            self.knowledge_collection = self.client.get_or_create_collection(
                "atarize_knowledge", 
                embedding_function=self.embedding_func
            )
            logger.info("[CHROMA] Knowledge collection initialized")
            
            self.intents_collection = self.client.get_or_create_collection(
                "atarize_intents", 
                embedding_function=self.embedding_func
            )
            logger.info("[CHROMA] Intents collection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            raise
    
    def _health_check(self):
        """Check database health"""
        try:
            knowledge_count = self.knowledge_collection.count()
            intents_count = self.intents_collection.count()
            logger.info(f"[STARTUP] Knowledge collection: {knowledge_count} docs")
            logger.info(f"[STARTUP] Intents collection: {intents_count} docs")
            
            if knowledge_count == 0:
                logger.warning("⚠️ Knowledge collection is empty!")
            if intents_count == 0:
                logger.warning("⚠️ Intents collection is empty!")
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
    
    def get_knowledge_collection(self):
        """Get knowledge collection"""
        return self.knowledge_collection
    
    def get_intents_collection(self):
        """Get intents collection"""
        return self.intents_collection
    
    def get_context_from_chroma(self, question, collection):
        """Get context from ChromaDB collection"""
        try:
            results = collection.query(
                query_texts=[question],
                n_results=4
            )
            
            if results and results['documents']:
                context = "\n".join(results['documents'][0])
                logger.debug(f"[CHROMA] Retrieved context: {len(context)} chars")
                return context
            else:
                logger.debug("[CHROMA] No relevant context found")
                return ""
                
        except Exception as e:
            logger.error(f"Error retrieving context from ChromaDB: {e}")
            return ""
    
    def get_knowledge_by_intent(self, intent_name):
        """Get knowledge entries by intent name"""
        try:
            results = self.knowledge_collection.get(
                where={"intent": intent_name}
            )
            
            if results and results['documents']:
                return results['documents']
            else:
                logger.debug(f"No knowledge found for intent: {intent_name}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving knowledge by intent: {e}")
            return []
    
    def get_examples_by_intent(self, intent_name, n_examples=3):
        """Get example responses by intent"""
        try:
            results = self.knowledge_collection.get(
                where={"intent": intent_name},
                limit=n_examples
            )
            
            if results and results['documents']:
                return results['documents']
            else:
                logger.debug(f"No examples found for intent: {intent_name}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving examples by intent: {e}")
            return []
    
    def get_enhanced_context_retrieval(self, question, intent_name, lang="he", n_results=4):
        """Enhanced context retrieval with fallbacks"""
        try:
            # Try to get context by intent first
            intent_results = self.knowledge_collection.get(
                where={"intent": intent_name},
                limit=n_results
            )
            
            if intent_results and intent_results['documents']:
                context = "\n".join(intent_results['documents'])
                logger.debug(f"[ENHANCED] Retrieved {len(intent_results['documents'])} documents by intent")
                return context
            
            # Fallback to semantic search
            semantic_results = self.knowledge_collection.query(
                query_texts=[question],
                n_results=n_results
            )
            
            if semantic_results and semantic_results['documents']:
                context = "\n".join(semantic_results['documents'][0])
                logger.debug(f"[ENHANCED] Retrieved {len(semantic_results['documents'][0])} documents by semantic search")
                return context
            
            # Final fallback - get random documents
            all_results = self.knowledge_collection.get(limit=n_results)
            if all_results and all_results['documents']:
                context = "\n".join(all_results['documents'])
                logger.debug(f"[ENHANCED] Retrieved {len(all_results['documents'])} random documents as fallback")
                return context
            
            logger.warning("[ENHANCED] No context found with any method")
            return ""
            
        except Exception as e:
            logger.error(f"Error in enhanced context retrieval: {e}")
            return ""
    
    def get_enhanced_context_with_fallbacks(self, question, intent_name, lang, collection):
        """Get enhanced context with multiple fallback strategies"""
        # Strategy 1: Intent-based retrieval
        intent_context = self.get_knowledge_by_intent(intent_name)
        if intent_context:
            return "\n".join(intent_context)
        
        # Strategy 2: Semantic search
        semantic_context = self.get_context_from_chroma(question, collection)
        if semantic_context:
            return semantic_context
        
        # Strategy 3: Language-specific fallback
        lang_specific_results = collection.get(
            where={"language": lang},
            limit=2
        )
        if lang_specific_results and lang_specific_results['documents']:
            return "\n".join(lang_specific_results['documents'])
        
        # Strategy 4: General fallback
        general_results = collection.get(limit=2)
        if general_results and general_results['documents']:
            return "\n".join(general_results['documents'])
        
        return ""