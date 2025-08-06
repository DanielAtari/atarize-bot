import random
import logging
from typing import Dict, List, Any, Optional
from utils.text_utils import detect_language

logger = logging.getLogger(__name__)

class ResponseVariationService:
    """
    Service to eliminate repetitive phrases and create natural conversation flow.
    Tracks conversation state and provides varied response endings.
    """
    
    def __init__(self):
        self.conversation_state = {}  # Track what we've said to each session
        
        # Hebrew response variations
        self.hebrew_variations = {
            "general_help": [
                "יש עוד משהו שאפשר לעזור לך בו?",
                "רוצה לשמוע עוד פרטים?",
                "יש לך שאלות נוספות?",
                "אפשר לעזור לך עם משהו נוסף?",
                "מעוניין בפרטים נוספים?",
                "רוצה שאסביר עוד משהו?",
                "יש מידע נוסף שיעזור לך?"
            ],
            "assistance_offer": [
                "רוצה שמישהו מהצוות יחזור אליך?",
                "אפשר לקבוע שיחה עם המומחים שלנו?",
                "רוצה שנחזור אליך עם הצעה מותאמת?",
                "מעוניין בייעוץ אישי?",
                "אשמח לחבר אותך למומחה שלנו",
                "רוצה שנכין לך הצעה מפורטת?",
                "האם תרצה לקבל יועץ אישי?"
            ],
            "pricing_follow": [
                "רוצה לשמוע על החבילות השונות?",
                "מעוניין בפירוט המחירים?",
                "יש לך תקציב מסוים בראש?",
                "רוצה שנמצא לך את החבילה המתאימה?",
                "מעוניין בהשוואת החבילות?",
                "רוצה לדעת מה הכי מתאים לך?",
                "אפשר לעזור לך לבחור חבילה?"
            ],
            "technical_follow": [
                "יש לך שאלות טכניות נוספות?",
                "רוצה לדבר עם המומחה הטכני שלנו?",
                "מעוניין בפגישת הדגמה?",
                "רוצה לראות איך זה עובד בפועל?",
                "יש לך דרישות טכניות מיוחדות?",
                "רוצה שנבדוק התאימות למערכת שלך?",
                "מעוניין בבדיקת התכנות?"
            ],
            "casual_ending": [
                "😊",
                "אני כאן אם יש עוד שאלות",
                "תרגיש חופשי לשאול כל דבר",
                "אני זמינה לעזרה נוספת",
                "",  # Sometimes no ending is better
                "בהצלחה!",
                "אשמח לעזור בכל דבר נוסף"
            ],
            "lead_confirmation": [
                "תודה רבה! קיבלנו את הפרטים שלך ומישהו מהצוות יחזור אליך בהקדם.",
                "מעולה! רשמנו את המידע שלך ונחזור אליך בקרוב לתיאום הצעדים הבאים.",
                "נהדר! רשמנו את הפרטים ומישהו מהצוות יחזור אליך תוך 24 שעות.",
                "מושלם! קיבלנו את הפרטים ונחזור אליך בהקדם לתיאום.",
                "תודה על הפרטים! נחזור אליך בקרוב כדי להתקדם.",
                "יופי! יש לנו את כל המידע הדרוש ונחזור אליך מאוד בקרוב."
            ]
        }
        
        # English response variations
        self.english_variations = {
            "general_help": [
                "Is there anything else I can help you with?",
                "Would you like to hear more details?",
                "Do you have any other questions?",
                "Can I assist you with something else?",
                "Interested in more information?",
                "Would you like me to explain anything else?",
                "Any other information that would help?"
            ],
            "assistance_offer": [
                "Would you like someone from our team to follow up?",
                "Can we schedule a call with our experts?",
                "Would you like us to get back to you with a tailored proposal?",
                "Interested in personal consultation?",
                "I'd be happy to connect you with our specialist",
                "Would you like us to prepare a detailed proposal?",
                "Would you like to get a personal consultant?"
            ],
            "pricing_follow": [
                "Would you like to hear about our different packages?",
                "Interested in pricing details?",
                "Do you have a specific budget in mind?",
                "Would you like us to find the right package for you?",
                "Interested in comparing packages?",
                "Want to know what would work best for you?",
                "Can I help you choose a package?"
            ],
            "technical_follow": [
                "Do you have additional technical questions?",
                "Would you like to speak with our technical expert?",
                "Interested in a demo session?",
                "Want to see how it works in practice?",
                "Do you have any special technical requirements?",
                "Should we check compatibility with your system?",
                "Interested in a technical assessment?"
            ],
            "casual_ending": [
                "😊",
                "I'm here if you have more questions",
                "Feel free to ask anything else",
                "I'm available for additional help",
                "",  # Sometimes no ending is better
                "Good luck!",
                "Happy to help with anything else"
            ],
            "lead_confirmation": [
                "Thank you! We have received your details. Someone from our team will contact you shortly.",
                "Perfect! Got your information. We'll reach out to you soon to discuss next steps.",
                "Excellent! We've noted your details and someone will get back to you within 24 hours.",
                "Great! Your information has been received. Our team will be in touch shortly.",
                "Thank you for your details! We'll contact you soon to move forward.",
                "Wonderful! We have everything we need and will reach out to you very soon."
            ]
        }
        
        logger.info("[RESPONSE_VARIATION] Initialized with varied response patterns")
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """Get conversation state for a session"""
        if session_id not in self.conversation_state:
            self.conversation_state[session_id] = {
                "used_phrases": set(),
                "response_count": 0,
                "last_category": None,
                "conversation_topics": set()
            }
        return self.conversation_state[session_id]
    
    def mark_phrase_used(self, session_id: str, phrase: str, category: str):
        """Mark a phrase as used in this conversation"""
        state = self.get_session_state(session_id)
        state["used_phrases"].add(phrase.lower().strip())
        state["last_category"] = category
        state["response_count"] += 1
        logger.debug(f"[RESPONSE_VARIATION] Marked phrase used: {phrase[:30]}... (category: {category})")
    
    def select_varied_response(self, category: str, language: str, session_id: str, context: str = "") -> str:
        """
        Select a varied response that hasn't been used recently in this conversation.
        
        Args:
            category: Type of response (general_help, assistance_offer, etc.)
            language: Language preference (he/en)
            session_id: Session identifier for tracking
            context: Context to help choose appropriate response
            
        Returns:
            Varied response string
        """
        state = self.get_session_state(session_id)
        
        # Choose variation pool based on language
        variations = self.hebrew_variations if language == "he" else self.english_variations
        
        if category not in variations:
            logger.warning(f"[RESPONSE_VARIATION] Unknown category: {category}, using general_help")
            category = "general_help"
        
        available_responses = variations[category]
        
        # Filter out recently used phrases
        unused_responses = [
            resp for resp in available_responses 
            if resp.lower().strip() not in state["used_phrases"]
        ]
        
        # If all responses have been used, reset and use any
        if not unused_responses:
            logger.info(f"[RESPONSE_VARIATION] All {category} responses used, resetting for session {session_id}")
            state["used_phrases"].clear()
            unused_responses = available_responses
        
        # Select response based on context and avoid recent category repetition
        selected_response = self._context_aware_selection(unused_responses, context, state)
        
        # Mark as used
        self.mark_phrase_used(session_id, selected_response, category)
        
        return selected_response
    
    def _context_aware_selection(self, responses: List[str], context: str, state: Dict[str, Any]) -> str:
        """
        Select response based on context and conversation flow.
        """
        if not responses:
            return ""
        
        context_lower = context.lower()
        
        # Context-based selection logic
        if "pricing" in context_lower or "cost" in context_lower or "מחיר" in context_lower:
            pricing_words = ["תקציב", "חבילה", "מחיר", "budget", "package", "price"]
            contextual_responses = [r for r in responses if any(word in r.lower() for word in pricing_words)]
            if contextual_responses:
                return random.choice(contextual_responses)
        
        elif "technical" in context_lower or "integration" in context_lower or "טכני" in context_lower:
            tech_words = ["טכני", "הדגמה", "מערכת", "technical", "demo", "system"]
            contextual_responses = [r for r in responses if any(word in r.lower() for word in tech_words)]
            if contextual_responses:
                return random.choice(contextual_responses)
        
        # Avoid being too formal if conversation is casual
        if state["response_count"] > 3:
            casual_responses = [r for r in responses if len(r) < 50 or "😊" in r or r == ""]
            if casual_responses and random.random() < 0.3:  # 30% chance for casual
                return random.choice(casual_responses)
        
        # Default: random selection from available responses
        return random.choice(responses)
    
    def generate_natural_ending(self, base_response: str, context: str, language: str, session_id: str) -> str:
        """
        Generate a natural ending for a response to avoid repetitive patterns.
        
        Args:
            base_response: The main response content
            context: Context of the conversation
            language: Language preference
            session_id: Session identifier
            
        Returns:
            Complete response with varied ending
        """
        # Determine appropriate category based on context
        context_lower = context.lower()
        
        if "pricing" in context_lower or "cost" in context_lower or "מחיר" in context_lower:
            category = "pricing_follow"
        elif "technical" in context_lower or "integration" in context_lower or "טכני" in context_lower:
            category = "technical_follow" 
        elif "help" in context_lower or "assistance" in context_lower or "עזרה" in context_lower:
            category = "assistance_offer"
        else:
            category = "general_help"
        
        # Get varied ending
        ending = self.select_varied_response(category, language, session_id, context)
        
        # Combine base response with varied ending
        if ending:
            if language == "he":
                complete_response = f"{base_response}\n\n{ending}"
            else:
                complete_response = f"{base_response}\n\n{ending}"
        else:
            complete_response = base_response  # Sometimes no ending is better
        
        logger.info(f"[RESPONSE_VARIATION] Generated natural ending (category: {category}, lang: {language})")
        return complete_response.strip()
    
    def should_add_ending(self, base_response: str, session_id: str) -> bool:
        """
        Determine if we should add an ending to avoid over-offering.
        """
        state = self.get_session_state(session_id)
        
        # Don't add ending if response is already long
        if len(base_response) > 400:
            return False
        
        # Don't add ending too frequently
        if state["response_count"] > 0 and state["response_count"] % 3 == 0:
            return False  # Skip ending every 3rd response
        
        # Don't add ending if response already ends with a question
        if base_response.strip().endswith("?"):
            return random.random() < 0.3  # Only 30% chance
        
        return True
    
    def clean_session_state(self, session_id: str):
        """Clean up session state when conversation ends"""
        if session_id in self.conversation_state:
            del self.conversation_state[session_id]
            logger.debug(f"[RESPONSE_VARIATION] Cleaned session state: {session_id}")
    
    def get_variation_stats(self) -> Dict[str, Any]:
        """Get statistics about response variation usage"""
        total_sessions = len(self.conversation_state)
        total_responses = sum(state["response_count"] for state in self.conversation_state.values())
        
        return {
            "active_sessions": total_sessions,
            "total_varied_responses": total_responses,
            "avg_responses_per_session": total_responses / total_sessions if total_sessions > 0 else 0,
            "variation_categories": len(self.hebrew_variations),
            "status": "Active response variation"
        }