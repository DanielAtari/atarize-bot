import re
import logging

logger = logging.getLogger(__name__)

def detect_buying_intent(text):
    """Detect when user shows clear buying/purchase intent"""
    text_lower = text.lower().strip()
    
    # Direct buying/purchase intent patterns (VERY specific to avoid false positives)
    buying_patterns = [
        # Hebrew buying intent - ONLY direct commitment phrases
        "אני רוצה לקנות", "רוצה לקנות", "רוצה לרכוש", "אני רוצה לרכוש",
        "אני רוצה להזמין", "רוצה להזמין", "רוצה את השירות", "רוצה בוט",
        "אני רוצה להתחיל", "רוצה להתחיל", "איך אפשר להתחיל", "איך מתחילים",
        "אני רוצה לעשות בוט", "רוצה לעשות בוט", "אני מעוניינת לקנות", "מעוניינת לקנות",
        
        # English buying intent - ONLY direct commitment phrases  
        "i want to buy", "want to buy", "want to purchase", "i want to purchase",
        "i want to order", "want to order", "want your service", "want a bot",
        "i want to get started", "how do i get started", "how to get started",
        "i want to create a bot", "want to create a bot", "hello, i want to buy",
        "i want to buy a chatbot", "want to buy a chatbot", "want a chatbot"
    ]
    
    # Check for buying intent patterns FIRST
    has_buying_intent = any(pattern in text_lower for pattern in buying_patterns)
    
    # If buying intent is detected, return True regardless of other patterns
    # This handles cases like "אני רוצה לקנות את הבוט. כמה זה עולה?"
    if has_buying_intent:
        logger.info(f"[BUYING_INTENT] ✅ Detected buying intent in: '{text}'")
        return True
    
    # Only check exclusion patterns if NO buying intent was found
    exclude_patterns = [
        "רק רוצה מידע", "רק רוצה לדעת", "רק רוצה להבין", "רוצה לשמוע",
        "מעוניין לשמוע", "כמה זה עולה", "מה המחיר", "מה העלות",
        "just want info", "just want to know", "just want to understand", "want to hear",
        "interested to hear", "how much does it cost", "what's the price", "pricing"
    ]
    
    has_exclusion = any(pattern in text_lower for pattern in exclude_patterns)
    if has_exclusion:
        return False
    
    return False

def detect_lead_info(text):
    """Enhanced lead detection - requires ALL THREE: name, phone, email"""
    text_lower = text.lower().strip()
    
    # Email detection (more comprehensive)
    has_email = (
        "@" in text and ("." in text.split("@")[-1] if "@" in text else False) or
        any(domain in text_lower for domain in [".com", ".co.il", ".net", ".org", "gmail", "hotmail", "yahoo", "walla"]) or
        any(word in text_lower for word in ["מייל", "email", "אימייל", "דוא\"ל"])
    )
    
    # Phone detection (Israeli phone patterns)
    has_phone = (
        any(prefix in text for prefix in ["050", "052", "053", "054", "055", "056", "057", "058", "059"]) or
        any(word in text_lower for word in ["טלפון", "נייד", "phone", "פלאפון", "מספר"]) or
        bool(re.search(r'\b0\d{1,2}[-\s]?\d{7}\b', text))  # Phone number pattern
    )
    
    # Name detection (comprehensive patterns)
    has_name = (
        any(word in text_lower for word in ["שמי", "שם שלי", "קוראים לי", "אני", "name", "my name"]) or
        bool(re.search(r'\b[A-Za-z]{2,}\s+[A-Za-z]{2,}\b', text)) or  # English full name pattern (case insensitive)
        bool(re.search(r'\b[א-ת]{2,}\s+[א-ת]{2,}\b', text)) or  # Hebrew name pattern (first + last)
        bool(re.search(r'\b[א-ת]{2,}\b', text)) or  # Single Hebrew name (2+ characters)
        bool(re.search(r'\b[A-Za-z]{2,}\b', text)) or  # Single English name (2+ characters)
        any(word in text_lower for word in ["שם מלא", "שמי הוא", "השם שלי"])
    )
    
    logger.debug(f"[LEAD_DETECTION] Text: '{text}' | Email: {has_email} | Phone: {has_phone} | Name: {has_name}")
    
    # Require ALL THREE components for complete lead info
    return has_email and has_phone and has_name

def detect_business_type(text):
    """Detect when user provides business type information"""
    text_lower = text.strip().lower()
    
    # Business type patterns in Hebrew
    business_patterns_he = [
        "יש לי חנות", "יש לי מסעדה", "יש לי קליניקה", "יש לי משרד", "יש לי עסק",
        "אני עובד", "אני מנהל", "אני בעלים", "אני סוכן", "אני רופא", "אני עורך דין",
        "חנות", "מסעדה", "קליניקה", "משרד", "בית מרקחת", "מרפאה", "סלון", "מכון כושר",
        "נדל\"ן", "ביטוח", "רכב", "תכשיטים", "אופנה", "טכנולוגיה", "חינוך", "ייעוץ",
        "אני עוסק", "אני עובד בתחום", "התחום שלי", "העסק שלי", "החברה שלי"
    ]
    
    # Business type patterns in English  
    business_patterns_en = [
        "i have a store", "i have a restaurant", "i have a clinic", "i have an office", "i have a business",
        "i work in", "i manage", "i own", "i am a doctor", "i am a lawyer", "i am an agent",
        "store", "restaurant", "clinic", "office", "pharmacy", "salon", "gym", "fitness",
        "real estate", "insurance", "automotive", "jewelry", "fashion", "technology", "education", "consulting",
        "my business", "my company", "my field", "our business", "our company"
    ]
    
    # Check for business type indicators
    is_business_response = (
        any(pattern in text_lower for pattern in business_patterns_he) or
        any(pattern in text_lower for pattern in business_patterns_en)
    )
    
    if is_business_response:
        logger.info(f"[BUSINESS_TYPE] Detected business type in: '{text}'")
        return True
    
    return False

def detect_specific_use_case(text):
    """Detect when user describes a specific business use case or pain point"""
    text_lower = text.strip().lower()
    
    # Recruitment/HR use case patterns
    recruitment_patterns = [
        "מגייס עובדים", "גיוס עובדים", "מגייס אנשים", "מחפש עובדים", "רוצה לגייס",
        "מקבל טלפונים", "מלא טלפונים", "הרבה טלפונים", "טלפונים ללא הפסקה",
        "לסנן", "לסנן אנשים", "לסנן מועמדים", "סינון", "לא רלוונטי", "לא מתאים",
        "recruiting", "hiring", "hr", "human resources", "filter candidates", "screen applicants",
        "too many calls", "phone overload", "unqualified", "irrelevant candidates"
    ]
    
    # Restaurant/Food service patterns
    restaurant_patterns = [
        "מסעדה", "בר", "קפה", "אוכל", "תפריט", "הזמנות", "מקומות", "שולחנות",
        "restaurant", "cafe", "bar", "food", "menu", "reservations", "tables", "booking"
    ]
    
    # Retail/Store patterns  
    retail_patterns = [
        "חנות", "קמעונאות", "מוצרים", "מלאי", "מבצעים", "קניות", "לקוחות",
        "store", "retail", "shop", "products", "inventory", "sales", "customers", "shopping"
    ]
    
    # Real estate patterns
    realestate_patterns = [
        "נדל\"ן", "דירות", "בתים", "השכרה", "מכירה", "נכסים", "סיורים",
        "real estate", "apartments", "houses", "rental", "property", "tours", "listings"
    ]
    
    # Medical/Clinic patterns
    medical_patterns = [
        "קליניקה", "רופא", "מרפאה", "תורים", "חולים", "ביטוח", "טיפול",
        "clinic", "doctor", "medical", "appointments", "patients", "insurance", "treatment"
    ]
    
    # Check for specific use cases
    use_cases = {
        "recruitment": any(pattern in text_lower for pattern in recruitment_patterns),
        "restaurant": any(pattern in text_lower for pattern in restaurant_patterns),
        "retail": any(pattern in text_lower for pattern in retail_patterns),
        "real_estate": any(pattern in text_lower for pattern in realestate_patterns),
        "medical": any(pattern in text_lower for pattern in medical_patterns)
    }
    
    detected_use_cases = [use_case for use_case, detected in use_cases.items() if detected]
    
    if detected_use_cases:
        logger.info(f"[USE_CASE] Detected use case(s): {detected_use_cases} in: '{text}'")
        return detected_use_cases[0]  # Return first detected use case
    
    return None

def detect_positive_engagement(text):
    """Detect when user shows positive engagement or interest"""
    text_lower = text.strip().lower()
    
    # Positive engagement patterns in Hebrew
    positive_patterns_he = [
        "זה נשמע טוב", "זה מעניין", "אני מעוניין", "אני רוצה", "זה בדיוק מה שאני צריך",
        "זה יכול לעזור", "זה נראה טוב", "אני אוהב את זה", "זה נהדר", "זה מושלם",
        "כן", "בטח", "אפשר", "למה לא", "בואו ננסה", "אני רוצה לנסות"
    ]
    
    # Positive engagement patterns in English
    positive_patterns_en = [
        "sounds good", "interesting", "i'm interested", "i want", "this is exactly what i need",
        "this could help", "this looks good", "i like this", "this is great", "this is perfect",
        "yes", "sure", "okay", "why not", "let's try", "i want to try"
    ]
    
    # Check for positive engagement
    is_positive = (
        any(pattern in text_lower for pattern in positive_patterns_he) or
        any(pattern in text_lower for pattern in positive_patterns_en)
    )
    
    if is_positive:
        logger.info(f"[ENGAGEMENT] Detected positive engagement in: '{text}'")
        return True
    
    return False

def is_vague_gpt_answer(answer):
    """
    More intelligent vagueness detection that reduces false positives.
    Only triggers when answer is ACTUALLY useless.
    """
    if not answer or not answer.strip():
        return True
    
    # Must be extremely short to be considered vague
    if len(answer.strip()) < 15:
        return True
    
    # Only flag very generic responses
    truly_vague_phrases = [
        "i don't know anything about",
        "i have no information about", 
        "i cannot help you with this",
        "i'm not able to assist",
        "אין לי שום מידע על",
        "לא יכול לעזור עם זה",
        "לא מוכר לי"
    ]
    
    answer_lower = answer.lower()
    vague_count = sum(1 for phrase in truly_vague_phrases if phrase in answer_lower)
    
    # Only consider vague if multiple vague phrases or very short
    return vague_count >= 2 or (vague_count >= 1 and len(answer) < 30)

def is_truly_vague(answer):
    """Enhanced vagueness detection"""
    return is_vague_gpt_answer(answer)