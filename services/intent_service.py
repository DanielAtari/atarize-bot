import logging
from rapidfuzz import fuzz
from utils.validation_utils import detect_business_type, detect_specific_use_case, detect_positive_engagement

logger = logging.getLogger(__name__)

class IntentService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.fuzzy_threshold = 70
    
    def detect_intent(self, user_input, intents, threshold=70):
        """Detect intent using fuzzy matching"""
        best_match = None
        best_score = 0
        
        for intent in intents:
            score = fuzz.ratio(user_input.lower(), intent['text'].lower())
            if score > best_score and score >= threshold:
                best_score = score
                best_match = intent
        
        return best_match
    
    def detect_intent_fuzzy(self, user_input, intents):
        """Fuzzy intent detection"""
        return self.detect_intent(user_input, intents, self.fuzzy_threshold)
    
    def detect_intent_chroma(self, user_question, threshold=1.2):
        """Detect intent using ChromaDB semantic search"""
        try:
            intents_collection = self.db_manager.get_intents_collection()
            if not intents_collection:
                logger.warning("No intents collection available")
                return None
            
            results = intents_collection.query(
                query_texts=[user_question],
                n_results=1
            )
            
            if results and results['distances'] and results['distances'][0]:
                distance = results['distances'][0][0]
                if distance <= threshold:
                    intent_name = results['metadatas'][0][0].get('intent_name', 'unknown')
                    logger.info(f"[CHROMA_INTENT] Detected intent: {intent_name} (distance: {distance})")
                    return intent_name
            
            logger.debug(f"[CHROMA_INTENT] No intent detected (best distance: {results['distances'][0][0] if results and results['distances'] else 'N/A'})")
            return None
            
        except Exception as e:
            logger.error(f"Error in ChromaDB intent detection: {e}")
            return None
    
    def get_use_case_specific_response(self, use_case, user_question, language="he"):
        """Generate use case specific responses"""
        responses = {
            "recruitment": {
                "he": f"אני מבין שאתה מתמודד עם אתגרי גיוס! 🎯 Atarize יכולה לעזור לך לסנן מועמדים אוטומטית ולחסוך שעות של עבודה ידנית. הצ'אטבוט שלנו יכול לענות על שאלות נפוצות של מועמדים ולאסוף מידע רלוונטי. {user_question}",
                "en": f"I understand you're dealing with recruitment challenges! 🎯 Atarize can help you automatically screen candidates and save hours of manual work. Our chatbot can answer common candidate questions and collect relevant information. {user_question}"
            },
            "restaurant": {
                "he": f"מסעדות וברים הם עסקים דינמיים! 🍽️ Atarize יכולה לעזור לך לנהל הזמנות, לענות על שאלות על התפריט, ולשפר את חוויית הלקוח. {user_question}",
                "en": f"Restaurants and bars are dynamic businesses! 🍽️ Atarize can help you manage reservations, answer menu questions, and improve customer experience. {user_question}"
            },
            "retail": {
                "he": f"חנויות וקמעונאות דורשות שירות לקוחות מעולה! 🛍️ Atarize יכולה לעזור לך לענות על שאלות על מוצרים, מבצעים, ומלאי. {user_question}",
                "en": f"Stores and retail require excellent customer service! 🛍️ Atarize can help you answer questions about products, promotions, and inventory. {user_question}"
            },
            "real_estate": {
                "he": f"נדל\"ן דורש זמינות גבוהה ומידע מדויק! 🏠 Atarize יכולה לעזור לך לענות על שאלות על נכסים, תיאום סיורים, ומידע על שכונה. {user_question}",
                "en": f"Real estate requires high availability and accurate information! 🏠 Atarize can help you answer questions about properties, schedule tours, and provide neighborhood information. {user_question}"
            },
            "medical": {
                "he": f"קליניקות ומרפאות דורשות זמינות 24/7! 🏥 Atarize יכולה לעזור לך לנהל תורים, לענות על שאלות רפואיות כלליות, ולשפר את השירות. {user_question}",
                "en": f"Clinics and medical practices require 24/7 availability! 🏥 Atarize can help you manage appointments, answer general medical questions, and improve service. {user_question}"
            }
        }
        
        return responses.get(use_case, {}).get(language, "")
    
    def get_business_specific_response(self, business_input, language="he"):
        """Generate business type specific responses"""
        responses = {
            "he": f"מעולה! אני רואה שיש לך עסק {business_input}. 🎯 Atarize מתמחה בבניית צ'אטבוטים לעסקים כמו שלך. הצ'אטבוט שלנו יכול לעזור לך לשפר את השירות ללקוחות ולחסוך זמן יקר. מה מעניין אותך לדעת?",
            "en": f"Great! I can see you have a {business_input} business. 🎯 Atarize specializes in building chatbots for businesses like yours. Our chatbot can help you improve customer service and save valuable time. What would you like to know?"
        }
        
        return responses.get(language, "")
    
    def get_follow_up_content_by_topic(self, topic, business_type=None, language="he"):
        """Generate follow-up content based on topic and business type"""
        follow_ups = {
            "pricing": {
                "he": "אני אשמח לספר לך על המחירים שלנו. יש לנו חבילות שונות שמתאימות לעסקים שונים. האם תרצה שאני אשלח לך פרטים?",
                "en": "I'd be happy to tell you about our pricing. We have different packages that suit different businesses. Would you like me to send you details?"
            },
            "process": {
                "he": "התהליך שלנו פשוט ויעיל. אנחנו מתחילים בהבנת הצרכים שלך, בונים את הצ'אטבוט, ומשלבים אותו באתר שלך. האם תרצה לשמוע יותר?",
                "en": "Our process is simple and efficient. We start by understanding your needs, build the chatbot, and integrate it into your website. Would you like to hear more?"
            },
            "features": {
                "he": "הצ'אטבוט שלנו כולל יכולות מתקדמות כמו זיהוי שפה, איסוף לידים, ואינטגרציה עם מערכות קיימות. מה מעניין אותך במיוחד?",
                "en": "Our chatbot includes advanced capabilities like language detection, lead collection, and integration with existing systems. What interests you most?"
            }
        }
        
        return follow_ups.get(topic, {}).get(language, "")
    
    def detect_follow_up_context(self, question, session):
        """Detect if this is a follow-up question"""
        follow_up_indicators = [
            "ומה לגבי", "ומה עם", "אבל", "אוקיי", "בסדר", "אני רוצה",
            "what about", "but", "okay", "alright", "i want"
        ]
        
        question_lower = question.lower()
        is_follow_up = any(indicator in question_lower for indicator in follow_up_indicators)
        
        # Also check if there's conversation history
        has_history = len(session.get("history", [])) > 2
        
        return is_follow_up or has_history