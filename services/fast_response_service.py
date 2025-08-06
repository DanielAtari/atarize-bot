import logging
from typing import Optional, Dict, Any
from utils.text_utils import detect_language

logger = logging.getLogger(__name__)

class FastResponseService:
    """
    Ultra-fast response service for common questions
    Bypasses GPT for deterministic answers to improve speed
    """
    
    def __init__(self):
        # Common question patterns and their fast responses
        self.fast_responses = {
            # Pricing questions
            "pricing": {
                "patterns": [
                    "מה המחיר", "כמה עולה", "מה העלות", "מחיר", "price", "cost", "כמה זה"
                ],
                "response": """עלות ההקמה: 600 ש"ח כולל מע"מ (תשלום חד-פעמי).
חבילות חודשיות:
• Basic: 49 ש"ח (עד 100 הודעות)
• Pro: 149 ש"ח (עד 500 הודעות) 
• Business+: 399 ש"ח (עד 2000 הודעות)

איזה סוג עסק יש לך? אוכל לתת דוגמה ספציפית לתחום שלך."""
            },
            
            # How it works
            "how_it_works": {
                "patterns": [
                    "איך זה עובד", "איך זה פועל", "מה התהליך", "how does it work", "how it works"
                ],
                "response": """התהליך פשוט:
1. בוחרים שירותים ומידע שהבוט צריך לדעת
2. מעלים תוכן רלוונטי (טקסט, שאלות נפוצות)
3. הקמה תוך 2-5 ימי עבודה
4. מקבלים קישור לצ'אטבוט אישי

רוצה שאסביר איך זה עובד לעסק כמו שלך?"""
            },
            
            # Features
            "features": {
                "patterns": [
                    "מה התכונות", "אילו פיצ'רים", "מה הפונקציות", "features", "capabilities"
                ],
                "response": """הצ'אטבוט שלנו כולל:
• מענה 24/7 לשאלות נפוצות
• איסוף לידים חמים
• הטמעה באתר, וואטסאפ או דף נחיתה
• התאמה אישית לטון העסק
• מסירת לידים דרך Webhook או CSV

מה הכי מעניין אותך - המחיר או האפשרויות?"""
            },
            
            # Support
            "support": {
                "patterns": [
                    "יש תמיכה", "איך מקבלים עזרה", "תמיכה טכנית", "support", "help"
                ],
                "response": """כן, יש תמיכה מלאה!
• תמיכה טכנית בזמן ההקמה
• עדכונים קטנים כלולים
• שינויים מהותיים בתיאום ותוספת
• תמיכה מתמשכת לכל החבילות

איך את מתנהלת כרגע עם לקוחות? אוכל להראות איך הבוט יעזור לך."""
            },
            
            # Implementation time
            "implementation": {
                "patterns": [
                    "כמה זמן לוקח", "תהליך היישום", "משך ההטמעה", "implementation time", "how long"
                ],
                "response": """הקמת הבוט נמשכת 2-5 ימי עבודה:
• יום 1-2: קבלת המידע והתכנים
• יום 3-4: הקמת הבוט והתאמה
• יום 5: בדיקות והפעלה

הזמן תלוי במורכבות ובמהירות קבלת המידע.

רוצה להתחיל? אוכל לשלוח לך טופס פשוט."""
            }
        }
    
    def get_fast_response(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Check if question matches fast response patterns
        Returns response dict if match found, None otherwise
        """
        question_lower = question.strip().lower()
        
        for category, data in self.fast_responses.items():
            patterns = data["patterns"]
            if any(pattern in question_lower for pattern in patterns):
                logger.info(f"[FAST_RESPONSE] Match found for category: {category}")
                return {
                    "answer": data["response"],
                    "category": category,
                    "fast_path": True,
                    "response_time": 0.1  # Simulated fast response time
                }
        
        return None
    
    def is_common_question(self, question: str) -> bool:
        """
        Check if question is a common one that could use fast path
        """
        return self.get_fast_response(question) is not None
    
    def get_fast_response_stats(self) -> Dict[str, Any]:
        """
        Get statistics about fast response categories
        """
        return {
            "categories": list(self.fast_responses.keys()),
            "total_patterns": sum(len(data["patterns"]) for data in self.fast_responses.values()),
            "coverage": [
                "pricing", "how_it_works", "features", "support", "implementation"
            ]
        }

# Global fast response service instance
fast_response_service = FastResponseService() 