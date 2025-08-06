import logging
import re
from typing import Dict, List, Optional, Set
from utils.text_utils import detect_language

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Advanced context management system to maintain user context throughout conversations
    """
    
    def __init__(self):
        # User context tracking
        self.user_profiles = {}  # session_id -> user_profile
        self.conversation_contexts = {}  # session_id -> conversation_context
        
        # Business type detection patterns
        self.business_patterns = {
            "restaurant": [
                "מסעדה", "בר", "קפה", "אוכל", "תפריט", "הזמנות", "מקומות", "שולחנות",
                "restaurant", "cafe", "bar", "food", "menu", "reservations", "tables", "booking"
            ],
            "makeup_artist": [
                "מאפרת", "מאפר", "איפור", "קוסמטיקה", "יופי", "טיפוח", "סלון יופי",
                "makeup artist", "makeup", "cosmetics", "beauty", "stylist", "beauty salon"
            ],
            "retail": [
                "חנות", "קמעונאות", "מוצרים", "מלאי", "מבצעים", "קניות", "לקוחות",
                "store", "retail", "shop", "products", "inventory", "sales", "customers"
            ],
            "medical": [
                "קליניקה", "רופא", "מרפאה", "תורים", "חולים", "ביטוח", "טיפול",
                "clinic", "doctor", "medical", "appointments", "patients", "insurance"
            ],
            "real_estate": [
                "נדל\"ן", "דירות", "בתים", "השכרה", "מכירה", "נכסים", "סיורים",
                "real estate", "apartments", "houses", "rental", "property", "tours"
            ],
            "education": [
                "מורה", "מלמד", "בית ספר", "תלמידים", "לימודים", "חומר לימודי",
                "teacher", "teaching", "school", "students", "education", "learning"
            ]
        }
        
        # Context correction patterns
        self.correction_patterns = [
            "לא", "לא נכון", "לא קשור", "לא זה", "אני לא", "זה לא",
            "no", "not", "not related", "that's not", "i'm not", "it's not"
        ]
    
    def get_session_id(self, session):
        """Generate consistent session ID"""
        import hashlib
        history_str = str(session.get("history", []))
        return hashlib.md5(history_str.encode()).hexdigest()[:8]
    
    def detect_business_type(self, text: str) -> Optional[str]:
        """
        Detect business type from user text
        """
        text_lower = text.strip().lower()
        
        for business_type, patterns in self.business_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                logger.info(f"[CONTEXT] Detected business type: {business_type} in: '{text}'")
                return business_type
        
        return None
    
    def detect_correction(self, text: str) -> bool:
        """
        Detect if user is correcting previous information
        """
        text_lower = text.strip().lower()
        return any(pattern in text_lower for pattern in self.correction_patterns)
    
    def update_user_context(self, session, question: str, bot_response: str = None):
        """
        Update user context based on the current interaction
        """
        session_id = self.get_session_id(session)
        
        # Initialize user profile if not exists
        if session_id not in self.user_profiles:
            self.user_profiles[session_id] = {
                "business_type": None,
                "corrections": [],
                "preferences": set(),
                "mentioned_topics": set(),
                "last_update": None
            }
        
        user_profile = self.user_profiles[session_id]
        
        # Detect business type
        detected_business = self.detect_business_type(question)
        if detected_business:
            # Check if this is a correction
            if self.detect_correction(question):
                # User is correcting previous assumption
                user_profile["corrections"].append({
                    "previous_assumption": user_profile.get("business_type"),
                    "correction": detected_business,
                    "text": question
                })
                logger.info(f"[CONTEXT] User corrected business type: {user_profile.get('business_type')} -> {detected_business}")
            
            user_profile["business_type"] = detected_business
            user_profile["last_update"] = "business_type"
        
        # Track mentioned topics
        user_profile["mentioned_topics"].add(question[:50])  # First 50 chars as topic
        
        # Update session with context
        session["user_business_type"] = user_profile["business_type"]
        session["user_corrections"] = user_profile["corrections"]
        session["context_updated"] = True
        
        logger.debug(f"[CONTEXT] Updated context for session {session_id}: {user_profile}")
    
    def build_context_for_response(self, session, question: str) -> str:
        """
        Build comprehensive context for the bot response
        """
        session_id = self.get_session_id(session)
        user_profile = self.user_profiles.get(session_id, {})
        
        context_parts = []
        
        # User's business type
        if user_profile.get("business_type"):
            context_parts.append(f"USER_BUSINESS_TYPE: {user_profile['business_type']}")
        
        # Recent corrections
        if user_profile.get("corrections"):
            latest_correction = user_profile["corrections"][-1]
            context_parts.append(f"RECENT_CORRECTION: User corrected from '{latest_correction['previous_assumption']}' to '{latest_correction['correction']}'")
            context_parts.append(f"CORRECTION_TEXT: '{latest_correction['text']}'")
        
        # Current question context
        detected_business = self.detect_business_type(question)
        if detected_business:
            context_parts.append(f"CURRENT_QUESTION_BUSINESS_TYPE: {detected_business}")
        
        # Conversation history context
        history = session.get("history", [])
        if len(history) > 0:
            # Get last few messages for context
            recent_messages = history[-3:]  # Last 3 messages
            context_parts.append("RECENT_CONVERSATION:")
            for msg in recent_messages:
                if msg.get("role") == "user":
                    context_parts.append(f"  User: {msg.get('content', '')[:100]}...")
                elif msg.get("role") == "assistant":
                    context_parts.append(f"  Bot: {msg.get('content', '')[:100]}...")
        
        # Build final context
        context = "\n".join(context_parts)
        
        logger.debug(f"[CONTEXT] Built context for session {session_id}: {context[:200]}...")
        return context
    
    def get_context_aware_prompt(self, session, question: str, base_prompt: str) -> str:
        """
        Create context-aware prompt that prevents incorrect assumptions
        """
        context = self.build_context_for_response(session, question)
        
        # Enhanced prompt with context awareness
        enhanced_prompt = f"""{base_prompt}

IMPORTANT CONTEXT INFORMATION:
{context}

CRITICAL INSTRUCTIONS:
1. ALWAYS respect the user's stated business type and preferences
2. If user has corrected previous assumptions, acknowledge and adapt
3. Do NOT make assumptions about the user's business type unless explicitly stated
4. If user mentions being a makeup artist, do NOT ask about restaurants
5. If user mentions being a restaurant owner, do NOT ask about makeup services
6. Always be contextually appropriate to the user's actual business

Current question: {question}

Provide a helpful response that respects the user's context and avoids incorrect assumptions."""

        return enhanced_prompt
    
    def validate_response_context(self, response: str, session) -> bool:
        """
        Validate that the response doesn't contradict user context
        """
        session_id = self.get_session_id(session)
        user_profile = self.user_profiles.get(session_id, {})
        
        if not user_profile.get("business_type"):
            return True  # No context to validate against
        
        business_type = user_profile["business_type"]
        response_lower = response.lower()
        
        # Check for context violations
        violations = []
        
        if business_type == "makeup_artist":
            # Check for restaurant-related questions
            restaurant_indicators = ["מסעדה", "restaurant", "אוכל", "food", "תפריט", "menu"]
            for indicator in restaurant_indicators:
                if indicator in response_lower:
                    violations.append(f"Asked about restaurants to makeup artist")
        
        elif business_type == "restaurant":
            # Check for makeup-related questions
            makeup_indicators = ["איפור", "makeup", "קוסמטיקה", "cosmetics", "יופי", "beauty"]
            for indicator in makeup_indicators:
                if indicator in response_lower:
                    violations.append(f"Asked about makeup to restaurant owner")
        
        if violations:
            logger.warning(f"[CONTEXT_VALIDATION] Context violations detected: {violations}")
            return False
        
        return True
    
    def get_context_summary(self, session) -> Dict:
        """
        Get summary of current context for debugging
        """
        session_id = self.get_session_id(session)
        user_profile = self.user_profiles.get(session_id, {})
        
        return {
            "business_type": user_profile.get("business_type"),
            "corrections_count": len(user_profile.get("corrections", [])),
            "mentioned_topics": list(user_profile.get("mentioned_topics", [])),
            "last_update": user_profile.get("last_update")
        }

# Global context manager instance
context_manager = ContextManager() 