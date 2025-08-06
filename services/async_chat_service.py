import asyncio
import aiohttp
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Tuple
from services.chat_service import ChatService

logger = logging.getLogger(__name__)

class AsyncChatService:
    """
    Async wrapper for ChatService to enable parallel processing
    and significantly faster first-time response times.
    """
    
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        self.executor = ThreadPoolExecutor(max_workers=4)
        
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
            "What features are included?",
            "How to integrate?",
            "Is there support?",
            "Demo available?"
        ]
        
        logger.info("[ASYNC_CHAT] 🚀 Initialized async chat service for faster responses")
    
    async def handle_question_async(self, question: str, session: Dict) -> Tuple[str, Dict]:
        """
        Async version of handle_question with parallel processing
        """
        start_time = time.time()
        logger.info(f"[ASYNC_CHAT] ⚡ Starting async processing for: '{question[:30]}...'")
        
        try:
            # Check cache first - this is always fast
            cache_key = self._generate_cache_key(question, session)
            cached_response = await self._check_cache_async(cache_key)
            
            if cached_response:
                logger.info(f"[ASYNC_CHAT] 🎯 Cache hit! Response time: {time.time() - start_time:.3f}s")
                session["history"].append({"role": "assistant", "content": cached_response})
                return cached_response, session
            
            # For first-time responses, use parallel processing
            logger.info("[ASYNC_CHAT] 🔄 Cache miss - starting parallel processing")
            
            # Run context retrieval and other operations in parallel
            tasks = [
                self._get_context_async(question),
                self._prepare_session_async(session),
                self._detect_language_async(question)
            ]
            
            context, prepared_session, language = await asyncio.gather(*tasks)
            
            # Now generate response with enhanced context
            response = await self._generate_response_async(question, prepared_session, context, language)
            
            # Cache the result for future use
            await self._cache_response_async(cache_key, response)
            
            # Add to session history
            prepared_session["history"].append({"role": "assistant", "content": response})
            
            total_time = time.time() - start_time
            logger.info(f"[ASYNC_CHAT] ✅ Async response generated in {total_time:.3f}s")
            
            return response, prepared_session
            
        except Exception as e:
            logger.error(f"[ASYNC_CHAT] ❌ Error in async processing: {e}")
            # Fallback to synchronous processing
            logger.info("[ASYNC_CHAT] 🔄 Falling back to synchronous processing")
            return self.chat_service.handle_question(question, session)
    
    async def _check_cache_async(self, cache_key: str) -> Optional[str]:
        """Check cache asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.chat_service.cache_manager.get(cache_key)
        )
    
    async def _cache_response_async(self, cache_key: str, response: str):
        """Cache response asynchronously"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self.chat_service.cache_manager.set(cache_key, response, ttl=1800)
        )
    
    async def _get_context_async(self, question: str) -> str:
        """Get context from ChromaDB asynchronously"""
        loop = asyncio.get_event_loop()
        
        def get_context():
            return self.chat_service._get_context_from_chroma(question, {})
        
        return await loop.run_in_executor(self.executor, get_context)
    
    async def _prepare_session_async(self, session: Dict) -> Dict:
        """Prepare session data asynchronously"""
        # This is usually fast, but we can optimize if needed
        return session.copy()
    
    async def _detect_language_async(self, question: str) -> str:
        """Detect language asynchronously"""
        loop = asyncio.get_event_loop()
        from utils.text_utils import detect_language
        return await loop.run_in_executor(
            self.executor,
            lambda: detect_language(question)
        )
    
    async def _generate_response_async(self, question: str, session: Dict, context: str, language: str) -> str:
        """Generate response using OpenAI asynchronously"""
        loop = asyncio.get_event_loop()
        
        def generate_response():
            # Use the existing chat service but with optimized context
            if context and len(context) > 50:
                return self.chat_service._generate_ai_response_with_enhanced_context(question, session, context)
            else:
                return self.chat_service._generate_ai_response(question, session)
        
        return await loop.run_in_executor(self.executor, generate_response)
    
    def _generate_cache_key(self, question: str, session: Dict) -> str:
        """Generate cache key for question and session"""
        import hashlib
        # Create more specific cache key to improve variation
        history_context = str(session.get("history", [])[-2:])  # Last 2 exchanges
        session_context = f"{session.get('greeted', False)}_{session.get('lead_collected', False)}"
        
        combined = f"{question}_{history_context}_{session_context}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    async def pre_warm_cache(self):
        """Pre-warm cache with common questions for instant responses"""
        logger.info("[ASYNC_CHAT] 🔥 Starting cache pre-warming with common questions")
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
        
        pre_warm_tasks = []
        for question in self.common_questions:
            task = self._pre_warm_single_question(question, clean_session.copy())
            pre_warm_tasks.append(task)
        
        # Process in batches to avoid overwhelming the system
        batch_size = 3
        for i in range(0, len(pre_warm_tasks), batch_size):
            batch = pre_warm_tasks[i:i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        pre_warm_time = time.time() - start_time
        logger.info(f"[ASYNC_CHAT] ✅ Cache pre-warming completed in {pre_warm_time:.2f}s")
        
        # Log cache statistics
        cache_stats = self.chat_service.cache_manager.get_stats()
        logger.info(f"[ASYNC_CHAT] 📊 Cache now has {cache_stats['total_entries']} entries")
    
    async def _pre_warm_single_question(self, question: str, session: Dict):
        """Pre-warm cache for a single question"""
        try:
            logger.debug(f"[ASYNC_CHAT] 🔥 Pre-warming: '{question}'")
            await self.handle_question_async(question, session)
        except Exception as e:
            logger.warning(f"[ASYNC_CHAT] ⚠️ Failed to pre-warm '{question}': {e}")
    
    async def batch_process_questions(self, questions_and_sessions: List[Tuple[str, Dict]]) -> List[Tuple[str, Dict]]:
        """Process multiple questions in parallel"""
        logger.info(f"[ASYNC_CHAT] 🚀 Batch processing {len(questions_and_sessions)} questions")
        
        tasks = [
            self.handle_question_async(question, session)
            for question, session in questions_and_sessions
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [result for result in results if not isinstance(result, Exception)]
        
        logger.info(f"[ASYNC_CHAT] ✅ Batch processing complete: {len(valid_results)}/{len(questions_and_sessions)} successful")
        return valid_results
    
    def get_async_stats(self) -> Dict[str, Any]:
        """Get async processing statistics"""
        cache_stats = self.chat_service.cache_manager.get_stats()
        
        return {
            "async_processing": "Enabled",
            "parallel_workers": self.executor._max_workers,
            "pre_warm_questions": len(self.common_questions),
            "cache_entries": cache_stats["total_entries"],
            "cache_hit_rate": f"{cache_stats.get('hit_rate_percent', 0):.1f}%",
            "optimization_status": "Async + Parallel processing active"
        }
    
    async def shutdown(self):
        """Shutdown async service cleanly"""
        logger.info("[ASYNC_CHAT] 🛑 Shutting down async chat service")
        self.executor.shutdown(wait=True)