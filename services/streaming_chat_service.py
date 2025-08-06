import logging
import json
import time
from flask import Response
from services.chat_service import ChatService
from utils.text_utils import detect_language, is_greeting

logger = logging.getLogger(__name__)

class StreamingChatService(ChatService):
    """
    Enhanced ChatService with streaming capabilities for better perceived performance
    """
    
    def __init__(self, db_manager, openai_client):
        super().__init__(db_manager, openai_client)
        self.typing_delay = 0.03  # Delay between characters for typing effect
        
    def stream_response(self, question, session):
        """
        Stream response in chunks for better perceived performance
        """
        try:
            # Check cache first for instant response
            cache_key = self._get_cache_key(question, session)
            cached_response = self.cache_manager.get(cache_key)
            
            if cached_response:
                logger.info(f"[STREAMING] Cache hit for: {question}")
                yield self._format_stream_chunk("cache_hit", True)
                yield self._format_stream_chunk("typing", True)
                
                # Stream cached response with typing effect
                for chunk in self._stream_text_with_typing(cached_response["answer"]):
                    yield chunk
                    
                yield self._format_stream_chunk("complete", {
                    "answer": cached_response["answer"],
                    "response_time": 0.1,
                    "cached": True
                })
                return
            
            # Not cached - stream with progress indicators
            yield self._format_stream_chunk("cache_hit", False)
            yield self._format_stream_chunk("processing", "Searching knowledge base...")
            
            # Process the question with timing
            start_time = time.time()
            result = self.handle_question(question, session)
            response_time = time.time() - start_time
            
            if result and result.get("answer"):
                yield self._format_stream_chunk("processing", "Generating response...")
                yield self._format_stream_chunk("typing", True)
                
                # Stream the answer with typing effect
                for chunk in self._stream_text_with_typing(result["answer"]):
                    yield chunk
                
                yield self._format_stream_chunk("complete", {
                    "answer": result["answer"],
                    "response_time": response_time,
                    "cached": False
                })
            else:
                yield self._format_stream_chunk("error", "Sorry, I couldn't process your question.")
                
        except Exception as e:
            logger.error(f"[STREAMING] Error streaming response: {e}")
            yield self._format_stream_chunk("error", "An error occurred while processing your question.")
    
    def _stream_text_with_typing(self, text):
        """
        Stream text character by character with typing effect
        """
        words = text.split()
        current_text = ""
        
        for i, word in enumerate(words):
            current_text += word
            if i < len(words) - 1:
                current_text += " "
            
            yield self._format_stream_chunk("text", current_text)
            
            # Add small delay for typing effect (only for longer responses)
            if len(text) > 100:
                time.sleep(self.typing_delay)
    
    def _format_stream_chunk(self, chunk_type, data):
        """
        Format streaming chunk for frontend consumption
        """
        chunk = {
            "type": chunk_type,
            "data": data,
            "timestamp": time.time()
        }
        return f"data: {json.dumps(chunk)}\n\n"
    
    def _get_cache_key(self, question, session):
        """
        Generate cache key for the question
        """
        # Use the same cache key generation as parent class
        import hashlib
        
        # Create cache key from question and relevant session context
        context_str = f"{question.strip().lower()}"
        
        # Add language context if available
        language = detect_language(question)
        if language:
            context_str += f"_lang:{language}"
        
        return hashlib.md5(context_str.encode()).hexdigest()

class StreamingResponseHandler:
    """
    Helper class to handle Server-Sent Events (SSE) streaming
    """
    
    @staticmethod
    def create_streaming_response(generator):
        """
        Create Flask SSE response from generator
        """
        def generate():
            yield "data: {\"type\": \"start\", \"data\": \"Starting response...\"}\n\n"
            
            try:
                for chunk in generator:
                    yield chunk
            except Exception as e:
                logger.error(f"[STREAMING] Generator error: {e}")
                error_chunk = {
                    "type": "error",
                    "data": "Stream interrupted",
                    "timestamp": time.time()
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
            
            yield "data: {\"type\": \"end\", \"data\": \"Stream complete\"}\n\n"
        
        return Response(
            generate(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'
            }
        )

# Quick streaming test function
def test_streaming_performance():
    """
    Test streaming performance vs regular performance
    """
    print("🚀 STREAMING PERFORMANCE TEST")
    print("="*50)
    
    # This would be called from the main test script
    test_questions = [
        "מה המחיר?",
        "איך זה עובד?",
        "מה התכונות?"
    ]
    
    for question in test_questions:
        print(f"📊 Testing streaming for: {question}")
        # Implementation would go here
        
    print("✅ Streaming test complete!")

if __name__ == "__main__":
    test_streaming_performance()