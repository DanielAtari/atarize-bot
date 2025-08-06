import os
import logging
from openai import OpenAI
from utils.token_utils import count_tokens, log_token_usage

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.client = self.get_client()
        self.model = "gpt-4-turbo"
        self.max_tokens = 1000
        # Add chat attribute for compatibility
        self.chat = self.client.chat
    
    def get_client(self):
        """Get OpenAI client"""
        try:
            return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    def call_gpt_with_context(self, prompt, session, client, model="gpt-4-turbo"):
        """Call GPT with context and error handling"""
        try:
            # Build messages
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": session.get("current_question", "")}
            ]
            
            # Add conversation history
            history = session.get("history", [])
            for msg in history[-6:]:  # Last 6 messages
                if msg.get("role") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Log token usage
            token_count = count_tokens(messages, model)
            log_token_usage(messages, model)
            
            if token_count > 8000:  # Safety limit
                logger.warning(f"Token count too high: {token_count}, truncating history")
                messages = messages[:2] + history[-2:]  # Keep only last 2 history messages
            
            # Call OpenAI
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info(f"[GPT] Generated response: {len(answer)} chars")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error calling GPT: {e}")
            return None
    
    def create_completion(self, messages, model=None, max_tokens=None, temperature=0.7):
        """Create a completion using the OpenAI client"""
        try:
            model = model or self.model
            max_tokens = max_tokens or self.max_tokens
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating completion: {e}")
            return None
    
    def handle_intent_failure(self, question, session, collection, system_prompt, client):
        """Handle cases where intent detection fails"""
        try:
            # Try to get some context from ChromaDB
            context = ""
            if collection:
                results = collection.query(
                    query_texts=[question],
                    n_results=2
                )
                if results and results['documents']:
                    context = "\n".join(results['documents'][0])
            
            # Build fallback prompt
            fallback_prompt = f"""
{system_prompt}

Context (if available):
{context}

User Question: {question}

Instructions:
- Provide a helpful response even without specific intent
- Suggest connecting with the team for detailed information
- Keep the response conversational and engaging
- If you don't know something, be honest and offer to connect them with the team
"""
            
            # Call GPT with fallback prompt
            response = self.call_gpt_with_context(fallback_prompt, session, client)
            
            if response:
                logger.info(f"[INTENT_FAILURE] Generated fallback response")
                return response
            else:
                # Final fallback
                lang = "he" if any(ord(c) > 127 for c in question) else "en"
                if lang == "he":
                    return "אני רוצה לעזור לך, אבל אני צריך יותר מידע. האם תוכל לפרט יותר על מה שאתה מחפש? או שאני אחבר אותך עם מישהו מהצוות?"
                else:
                    return "I want to help you, but I need more information. Can you provide more details about what you're looking for? Or should I connect you with someone from the team?"
                    
        except Exception as e:
            logger.error(f"Error in intent failure handling: {e}")
            return "I'm having trouble processing your request. Please try again or contact our team for assistance."
    
    def is_truly_vague(self, answer):
        """Enhanced vagueness detection"""
        if not answer or len(answer.strip()) < 15:
            return True
        
        vague_phrases = [
            "i don't know", "לא יודע", "לא ברור", "not sure",
            "תלוי", "depends", "אולי", "maybe"
        ]
        
        answer_lower = answer.lower()
        vague_count = sum(1 for phrase in vague_phrases if phrase in answer_lower)
        
        return vague_count >= 2