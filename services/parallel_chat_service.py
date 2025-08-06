import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Tuple
from services.chat_service import ChatService

logger = logging.getLogger(__name__)

class ParallelChatService:
    """
    Parallel processing wrapper for ChatService using threading instead of asyncio.
    More stable with Flask and provides faster first-time responses through parallel operations.
    """
    
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        self.executor = ThreadPoolExecutor(max_workers=3)  # Conservative worker count
        
        # Common questions for pre-warming cache
        self.common_questions = [
            "כמה עולה השירות?",
            "מה המחיר?", 
            "איך זה עובד?",
            "מה התכונות?",
            "איך משלבים את זה?",
            "יש תמיכה?",
            "כמה זמן לוקח ההטמעה?",
            "יש הדגמה?",
            "What's the pricing?",
            "How does it work?",
            "What features are included?"
        ]
        
        self.is_pre_warming = False
        
        logger.info("[PARALLEL_CHAT] 🚀 Initialized parallel chat service for faster responses")
    
    def handle_question_parallel(self, question: str, session: Dict, timeout: float = 30.0) -> Tuple[str, Dict]:
        """
        Parallel version of handle_question with optimized processing
        """
        start_time = time.time()
        logger.info(f"[PARALLEL_CHAT] ⚡ Starting parallel processing for: '{question[:30]}...'")
        
        try:
            # Check cache first - this is always fast
            cached_response = self._check_cache_quickly(question, session)
            
            if cached_response:
                logger.info(f"[PARALLEL_CHAT] 🎯 Cache hit! Response time: {time.time() - start_time:.3f}s")
                session["history"].append({"role": "assistant", "content": cached_response})
                return cached_response, session
            
            logger.info("[PARALLEL_CHAT] 🔄 Cache miss - using parallel context retrieval")
            
            # For first-time responses, get context in parallel with other operations
            future_context = self.executor.submit(self._get_context_threaded, question)
            future_language = self.executor.submit(self._detect_language_threaded, question)
            
            # Wait for both with timeout
            try:
                context = future_context.result(timeout=15.0)
                language = future_language.result(timeout=2.0)
            except Exception as e:
                logger.warning(f"[PARALLEL_CHAT] Parallel operation failed: {e}, using sequential")
                context = self.chat_service._get_context_from_chroma(question, session)
                from utils.text_utils import detect_language
                language = detect_language(question)
            
            # Generate response with enhanced context
            if context and len(context) > 50:
                response = self.chat_service._generate_ai_response_with_enhanced_context(question, session, context)
            else:
                response = self.chat_service._generate_ai_response(question, session)
            
            # Cache the result for future use
            self._cache_response_quickly(question, session, response)
            
            # Add to session history
            session["history"].append({"role": "assistant", "content": response})
            
            total_time = time.time() - start_time
            logger.info(f"[PARALLEL_CHAT] ✅ Parallel response generated in {total_time:.3f}s")
            
            return response, session
            
        except Exception as e:
            logger.error(f"[PARALLEL_CHAT] ❌ Error in parallel processing: {e}")
            # Fallback to synchronous processing
            logger.info("[PARALLEL_CHAT] 🔄 Falling back to synchronous processing")
            return self.chat_service.handle_question(question, session)
    
    def _check_cache_quickly(self, question: str, session: Dict) -> Optional[str]:
        """Quick cache check without complex key generation"""
        try:
            import hashlib
            simple_key = hashlib.md5(f"{question}_{session.get('greeted', False)}".encode()).hexdigest()[:12]
            return self.chat_service.cache_manager.get(simple_key)
        except:
            return None
    
    def _cache_response_quickly(self, question: str, session: Dict, response: str):
        """Quick cache storage"""
        try:
            import hashlib
            simple_key = hashlib.md5(f"{question}_{session.get('greeted', False)}".encode()).hexdigest()[:12]
            self.chat_service.cache_manager.set(simple_key, response, ttl=1800)
        except Exception as e:
            logger.debug(f"[PARALLEL_CHAT] Cache storage failed: {e}")
    
    def _get_context_threaded(self, question: str) -> str:
        """Get context from ChromaDB in separate thread"""
        try:
            return self.chat_service._get_context_from_chroma(question, {})
        except Exception as e:
            logger.warning(f"[PARALLEL_CHAT] Context retrieval failed: {e}")
            return ""
    
    def _detect_language_threaded(self, question: str) -> str:
        """Detect language in separate thread"""
        try:
            from utils.text_utils import detect_language
            return detect_language(question)
        except Exception as e:
            logger.warning(f"[PARALLEL_CHAT] Language detection failed: {e}")
            return "he"  # Default to Hebrew
    
    def pre_warm_cache_threaded(self, max_questions: int = 5):
        """Pre-warm cache with common questions using threading"""
        if self.is_pre_warming:
            logger.info("[PARALLEL_CHAT] ⚠️ Pre-warming already in progress")
            return
        
        self.is_pre_warming = True
        logger.info(f"[PARALLEL_CHAT] 🔥 Starting threaded cache pre-warming with {max_questions} questions")
        start_time = time.time()
        
        # Create a clean session for pre-warming
        clean_session = {
            "history": [],
            "greeted": False,
            "intro_given": False,
            "lead_collected": False,
            "interested_lead_pending": False,
            "product_market_fit_detected": False
        }
        
        # Pre-warm a limited set of questions
        questions_to_warm = self.common_questions[:max_questions]
        
        # Use threading for pre-warming
        futures = []
        for question in questions_to_warm:
            future = self.executor.submit(self._pre_warm_single_question, question, clean_session.copy())
            futures.append(future)
        
        # Wait for completion with timeout
        completed = 0
        for future in as_completed(futures, timeout=30):
            try:
                future.result()
                completed += 1
                logger.debug(f"[PARALLEL_CHAT] Pre-warming progress: {completed}/{len(questions_to_warm)}")
            except Exception as e:
                logger.warning(f"[PARALLEL_CHAT] Pre-warming task failed: {e}")
        
        pre_warm_time = time.time() - start_time
        logger.info(f"[PARALLEL_CHAT] ✅ Pre-warming completed: {completed}/{len(questions_to_warm)} in {pre_warm_time:.2f}s")
        
        # Log cache statistics
        try:
            cache_stats = self.chat_service.cache_manager.get_stats()
            logger.info(f"[PARALLEL_CHAT] 📊 Cache now has {cache_stats['total_entries']} entries")
        except Exception as e:
            logger.debug(f"[PARALLEL_CHAT] Could not get cache stats: {e}")
        
        self.is_pre_warming = False
    
    def _pre_warm_single_question(self, question: str, session: Dict):
        """Pre-warm cache for a single question"""
        try:
            logger.debug(f"[PARALLEL_CHAT] 🔥 Pre-warming: '{question}'")
            # Use the regular chat service for pre-warming to avoid recursion
            self.chat_service.handle_question(question, session)
        except Exception as e:
            logger.warning(f"[PARALLEL_CHAT] ⚠️ Failed to pre-warm '{question}': {e}")
    
    def start_background_pre_warming(self):
        """Start pre-warming in background thread"""
        def pre_warm_worker():
            time.sleep(2)  # Small delay to let the server start
            self.pre_warm_cache_threaded(max_questions=5)
        
        pre_warm_thread = threading.Thread(target=pre_warm_worker, daemon=True)
        pre_warm_thread.start()
        logger.info("[PARALLEL_CHAT] 🚀 Background pre-warming started")
    
    def get_parallel_stats(self) -> Dict[str, Any]:
        """Get parallel processing statistics"""
        try:
            cache_stats = self.chat_service.cache_manager.get_stats()
            
            return {
                "parallel_processing": "Enabled (Threading)",
                "max_workers": self.executor._max_workers,
                "pre_warm_questions": len(self.common_questions),
                "cache_entries": cache_stats["total_entries"],
                "cache_hit_rate": f"{cache_stats.get('hit_rate_percent', 0):.1f}%",
                "pre_warming_active": self.is_pre_warming,
                "optimization_status": "Parallel processing with threading (Flask-compatible)"
            }
        except Exception as e:
            logger.debug(f"[PARALLEL_CHAT] Stats error: {e}")
            return {
                "parallel_processing": "Enabled (Threading)",
                "max_workers": self.executor._max_workers,
                "status": "Active",
                "optimization_status": "Parallel processing active"
            }
    
    def shutdown(self):
        """Shutdown parallel service cleanly"""
        logger.info("[PARALLEL_CHAT] 🛑 Shutting down parallel chat service")
        self.executor.shutdown(wait=True)