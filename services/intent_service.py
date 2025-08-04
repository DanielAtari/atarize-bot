import logging
from rapidfuzz import fuzz
from config.settings import Config

logger = logging.getLogger(__name__)

class IntentService:
    def __init__(self, intents_collection=None):
        self.intents_collection = intents_collection
    
    def detect_intent_fuzzy(self, user_input, intents, threshold=70):
        """Detect intent using fuzzy string matching"""
        if not user_input or not intents:
            return None
        
        user_input = user_input.lower().strip()
        best_intent = None
        best_score = 0
        
        logger.debug(f"[INTENT_FUZZY] Testing input: '{user_input}' against {len(intents)} intents")
        
        for intent in intents:
            intent_name = intent.get("intent", "")
            triggers = intent.get("triggers", [])
            
            for trigger in triggers:
                score = fuzz.partial_ratio(user_input, trigger.lower())
                logger.debug(f"[INTENT_FUZZY] '{user_input}' vs '{trigger}' → Score: {score}")
                
                if score > best_score:
                    best_score = score
                    best_intent = intent
        
        if best_score >= threshold:
            logger.info(f"[INTENT_FUZZY] ✅ Match found: {best_intent.get('intent')} (score: {best_score})")
            return {
                "intent": best_intent.get("intent"),
                "confidence": best_score,
                "method": "fuzzy",
                "metadata": best_intent
            }
        else:
            logger.debug(f"[INTENT_FUZZY] ❌ No match above threshold {threshold}. Best score: {best_score}")
            return None
    
    def detect_intent_chroma(self, user_question, threshold=1.2):
        """Detect intent using ChromaDB semantic search"""
        if not self.intents_collection:
            logger.warning("[INTENT_CHROMA] Intents collection not available")
            return None
        
        try:
            logger.debug(f"[INTENT_CHROMA] Querying ChromaDB for: '{user_question}'")
            
            results = self.intents_collection.query(
                query_texts=[user_question],
                n_results=1,
                include=["distances", "documents", "metadatas"]
            )
            
            if not results["distances"] or not results["distances"][0]:
                logger.debug("[INTENT_CHROMA] No results returned from ChromaDB")
                return None
            
            top_distance = results["distances"][0][0]
            top_metadata = results["metadatas"][0][0] if results["metadatas"][0] else {}
            
            logger.debug(f"[INTENT_CHROMA] Top match distance: {top_distance} (threshold: {threshold})")
            
            if top_distance < threshold:
                intent_name = top_metadata.get("intent", "unknown")
                logger.info(f"[INTENT_CHROMA] ✅ Match found: {intent_name} (distance: {top_distance})")
                
                return {
                    "intent": intent_name,
                    "confidence": 1.0 - (top_distance / 2.0),  # Convert distance to confidence
                    "method": "chroma",
                    "distance": top_distance,
                    "metadata": top_metadata
                }
            else:
                logger.debug(f"[INTENT_CHROMA] ❌ Distance {top_distance} above threshold {threshold}")
                return None
                
        except Exception as e:
            logger.error(f"[INTENT_CHROMA] Error in ChromaDB query: {e}")
            return None
    
    def detect_intent(self, user_input, intents):
        """Combined intent detection using both fuzzy and ChromaDB"""
        logger.debug(f"[INTENT_DETECTION] Starting intent detection for: '{user_input}'")
        
        # Try ChromaDB first (more accurate)
        chroma_result = self.detect_intent_chroma(user_input, Config.CHROMA_THRESHOLD)
        
        # Try fuzzy matching
        fuzzy_result = self.detect_intent_fuzzy(user_input, intents, Config.FUZZY_THRESHOLD)
        
        # Priority: ChromaDB > Fuzzy > None
        if chroma_result:
            logger.info(f"[INTENT_DETECTION] Using ChromaDB result: {chroma_result['intent']}")
            return chroma_result
        elif fuzzy_result:
            logger.info(f"[INTENT_DETECTION] Using fuzzy result: {fuzzy_result['intent']}")
            return fuzzy_result
        else:
            logger.debug("[INTENT_DETECTION] No intent detected")
            return None