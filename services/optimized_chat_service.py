import logging
import os
import json
import hashlib
import time
from config.settings import Config
from utils.text_utils import detect_language, is_greeting, get_natural_greeting, is_small_talk
from utils.validation_utils import detect_lead_info, is_vague_gpt_answer
from utils.token_utils import count_tokens, log_token_usage
from services.advanced_cache_service import AdvancedCacheService
from services.response_variation_service import ResponseVariationService
from services.context_manager import context_manager
from services.fast_response_service import fast_response_service

logger = logging.getLogger(__name__)

class OptimizedChatService:
    def __init__(self, db_manager, openai_client):
        self.db_manager = db_manager
        self.openai_client = openai_client
        
        # Enhanced caching for better performance
        self.cache_manager = AdvancedCacheService(
            max_size=2000,  # Larger cache for better hit rates
            default_ttl=7200  # 2 hour default TTL
        )
        
        # Response variation service
        self.response_variation = ResponseVariationService()
        
        # Load system prompt and intents
        self._load_system_prompt()
        self._load_intents()
    
    def _load_system_prompt(self):
        """Load system prompt from file"""
        try:
            system_prompt_path = os.path.join(Config.DATA_DIR, "system_prompt_atarize.txt")
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
                logger.info("[OPTIMIZED_CHAT] System prompt loaded successfully")
        except Exception as e:
            logger.error(f"[OPTIMIZED_CHAT] Failed to load system prompt: {e}")
            self.system_prompt = "You are a helpful assistant for Atarize."
    
    def _load_intents(self):
        """Load intents configuration from file"""
        try:
            intents_path = os.path.join(Config.DATA_DIR, "intents_config.json")
            with open(intents_path, "r", encoding="utf-8") as f:
                self.intents = json.load(f)
                logger.info(f"[OPTIMIZED_CHAT] Loaded {len(self.intents)} intents")
        except Exception as e:
            logger.error(f"[OPTIMIZED_CHAT] Failed to load intents: {e}")
            self.intents = []
    

    
    def handle_question(self, question, session):
        """Optimized main chat handling logic"""
        start_time = time.time()
        
        # Initialize session
        if "history" not in session:
            session["history"] = []
        if "greeted" not in session:
            session["greeted"] = False
        
        # Check cache first
        cached_response = self.cache_manager.get(question, session)
        if cached_response:
            logger.info(f"[OPTIMIZED_CHAT] Cache hit: {time.time() - start_time:.2f}s")
            self._update_session(question, cached_response, session)
            return cached_response, session
        
        # Enhanced context retrieval with timeout
        context = self._get_optimized_context(question, session)
        
        # Generate response with performance monitoring
        answer = self._generate_optimized_response(question, session, context)
        
        # Cache the response
        self.cache_manager.set(question, answer, session)
        
        # Update session
        self._update_session(question, answer, session)
        
        total_time = time.time() - start_time
        logger.info(f"[OPTIMIZED_CHAT] Total response time: {total_time:.2f}s")
        
        return answer, session
    

    
    def _get_optimized_context(self, question, session):
        """Optimized context retrieval with timeout"""
        try:
            knowledge_collection = self.db_manager.get_knowledge_collection()
            if not knowledge_collection:
                return ""
            
            lang = detect_language(question)
            
            # Fast single query with timeout
            results = knowledge_collection.query(
                query_texts=[question],
                n_results=2,  # Reduced for speed
                where={"language": lang} if lang else None,
                include=["documents", "metadatas"]
            )
            
            if not results or not results.get("documents"):
                return ""
            
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            
            # Build context string
            context_parts = []
            for doc, meta in zip(docs, metas):
                intent = meta.get("intent", "")
                category = meta.get("category", "")
                context_parts.append(f"Context ({category}): {doc}")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"[OPTIMIZED_CHAT] Context retrieval failed: {e}")
            return ""
    
    def _generate_optimized_response(self, question, session, context):
        """Generate optimized AI response"""
        try:
            lang = detect_language(question)
            
            # Enhanced prompt for intelligent, context-aware responses
            if context:
                prompt = f"""User question: {question}

Available context:
{context}

Provide a helpful, accurate, and contextual response. Be conversational and professional.
Only mention pricing if specifically asked about costs or pricing.
Respond naturally without pushing information unless relevant to the question.
Language: {lang}"""
            else:
                prompt = f"""User question: {question}

Provide a helpful response about Atarize chatbot services.
Only mention pricing if specifically asked about costs or pricing.
Respond naturally without pushing information unless relevant to the question.
Language: {lang}"""
            
            # Optimized OpenAI call
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            # Reduced token usage for speed
            completion = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=400  # Increased to prevent truncation
            )
            
            answer = completion.choices[0].message.content.strip()
            
            # Ensure complete sentence
            if not answer.endswith(('.', '!', '?')):
                answer += '.'
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPTIMIZED_CHAT] Response generation failed: {e}")
            return self._generate_fallback_response(question, session)
    
    def _generate_fallback_response(self, question, session):
        """Generate fallback response"""
        lang = detect_language(question)
        
        if lang == "he":
            return "תודה על השאלה! אני עטרה מבית Atarize. אוכל לעזור לך עם מידע על הצ'אטבוטים שלנו. מה מעניין אותך?"
        else:
            return "Thanks for your question! I'm Atara from Atarize. I can help you with information about our chatbots. What interests you?"
    
    def _update_session(self, question, answer, session):
        """Update session with new conversation"""
        session["history"].append({
            "question": question,
            "answer": answer,
            "timestamp": time.time()
        })
        
        # Keep only last 5 messages for performance
        if len(session["history"]) > 5:
            session["history"] = session["history"][-5:]
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return self.cache_manager.get_stats()
    
    def clear_cache(self):
        """Clear all caches"""
        self.cache_manager.clear()
        logger.info("[OPTIMIZED_CHAT] All caches cleared") 