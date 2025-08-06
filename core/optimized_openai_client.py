import os
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from utils.token_utils import count_tokens, log_token_usage

logger = logging.getLogger(__name__)

class OptimizedOpenAIClient:
    """
    Optimized OpenAI client with performance improvements:
    - Faster model selection
    - Optimized token usage
    - Concurrent processing capabilities
    - Smart context management
    """
    
    def __init__(self):
        self.client = self.get_client()
        
        # Performance optimizations
        self.fast_model = "gpt-3.5-turbo"  # Faster for simple queries
        self.smart_model = "gpt-4-turbo"   # For complex queries
        self.max_tokens_fast = 500         # Reduced for faster responses
        self.max_tokens_smart = 1000       # Standard for complex responses
        
        # Concurrent processing
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Performance tracking
        self.response_times = []
        
    def get_client(self):
        """Get OpenAI client"""
        try:
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    def _should_use_fast_model(self, question):
        """
        Determine if we should use fast model for simple queries
        """
        # Simple heuristics for fast model usage
        simple_indicators = [
            len(question) < 50,  # Short questions
            any(word in question.lower() for word in [
                "מחיר", "price", "כמה", "how much", "עולה", "cost",
                "מה זה", "what is", "כן", "yes", "לא", "no"
            ]),
            question.count("?") == 1 and len(question.split()) <= 10
        ]
        
        return any(simple_indicators)
    
    def call_gpt_optimized(self, prompt, session, question=None, force_smart=False):
        """
        Optimized GPT call with smart model selection and reduced latency
        """
        start_time = time.time()
        
        try:
            # Smart model selection
            if force_smart or not self._should_use_fast_model(question or ""):
                model = self.smart_model
                max_tokens = self.max_tokens_smart
                logger.debug(f"[OPTIMIZED] Using smart model for complex query")
            else:
                model = self.fast_model
                max_tokens = self.max_tokens_fast
                logger.debug(f"[OPTIMIZED] Using fast model for simple query")
            
            # Build optimized messages
            messages = self._build_optimized_messages(prompt, session, question)
            
            # Token optimization
            token_count = count_tokens(messages, model)
            if token_count > 6000:  # More aggressive limit for speed
                messages = self._truncate_messages(messages)
                logger.debug(f"[OPTIMIZED] Truncated messages for speed")
            
            # Call OpenAI with optimizations
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                # Performance optimizations
                top_p=0.9,  # Slightly reduced for faster generation
                frequency_penalty=0.1,  # Reduce repetition
                presence_penalty=0.1
            )
            
            answer = response.choices[0].message.content.strip()
            response_time = time.time() - start_time
            
            # Track performance
            self.response_times.append(response_time)
            logger.info(f"[OPTIMIZED] Response generated in {response_time:.2f}s using {model}")
            
            return answer
            
        except Exception as e:
            logger.error(f"[OPTIMIZED] Error calling GPT: {e}")
            return None
    
    def _build_optimized_messages(self, prompt, session, question):
        """
        Build optimized message structure for faster processing
        """
        messages = [
            {"role": "system", "content": self._optimize_system_prompt(prompt)}
        ]
        
        # Add user question
        if question:
            messages.append({"role": "user", "content": question})
        elif session.get("current_question"):
            messages.append({"role": "user", "content": session["current_question"]})
        
        # Add minimal conversation history for context
        history = session.get("history", [])
        if history:
            # Only add last 2-4 exchanges for speed
            recent_history = history[-4:]
            for msg in recent_history:
                if msg.get("role") and msg.get("content"):
                    # Truncate long messages
                    content = msg["content"]
                    if len(content) > 200:
                        content = content[:200] + "..."
                    messages.append({"role": msg["role"], "content": content})
        
        return messages
    
    def _optimize_system_prompt(self, prompt):
        """
        Optimize system prompt for faster processing
        """
        # Keep essential instructions, remove verbose parts
        if len(prompt) > 1000:
            # Extract key instructions
            key_phrases = [
                "אתה עוזר ללקוחות",
                "You are a helpful assistant",
                "Atarize",
                "חברת טכנולוגיה",
                "technology company"
            ]
            
            # Create condensed prompt
            condensed = "אתה עוזר ללקוחות של Atarize - חברת טכנולוגיה המתמחה בפתרונות דיגיטליים. ענה בצורה מדויקת וידידותית."
            return condensed
        
        return prompt
    
    def _truncate_messages(self, messages):
        """
        Aggressively truncate messages for speed
        """
        if len(messages) <= 2:
            return messages
        
        # Keep system prompt and current question, minimal history
        return [messages[0], messages[1]] + messages[-2:]
    
    def call_gpt_concurrent(self, prompts_and_sessions):
        """
        Process multiple GPT calls concurrently
        """
        def process_single(prompt_session):
            prompt, session, question = prompt_session
            return self.call_gpt_optimized(prompt, session, question)
        
        # Use ThreadPoolExecutor for concurrent processing
        futures = []
        for prompt_session in prompts_and_sessions:
            future = self.executor.submit(process_single, prompt_session)
            futures.append(future)
        
        # Collect results
        results = []
        for future in futures:
            try:
                result = future.result(timeout=15)  # 15s timeout per call
                results.append(result)
            except Exception as e:
                logger.error(f"[CONCURRENT] Error in concurrent processing: {e}")
                results.append(None)
        
        return results
    
    def get_performance_stats(self):
        """
        Get performance statistics
        """
        if not self.response_times:
            return {
                "average_response_time": 0,
                "total_calls": 0,
                "fastest_call": 0,
                "slowest_call": 0
            }
        
        return {
            "average_response_time": sum(self.response_times) / len(self.response_times),
            "total_calls": len(self.response_times),
            "fastest_call": min(self.response_times),
            "slowest_call": max(self.response_times),
            "recent_average": sum(self.response_times[-10:]) / min(len(self.response_times), 10)
        }
    
    def handle_intent_failure_optimized(self, question, session, collection, system_prompt):
        """
        Optimized intent failure handling
        """
        try:
            # Quick context retrieval
            context = ""
            if collection:
                results = collection.query(
                    query_texts=[question],
                    n_results=1  # Reduced for speed
                )
                if results and results['documents']:
                    context = results['documents'][0][0][:300]  # Truncated for speed
            
            # Simplified fallback prompt
            fallback_prompt = f"""אתה עוזר ללקוחות של Atarize.
            
{context[:200] if context else ""}

שאלת המשתמש: {question}

ענה בקיצור ובאופן מועיל."""
            
            # Use fast model for fallback
            return self.call_gpt_optimized(
                fallback_prompt, 
                session, 
                question, 
                force_smart=False  # Use fast model
            )
            
        except Exception as e:
            logger.error(f"[OPTIMIZED_FALLBACK] Error: {e}")
            # Quick response
            lang = "he" if any(ord(c) > 127 for c in question) else "en"
            if lang == "he":
                return "אני כאן לעזור! אפשר לפרט את השאלה?"
            else:
                return "I'm here to help! Can you provide more details?"

# Backward compatibility wrapper
class OpenAIClient(OptimizedOpenAIClient):
    """
    Backward compatible wrapper that maintains the original interface
    while using optimized implementation
    """
    
    def __init__(self):
        super().__init__()
        self.model = self.smart_model  # Default for compatibility
        self.max_tokens = self.max_tokens_smart
    
    def call_gpt_with_context(self, prompt, session, client=None, model=None):
        """
        Backward compatible method that uses optimized implementation
        """
        # Use optimized call
        return self.call_gpt_optimized(prompt, session)
    
    def handle_intent_failure(self, question, session, collection, system_prompt, client=None):
        """
        Backward compatible intent failure handling
        """
        return self.handle_intent_failure_optimized(question, session, collection, system_prompt)

if __name__ == "__main__":
    # Performance test
    client = OptimizedOpenAIClient()
    print("🚀 Optimized OpenAI Client initialized!")
    print(f"Fast model: {client.fast_model}")
    print(f"Smart model: {client.smart_model}")