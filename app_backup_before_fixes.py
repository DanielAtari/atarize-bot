from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
from datetime import timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
import re
import traceback
import time
from rapidfuzz import fuzz
import copy
import tiktoken
import logging

# === טעינת משתני סביבה === #
load_dotenv()

# === LOGGING CONFIGURATION === #
# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging for both development and production
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO in production
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Create logger instance
logger = logging.getLogger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TARGET = os.getenv("EMAIL_TARGET")

# === הגדרת Flask === #
app = Flask(__name__, static_folder="static/dist", static_url_path="")
app.secret_key = FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

# Session management - use Flask's session directly

# === GLOBAL CONFIGURATION === #
class Config:
    FUZZY_THRESHOLD = 70
    CHROMA_THRESHOLD = 1.4  # Relaxed threshold to catch more valid intents
    MIN_ANSWER_LENGTH = 10
    # Token limits for different models
    GPT4_TOKEN_LIMIT = 8192
    GPT4_TURBO_TOKEN_LIMIT = 128000
    GPT35_TOKEN_LIMIT = 4096
    MAX_PROMPT_TOKENS = 100000  # Much higher limit for GPT-4 Turbo

# === GLOBAL PATHS AND CLIENTS === #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")

embedding_func = OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-large"
)
chroma_client = PersistentClient(path=CHROMA_DB_PATH)
knowledge_collection = chroma_client.get_or_create_collection("atarize_knowledge", embedding_function=embedding_func)
intents_collection = None
try:
    intents_collection = chroma_client.get_or_create_collection("atarize_intents", embedding_function=embedding_func)
except Exception as e:
    logger.warning(f"[INIT WARNING] Could not load atarize_intents collection: {e}")

# Debug collections health at startup
def debug_collections_health():
    try:
        knowledge_count = knowledge_collection.count()
        intents_count = intents_collection.count() if intents_collection else 0
        logger.info(f"[STARTUP] Knowledge collection: {knowledge_count} docs")
        logger.info(f"[STARTUP] Intents collection: {intents_count} docs")
        if knowledge_count == 0:
            logger.warning("⚠️  WARNING: Knowledge collection is empty!")
        if intents_count == 0:
            logger.warning("⚠️  WARNING: Intents collection is empty!")
    except Exception as e:
        logger.error(f"❌ ChromaDB health check failed: {e}")

debug_collections_health()

# === TOKEN COUNTING UTILITIES === #
def count_tokens(messages, model="gpt-4-turbo"):
    """Count tokens in messages using tiktoken"""
    try:
        if model.startswith("gpt-4"):
            # Both gpt-4 and gpt-4-turbo use the same encoding
            encoding = tiktoken.encoding_for_model("gpt-4")
        elif model.startswith("gpt-3.5"):
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        else:
            encoding = tiktoken.get_encoding("cl100k_base")  # Default
        
        total_tokens = 0
        for message in messages:
            # Each message has role + content + some overhead
            total_tokens += 4  # Message overhead
            for key, value in message.items():
                total_tokens += len(encoding.encode(str(value)))
        total_tokens += 2  # Conversation overhead
        
        return total_tokens
    except Exception as e:
        logger.error(f"[TOKEN_COUNT] Error counting tokens: {e}")
        return 0

def log_token_usage(messages, model="gpt-4-turbo"):
    """Log token usage with warnings if approaching limits"""
    token_count = count_tokens(messages, model)
    limit = Config.GPT4_TOKEN_LIMIT if model.startswith("gpt-4") else Config.GPT35_TOKEN_LIMIT
    
    logger.debug(f"[TOKEN_USAGE] 📏 Token count: {token_count}")
    logger.debug(f"[TOKEN_USAGE] 🎯 Model: {model}")
    logger.debug(f"[TOKEN_USAGE] 📊 Limit: {limit}")
    logger.debug(f"[TOKEN_USAGE] 📈 Usage: {token_count/limit*100:.1f}%")
    
    if token_count > limit * 0.9:  # 90% of limit
        logger.warning(f"[TOKEN_USAGE] ⚠️  WARNING: Approaching token limit! ({token_count}/{limit})")
    elif token_count > limit * 0.7:  # 70% of limit
        logger.warning(f"[TOKEN_USAGE] 🔶 CAUTION: High token usage ({token_count}/{limit})")
    elif token_count > limit:
        logger.error(f"[TOKEN_USAGE] ❌ ERROR: Token limit exceeded! ({token_count}/{limit})")
    else:
        logger.debug(f"[TOKEN_USAGE] ✅ Token usage OK")
    
    return token_count

# === חיבור ל־OpenAI === #
client = OpenAI(api_key=OPENAI_API_KEY)

# === טעינת system prompt === #
with open(os.path.join(BASE_DIR, "data", "system_prompt_atarize.txt"), encoding="utf-8") as f:
    system_prompt = f.read()

# === טעינת קובץ JSON עם intents === #
with open(os.path.join(BASE_DIR, "data", "intents_config.json"), encoding="utf-8") as f:
    intents = json.load(f)
    # Add requires_chroma: true for all intents by default, can be customized per intent
    for intent in intents:
        if "requires_chroma" not in intent:
            intent["requires_chroma"] = True

# === פונקציה לזיהוי intent === #
def detect_intent(user_input, intents, threshold=70):
    user_input = user_input.lower()
    best_intent = None
    best_score = 0
    for intent in intents:
        for trigger in intent.get("triggers", []):
            score = fuzz.partial_ratio(user_input, trigger.lower())
            logger.debug(f"[DEBUG] Comparing input: '{user_input}' with trigger: '{trigger}' → Score: {score}")
            if score > best_score:
                best_score = score
                best_intent = intent
    if best_score >= threshold:
        return best_intent
    return None

def chroma_detect_intent(user_question, threshold=1.2):
    """
    Semantic intent detection using ChromaDB embeddings.
    Returns (intent_name, metadata) if a match is found below the threshold, else None.
    """
    logger.debug(f"[CHROMA_DETECT] Starting chroma intent detection for: '{user_question}' with threshold {threshold}")
    if intents_collection is None:
        logger.warning("[CHROMA_DETECT] ❌ Intents collection not initialized.")
        return None
    
    try:
        logger.debug(f"[CHROMA_DETECT] Querying intents collection...")
        results = intents_collection.query(query_texts=[user_question], n_results=1, include=["metadatas", "distances", "documents"])
        logger.debug(f"[CHROMA_DETECT] ✅ Query completed")
    except Exception as e:
        logger.error(f"[CHROMA_DETECT] ❌ Query failed: {e}")
        return None
    
    ids = results.get("ids", [[]])[0]  # ids will still be present in the result, but not as part of include
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    docs = results.get("documents", [[]])[0]
    
    if not ids:
        logger.debug("[CHROMA_DETECT] ❌ No intent match found in results.")
        return None
    
    top_id = ids[0]
    top_meta = metadatas[0]
    top_distance = distances[0]
    top_doc = docs[0]
    
    logger.debug(f"[CHROMA_DETECT] Results:")
    logger.debug(f"[CHROMA_DETECT]   Top match: {top_id}")
    logger.debug(f"[CHROMA_DETECT]   Distance: {top_distance}")
    logger.debug(f"[CHROMA_DETECT]   Threshold: {threshold}")
    logger.debug(f"[CHROMA_DETECT]   Content preview: {top_doc[:100]}...")
    logger.debug(f"[CHROMA_DETECT]   Metadata: {top_meta}")
    
    if top_distance < threshold:
        logger.debug(f"[CHROMA_DETECT] ✅ Intent accepted (distance {top_distance} < {threshold})")
        return top_id, top_meta
    else:
        logger.debug(f"[CHROMA_DETECT] ❌ Intent rejected (distance {top_distance} >= {threshold})")
    return None

# === שליחת התראה למייל עם דיבאג === #
def send_email_notification(subject, message):
    logger.info(f"📧 Attempting to send email...")
    logger.info(f"Subject: {subject}")
    logger.debug(f"Content:\n{message}")
    logger.debug(f"From: {EMAIL_USER} → To: {EMAIL_TARGET}")

    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TARGET

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        logger.info("✅ Email sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")
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

def detect_lead_info(text):
    # Simple check for email, phone, and name (expand as needed)
    has_email = "@" in text or ".com" in text or "מייל" in text
    has_phone = any(x in text for x in ["050", "052", "053", "054", "055", "056", "057", "058", "טלפון"])
    has_name = any(x in text for x in ["שם", "name"])
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
    
    # Detect specific use case
    if any(pattern in text_lower for pattern in recruitment_patterns):
        if any(word in text_lower for word in ["מגייס", "גיוס", "recruiting", "hiring"]) and \
           any(word in text_lower for word in ["טלפונים", "לסנן", "calls", "filter", "screen"]):
            logger.info(f"[USE_CASE] Detected recruitment use case with pain points")
            return "recruitment_screening"
    
    elif any(pattern in text_lower for pattern in restaurant_patterns):
        return "restaurant_service"
    elif any(pattern in text_lower for pattern in retail_patterns):
        return "retail_automation"
    elif any(pattern in text_lower for pattern in realestate_patterns):
        return "realestate_leads"
    elif any(pattern in text_lower for pattern in medical_patterns):
        return "medical_scheduling"
    
    return None

def get_use_case_specific_response(use_case, user_question, language="he"):
    """Generate targeted response for specific business use cases"""
    
    if use_case == "recruitment_screening":
        if language == "he":
            return """בדיוק בשביל זה הבוט מושלם! 🎯

**סינון אוטומטי של מועמדים:**
• הבוט שואל שאלות מסננות בסיסיות (ניסיון, זמינות, דרישות שכר)
• מועמדים לא מתאימים מקבלים תשובה מיידית ונדחים בנימוס
• רק מועמדים איכותיים מועברים אליך לשיחה

**יתרונות ענקיים:**
📞 חיסוך של 70-80% מהטלפונים הלא רלוונטיים
⏰ הבוט עובד 24/7 - אפילו בלילה או בסופ"ש
📋 איסוף מידע מסודר מכל מועמד (קו"ח, זמינות, ציפיות)
🎯 הגעה אליך רק של מועמדים שעוברים את הקריטריונים שלך

**דוגמה**: הבוט שואל "איזה ניסיון יש לך בתחום? מה זמינותך לעבודה? מה ציפיות השכר?" - ומי שלא מתאים פשוט לא מגיע אליך.

כמה מועמדים בערך מתקשרים אליך בשבוע? ואיזה תחום גיוס?"""
        else:
            return """That's exactly what the bot is perfect for! 🎯

**Automated Candidate Screening:**
• Bot asks basic filtering questions (experience, availability, salary expectations)
• Unqualified candidates get immediate, polite responses and are filtered out
• Only quality candidates are forwarded to you for actual conversation

**Huge Benefits:**
📞 Saves 70-80% of irrelevant phone calls
⏰ Bot works 24/7 - even nights and weekends
📋 Collects organized info from each candidate (CV, availability, expectations)
🎯 Only candidates who meet your criteria reach you

**Example**: Bot asks "What experience do you have in this field? What's your availability? Salary expectations?" - those who don't fit simply don't reach you.

How many candidates typically call you per week? And what field are you recruiting for?"""
    
    elif use_case == "restaurant_service":
        if language == "he":
            return """מושלם למסעדות! הבוט חוסך המון טלפונים על:
• תפריט ומחירים
• זמינות ושעות פתיחה  
• הזמנת מקומות
• שאלות על אלרגנים
• אירועים מיוחדים

כמה טלפונים בדרך כלל מקבלים ביום?"""
        else:
            return """Perfect for restaurants! The bot saves tons of calls about:
• Menu and prices
• Availability and hours
• Table reservations  
• Allergen questions
• Special events

How many calls do you typically get per day?"""
    
    # Add other use cases as needed...
    else:
        if language == "he":
            return "נשמע שיש לך צורך ספציפי! הבוט יכול להתאים בדיוק לתחום שלך. איזה סוג עסק זה?"
        else:
            return "Sounds like you have a specific need! The bot can be perfectly tailored to your field. What type of business is it?"

def get_business_specific_response(business_input, language="he"):
    """Generate targeted response based on detected business type"""
    business_lower = business_input.lower()
    
    if language == "he":
        # Specific business type responses in Hebrew
        if any(word in business_lower for word in ["חנות", "קמעונאות", "מכירות"]):
            return "מעולה! חנויות נהנות מהבוט במיוחד - הוא עוזר עם שאלות על מוצרים, מלאי, מחירים ושעות פתיחה. גם אוסף פרטי לקוחות לעדכונים על מבצעים. איך הלקוחות שלך בדרך כלל פונים אליך - בטלפון, ברשתות או באתר?"
        elif any(word in business_lower for word in ["מסעדה", "בר", "קפה", "אוכל"]):
            return "מושלם! בוטים במסעדות חוסכים המון טלפונים - תפריט, אלרגנים, הזמנות מקום, שעות ואירועים מיוחדים. כמה שיחות טלפון בערך מקבלים ביום ממוצע?"
        elif any(word in business_lower for word in ["קליניקה", "רופא", "מרפאה", "רפואי"]):
            return "נהדר! קליניקות משתמשות בבוט לתיאום תורים, שאלות על טיפולים ועלויות, ואפילו שאלונים לפני הגעה. מה התהליך הנוכחי שלך לקביעת תורים?"
        elif any(word in business_lower for word in ["נדל\"ן", "דירות", "בתים", "השכרה"]):
            return "מצוין! בנדל\"ן הבוט אוסף קריטריונים (מיקום, תקציב, חדרים), שולח נכסים מתאימים ומתאם סיורים. איך אתה כרגע מקבל פניות - דרך האתר, יד2, או טלפונים?"
        else:
            return "נשמע מעניין! יש לי דוגמאות איך הבוט עוזר בתחומים שונים - מסעדות, קליניקות, נדל\"ן, חנויות ועוד. מה הכי מעניין אותך לדעת - איך זה חוסך זמן או איך זה עוזר עם המכירות?"
    else:
        # English responses
        if any(word in business_lower for word in ["store", "retail", "shop", "sales"]):
            return "Excellent! Retail stores love the bot - it handles product questions, inventory, pricing, and hours. Plus it collects customer details for promotions. How do your customers usually contact you - phone, social media, or website?"
        elif any(word in business_lower for word in ["restaurant", "bar", "cafe", "food"]):
            return "Perfect! Restaurant bots save tons of phone calls - menu, allergens, reservations, hours, and special events. How many phone calls do you typically get per day?"
        elif any(word in business_lower for word in ["clinic", "doctor", "medical", "healthcare"]):
            return "Great! Clinics use bots for appointment scheduling, treatment questions, costs, and even pre-visit questionnaires. What's your current process for booking appointments?"
        elif any(word in business_lower for word in ["real estate", "properties", "apartments", "rental"]):
            return "Excellent! In real estate, the bot collects criteria (location, budget, rooms), sends matching properties, and schedules tours. How do you currently receive leads - website, portals, or phone calls?"
        else:
            return "Sounds interesting! I have examples of how the bot helps different industries - restaurants, clinics, real estate, stores, and more. What interests you most - how it saves time or how it helps with sales?"

def detect_positive_engagement(text):
    """Detect when user shows interest or engagement but isn't giving specific business info"""
    text_lower = text.strip().lower()
    
    positive_patterns_he = [
        "כן", "בטח", "נהדר", "מעניין", "אוקיי", "בסדר", "טוב", "נשמע טוב", "אני מעוניין", 
        "רוצה לדעת", "ספר לי", "איך זה עובד", "תן לי דוגמה", "מה זה אומר"
    ]
    
    positive_patterns_en = [
        "yes", "sure", "great", "interesting", "okay", "ok", "good", "sounds good", "i'm interested",
        "want to know", "tell me", "how does it work", "give me an example", "what does that mean"
    ]
    
    is_positive = (
        any(pattern in text_lower for pattern in positive_patterns_he) or
        any(pattern in text_lower for pattern in positive_patterns_en)
    )
    
    if is_positive and len(text.strip()) < 30:  # Short positive responses
        logger.info(f"[ENGAGEMENT] Detected positive engagement: '{text}'")
        return True
    
    return False

def get_follow_up_content_by_topic(topic, business_type=None, language="he"):
    """Generate specific follow-up content based on conversation context"""
    
    if topic == "technology_deep_dive":
        if language == "he":
            return """נהדר! אסביר לך את הטכנולוgia מאחורי הבוט:

🧠 **GPT + Vector Database** - הבוט משלב בינה מלאכותית עם מאגר מידע חכם. הוא לא רק זוכר מה אמרת, אלא מבין את הקונטקסט ומחבר בין מידע שונה.

🎯 **זיהוי כוונות חכם** - הבוט מזהה מה המשתמש באמת רוצה, גם אם הוא לא ביטא את זה בצורה מושלמת. למשל, "כמה זה עולה" יובן כ"בקשה למחירון מפורט".

🔄 **למידה מתמשכת** - הבוט משתפר מכל שיחה, זוכר תבניות נפוצות ומתאים את התשובות לסגנון הספציפי של העסק.

מה מעניין אותך יותר - איך זה חוסך לך זמן, או איך זה משפר את השירות ללקוחות?"""
        else:
            return """Great! Let me explain the technology behind the bot:

🧠 **GPT + Vector Database** - The bot combines AI with intelligent knowledge storage. It doesn't just remember what you said, but understands context and connects different pieces of information.

🎯 **Smart Intent Recognition** - The bot understands what users really want, even if they don't express it perfectly. For example, "how much does it cost" is understood as "request for detailed pricing".

🔄 **Continuous Learning** - The bot improves from every conversation, remembers common patterns, and adapts responses to your business's specific style.

What interests you more - how it saves you time, or how it improves customer service?"""
    
    elif topic == "business_benefits_deep":
        content_base = """
🕒 **חיסוך זמן משמעותי** - הבוט מטפל ב-80% מהשאלות הנפוצות ללא התערבות שלך. אתה מתפנה לעסקים חדשים במקום לענות על אותן השאלות שוב ושוב.

📈 **שיפור המרות** - לקוחות מקבלים מענה מיידי 24/7, מה שמגדיל את הסיכוי שהם יישארו מעוניינים ויבצעו רכישה.

💰 **ROI מהיר** - העלות החודשית של הבוט פחותה משעת עבודה אחת של עובד, אבל הוא עובד כל היום.

📊 **תובנות עסקיות** - הבוט אוסף דאטה על מה הלקוחות שואלים הכי הרבה, מה מעניין אותם, ואילו נקודות כאב יש להם."""
        
        if business_type and any(biz in business_type.lower() for biz in ["חנות", "store", "retail"]):
            content_base += "\n\n🛍️ **ספציפית לחנויות** - הבוט יכול לעזור עם מלאי, להכווין ללקוחות למוצרים נכונים, ולאסוף פרטים להודעות על מבצעים חדשים."
        elif business_type and any(biz in business_type.lower() for biz in ["מסעדה", "restaurant", "food"]):
            content_base += "\n\n🍽️ **ספציפית למסעדות** - הבוט חוסך את רוב השיחות על תפריט, הזמנת מקומות, ושעות פתיחה. גם יכול לאסוף העדפות לאירועים מיוחדים."
        
        if language == "he":
            return f"מושלם! הנה איך הבוט באמת עוזר לעסק:{content_base}\n\nמה הכי מעניין אותך מהרשימה? או שיש נושא אחר שתרצה לחקור?"
        else:
            # English version would be similar but translated
            return f"Perfect! Here's how the bot really helps your business:{content_base}\n\nWhat interests you most from this list? Or is there another topic you'd like to explore?"
    
    elif topic == "implementation_details":
        if language == "he":
            return """בואו נדבר על ההטמעה בפועל:

⚙️ **תהליך הקמה (2-5 ימים)**:
יום 1-2: איסוף המידע שלך (טקסטים שיווקיים, שאלות נפוצות, מדיניות המחירים)
יום 3-4: בניית הבוט המותאם אישית ובדיקות
יום 5: הטמעה באתר והדרכה קצרה

🔧 **מה אתה צריך לספק**:
• טקסטים שיווקיים קיימים (אתר, עלונים)
• שאלות נפוצות מלקוחות
• מדיניות מחירים ושירותים
• טון הדיבור הרצוי (רשמי/חבבי/הומוריסטי)

📱 **אפשרויות הטמעה**:
• באתר הקיים שלך (קוד HTML פשוט)
• כלינק נפרד לשיתוף ברשתות
• אינטגרציה עם WhatsApp Business (עם אישור Meta)

איך אתה מעדיף להתחיל - עם הטמעה באתר או כלינק נפרד?"""
        else:
            return """Let's talk about the actual implementation:

⚙️ **Setup Process (2-5 days)**:
Day 1-2: Gathering your info (marketing texts, FAQs, pricing policy)
Day 3-4: Building your custom bot and testing
Day 5: Website integration and quick training

🔧 **What you need to provide**:
• Existing marketing materials (website, brochures)
• Common customer questions
• Pricing and service policies
• Desired tone (formal/casual/humorous)

📱 **Integration options**:
• On your existing website (simple HTML code)
• Separate link for social media sharing
• WhatsApp Business integration (with Meta approval)

How would you prefer to start - with website integration or a separate link?"""
    
    elif topic == "pricing_breakdown":
        if language == "he":
            return """בואו נפרק את התמחור בפירוט:

💰 **עלויות חד פעמיות**:
• הקמת הבוט: 600₪ (כולל מע"מ)
• עזרה בהטמעה באתר: +200₪ (אופציונלי)
• עדכונים גדולים בעתיד: מחיר לפי התיאום

📊 **חבילות חודשיות**:
• Basic (59₪): עד 100 הודעות - מושלם לעסקים קטנים
• Pro (99₪): עד 500 הודעות - מתאים לרוב העסקים
• Business: 2000+ הודעות - תכנית מותאמת אישית

🎯 **מה נכלל**:
• הוסטינג ותחזוקה של הבוט
• עדכונים קטנים בתוכן (ללא עלות נוספת)
• תמיכה טכנית
• סטטיסטיקות והתקנות

💡 **השוואה**: עובד במינימום עולה ~30₪ לשעה. הבוט עולה פחות מ-2 שעות עבודה לחודש, אבל עובד 24/7.

איזה נפח הודעות אתה מעריך שתצטרך בחודש?"""
        else:
            return """Let's break down the pricing in detail:

💰 **One-time costs**:
• Bot setup: 600₪ (including VAT)
• Website integration help: +200₪ (optional)
• Major future updates: price by agreement

📊 **Monthly plans**:
• Basic (59₪): up to 100 messages - perfect for small businesses
• Pro (99₪): up to 500 messages - suitable for most businesses
• Business: 2000+ messages - custom plan

🎯 **What's included**:
• Bot hosting and maintenance
• Small content updates (no extra cost)
• Technical support
• Statistics and insights

💡 **Comparison**: Minimum wage employee costs ~30₪/hour. The bot costs less than 2 work hours per month, but works 24/7.

What message volume do you estimate you'll need per month?"""
    
    else:
        # Generic follow-up for unknown topics
        if language == "he":
            return "נהדר שאתה מעוניין! איזה היבט מעניין אותך הכי הרבה - הטכנולוגיה, היתרונות העסקיים, תהליך ההטמעה, או פירוט המחירים?"
        else:
            return "Great that you're interested! Which aspect interests you most - the technology, business benefits, implementation process, or pricing details?"

def detect_follow_up_context(question, session):
    """Analyze conversation history to understand what specific follow-up content is needed"""
    history = session.get("history", [])
    if len(history) < 2:
        return None, None
    
    # Get the last few bot messages to understand context
    recent_bot_messages = []
    for i in range(len(history) - 1, max(len(history) - 6, -1), -1):
        if history[i].get("role") == "assistant":
            recent_bot_messages.append(history[i].get("content", "").lower())
    
    recent_context = " ".join(recent_bot_messages)
    question_lower = question.lower().strip()
    
    # Detect "yes" responses to specific offers
    is_yes_response = any(pattern in question_lower for pattern in [
        "כן", "yes", "בטח", "sure", "אוקיי", "ok", "נהדר", "great", "מעניין", "interesting"
    ]) and len(question.strip()) < 20
    
    if not is_yes_response:
        return None, None
    
    # Determine what follow-up content to provide based on recent context
    if any(phrase in recent_context for phrase in [
        "טכנולוגיה", "technology", "איך זה עובד", "how it works", "gpt", "vector"
    ]):
        return "technology_deep_dive", session.get("business_info", "")
    
    elif any(phrase in recent_context for phrase in [
        "איך זה עוזר", "business benefits", "יתרונות", "חוסך", "saves", "roi"
    ]):
        return "business_benefits_deep", session.get("business_info", "")
    
    elif any(phrase in recent_context for phrase in [
        "איך מתחילים", "how to start", "הקמה", "setup", "implementation", "תהליך"
    ]):
        return "implementation_details", session.get("business_info", "")
    
    elif any(phrase in recent_context for phrase in [
        "מחיר", "price", "עלות", "cost", "כמה", "how much", "תמחור"
    ]):
        return "pricing_breakdown", session.get("business_info", "")
    
    # Check if bot offered examples or details in recent messages
    elif any(phrase in recent_context for phrase in [
        "רוצה לראות דוגמה", "want to see an example", "תן לי דוגמה", "give me an example",
        "רוצה לדעת עוד", "want to know more", "מעניין אותך", "interests you"
    ]):
        # Default to business benefits if we can't determine specific context
        return "business_benefits_deep", session.get("business_info", "")
    
    return None, None

def detect_language(text):
    """Detect if text is Hebrew or English based on character presence"""
    return "he" if re.search(r'[א-ת]', text) else "en"

def is_greeting(text):
    """Check if text is a greeting/conversation opener"""
    greeting_phrases = [
        "hi", "hello", "hey", "shalom", "שלום", "היי", "מה נשמע", "מה קורה", "what's up", "how are you", "good morning", "good evening", "evening", "morning", "אהלן", "בוקר טוב"
    ]
    text_lower = text.strip().lower()
    return any(phrase in text_lower for phrase in greeting_phrases)

def get_natural_greeting(language, greeting_text=""):
    """Generate natural, human-like greeting that varies and feels conversational"""
    import random
    
    if language == "he":
        # Natural Hebrew greetings with variety
        warm_responses = [
            f"היי! תודה שפניתם 😊 אני עטרה מצוות Atarize. נעים להכיר! איך אוכל לעזור לכם היום?",
            f"שלום! אני מקווה שהכול בסדר אצלכם. אני עטרה מ-Atarize ואשמח לעזור בכל מה שתצטרכו!",
            f"היי שם! תודה שפניתם אלינו 🙂 אני עטרה, הבוטית של Atarize. איך המצב? במה אוכל לעזור?",
            f"שלום ובוקר טוב! אני עטרה מ-Atarize ואני כאן כדי לעזור לכם. מה מעניין אתכם לדעת?"
        ]
        
        # Add contextual responses based on greeting type
        if "בוקר" in greeting_text.lower():
            return "בוקר טוב! איזה יום נהדר להתחיל משהו חדש 😊 אני עטרה מ-Atarize ואשמח לעזור לכם לגלות איך הבוט שלנו יכול לשפר את העסק שלכם. במה נתחיל?"
        elif "ערב" in greeting_text.lower():
            return "ערב טוב! תודה שפניתם גם בשעה המאוחרת הזו 🌙 אני עטרה מ-Atarize ואני כאן בשבילכם 24/7. איך אוכל לעזור?"
        else:
            return random.choice(warm_responses)
    else:
        # Natural English greetings with variety  
        warm_responses = [
            f"Hi there! Thanks for reaching out 😊 I'm Atara from the Atarize team. Hope you're having a great day! How can I help you?",
            f"Hello! I hope you're doing well. I'm Atara from Atarize and I'm here to help with whatever you need!",
            f"Hey! Thanks for stopping by 🙂 I'm Atara, Atarize's AI assistant. What's on your mind today?",
            f"Hi! Good to meet you. I'm Atara from Atarize and I'd love to help you explore how we can support your business!"
        ]
        
        # Add contextual responses based on greeting type
        if "morning" in greeting_text.lower():
            return "Good morning! What a great day to start something new 😊 I'm Atara from Atarize and I'd love to help you discover how our chatbot can improve your business. Where shall we start?"
        elif "evening" in greeting_text.lower():
            return "Good evening! Thanks for reaching out even at this hour 🌙 I'm Atara from Atarize and I'm here for you 24/7. How can I help?"
        else:
            return random.choice(warm_responses)

def is_small_talk(text):
    """Check for very basic small talk that shouldn't trigger full conversation"""
    basic_small_talk = ["ok", "אוקיי", "כן", "yes", "no", "לא", "תודה", "thanks", "נחמד", "nice", "cool", "טוב"]
    text_lower = text.strip().lower()
    return any(phrase == text_lower for phrase in basic_small_talk)

def should_continue_conversation(question, session):
    """Determine if this is a follow-up that should continue the conversation naturally"""
    # If intro was already given and this is a greeting, treat as follow-up
    if session.get("intro_given") and is_greeting(question):
        return True
    
    # If there's chat history, this is part of ongoing conversation  
    if len(session.get("history", [])) > 0:
        return True
        
    return False

def get_conversation_context(question, session):
    """Analyze conversation history to understand follow-up questions in context"""
    history = session.get("history", [])
    if len(history) < 2:
        return None, None
    
    # Get recent conversation context (last 4 messages)
    recent_context = history[-4:]
    
    # Extract topics from recent conversation
    context_text = " ".join([msg.get("content", "") for msg in recent_context])
    context_lower = context_text.lower()
    question_lower = question.lower()
    
    # Context-aware topic detection
    contextual_intent = None
    context_info = {}
    
    # WhatsApp + Meta context
    if any(term in context_lower for term in ["whatsapp", "וואטסאפ"]) and \
       any(term in question_lower for term in ["meta", "approval", "אישור", "verification", "מאומת", "operator"]):
        contextual_intent = "faq"
        context_info = {
            "topic": "whatsapp_meta_verification",
            "specific_question": "Meta business verification for WhatsApp integration"
        }
        logger.info(f"[CONTEXT_BRIDGE] Detected WhatsApp+Meta follow-up question")
    
    # CRM + Integration context
    elif any(term in context_lower for term in ["crm", "integration", "אינטגרציה", "מערכות"]) and \
         any(term in question_lower for term in ["how", "איך", "possible", "אפשר", "requirements", "דרישות"]):
        contextual_intent = "faq" 
        context_info = {
            "topic": "crm_integration",
            "specific_question": "CRM and system integration capabilities"
        }
        logger.info(f"[CONTEXT_BRIDGE] Detected CRM integration follow-up question")
    
    # Pricing + Plans context
    elif any(term in context_lower for term in ["price", "cost", "מחיר", "עלות", "שח"]) and \
         any(term in question_lower for term in ["what about", "מה לגבי", "other", "אחר", "more", "עוד"]):
        contextual_intent = "pricing"
        context_info = {
            "topic": "pricing_details", 
            "specific_question": "Additional pricing information or plan details"
        }
        logger.info(f"[CONTEXT_BRIDGE] Detected pricing follow-up question")
    
    # Business use cases context
    elif any(term in context_lower for term in ["business", "עסק", "industry", "תחום"]) and \
         any(term in question_lower for term in ["example", "דוגמה", "how", "איך", "like mine", "כמו שלי"]):
        contextual_intent = "chatbot_use_cases"
        context_info = {
            "topic": "business_specific_examples",
            "specific_question": "Industry-specific chatbot use cases"
        }
        logger.info(f"[CONTEXT_BRIDGE] Detected business use case follow-up question")
    
    if contextual_intent:
        logger.info(f"[CONTEXT_BRIDGE] ✅ Contextual intent detected: {contextual_intent} | Topic: {context_info.get('topic')}")
        return contextual_intent, context_info
    else:
        logger.debug(f"[CONTEXT_BRIDGE] No specific context detected for follow-up")
        return None, None

def build_enriched_context(question, session, greeting_context=None):
    """Build enriched context from all detection signals for GPT"""
    context_signals = []
    
    # Greeting context
    if greeting_context:
        if greeting_context.get("is_first_greeting"):
            context_signals.append("CONTEXT: This is the user's first greeting - provide a warm welcome and introduction.")
        elif greeting_context.get("is_repeat_greeting"):
            context_signals.append("CONTEXT: This is a repeat greeting in an ongoing conversation - respond naturally and continue.")
    
    # Use case context
    if session.get("specific_use_case"):
        context_signals.append(f"CONTEXT: User has specific business use case: {session['specific_use_case']}")
    
    # Follow-up context
    if session.get("follow_up_context"):
        context_signals.append(f"CONTEXT: User is asking follow-up about: {session['follow_up_context']}")
    
    # Engagement context
    if session.get("positive_engagement"):
        context_signals.append("CONTEXT: User shows positive engagement and interest")
    
    # Conversion opportunity
    if session.get("conversion_opportunity"):
        context_signals.append("CONTEXT: This is a potential conversion opportunity - be helpful and guide naturally")
    
    # Lead collection context
    if session.get("interested_lead_pending"):
        context_signals.append("CONTEXT: User may be interested in leaving contact details if appropriate")
    
    return "\n".join(context_signals) if context_signals else ""


def build_contextual_prompt(question, context_info, base_context):
    """Build enhanced prompt that bridges conversation context"""
    if not context_info:
        return base_context
    
    topic = context_info.get("topic", "")
    specific_question = context_info.get("specific_question", "")
    
    if topic == "whatsapp_meta_verification":
        context_enhancement = f"""
🔗 CONVERSATION CONTEXT: The user previously asked about WhatsApp deployment and is now asking a follow-up about Meta/approval/verification.

IMPORTANT: The knowledge base contains specific information about Meta business verification requirements for WhatsApp integration. Use this information to provide a confident, detailed answer about:
- Meta Business account verification requirements
- WhatsApp official integration process
- Business verification steps

Connect this follow-up question to the previous WhatsApp discussion and provide specific, actionable information from the knowledge base.
"""
    elif topic == "crm_integration":
        context_enhancement = f"""
🔗 CONVERSATION CONTEXT: The user previously asked about CRM/system integrations and wants more details.

Use the knowledge base information about integration capabilities, requirements, and the case-by-case evaluation process. Provide specific details about what's possible.
"""
    elif topic == "pricing_details":
        context_enhancement = f"""
🔗 CONVERSATION CONTEXT: The user previously discussed pricing and wants additional pricing information.

Provide comprehensive pricing details from the knowledge base, including setup costs, monthly plans, and any additional services.
"""
    elif topic == "business_specific_examples":
        context_enhancement = f"""
🔗 CONVERSATION CONTEXT: The user discussed business applications and wants specific examples.

Use the detailed business use cases from the knowledge base to provide industry-specific examples and applications.
"""
    else:
        context_enhancement = ""
    
    return f"{base_context}\n\n{context_enhancement}"

def get_conversational_enhancement(question, intent_name):
    """Generate engaging conversational instructions that the bot can actually fulfill with available knowledge"""
    
    # Check for general service inquiries
    service_keywords = ["השירות", "מה אתם", "מה זה", "רוצה לשאול", "service", "what do you", "want to ask"]
    if any(keyword in question.lower() for keyword in service_keywords):
        if detect_language(question) == "he":
            return "\n💡 התנהגות: הסבירי בחמימות מה Atarize עושה בהתבסס על המידע שיש לך. ואז שאלי: 'מה הכי מעניין אותך - הטכנולוגיה מאחורי הבוט, או איך זה עוזר לעסק כמו שלך?' כך תוכלי להכווין לתוכן מעמיק שיש לך."
        else:
            return "\n💡 Behavior: Warmly explain what Atarize does based on your available information. Then ask: 'What interests you most - the technology behind the bot, or how it helps a business like yours?' This way you can direct to the detailed content you have."
    
    # Check for pricing questions
    pricing_keywords = ["מחיר", "עולה", "עלות", "כסף", "price", "cost", "money"]
    if any(keyword in question.lower() for keyword in pricing_keywords):
        if detect_language(question) == "he":
            return "\n💡 התנהגות: ענה על המחיר בצורה ברורה מהמידע שיש לך, הסברי את הערך העסקי שהבוט מביא (חיסוך זמן, שירות 24/7, איסוף לידים). ואז שאלי: 'איזה סוג עסק יש לך? יש לי דוגמאות ספציפיות איך הבוט חוסך כסף בתחומים שונים.'"
        else:
            return "\n💡 Behavior: Answer the price clearly from your available info, explain the business value the bot brings (time savings, 24/7 service, lead collection). Then ask: 'What type of business do you have? I have specific examples of how the bot saves money in different industries.'"
    
    # Check for setup/timing questions
    if intent_name == "onboarding_process":
        if detect_language(question) == "he":
            return "\n💡 התנהגות: ענה על זמני ההקמה מהמידע שיש לך (2-5 ימים), הסברי את התהליך הפשוט. ואז שאלי: 'איזה תחום עסקי מעניין אותך? יש לי דוגמאות מעשיות למסעדות, נדל\"ן, קליניקות ועוד' - כך תוכלי לתת תוכן ספציפי."
        else:
            return "\n💡 Behavior: Answer about setup times from your available info (2-5 days), explain the simple process. Then ask: 'What business area interests you? I have practical examples for restaurants, real estate, clinics and more' - this way you can provide specific content."
    
    # Check for use case questions - be specific about what you can deliver
    if intent_name == "chatbot_use_cases":
        if detect_language(question) == "he":
            return "\n💡 התנהגות: תני דוגמאות קונקרטיות מהמידע המפורט שיש לך על שימושים בתחומים שונים. ואז שאלי: 'איזה מהתחומים הכי רלוונטי לך - מסעדות, נדל\"ן, קליניקות, או משהו אחר?' כך תוכלי לתת הסבר מעמיק יותר."
        else:
            return "\n💡 Behavior: Give concrete examples from the detailed information you have about uses in different industries. Then ask: 'Which area is most relevant to you - restaurants, real estate, clinics, or something else?' This way you can provide deeper explanations."
    
    # Check for technical questions - direct to available tech content
    if intent_name in ["tech_explanation", "about_atarize"]:
        if detect_language(question) == "he":
            return "\n💡 התנהגות: הסברי את הטכנולוגיה (GPT, Vector DB) בהתבסס על המידע המפורט שיש לך. ואז שאלי: 'רוצה לדעת איך הטכנולוגיה הזו עוזרת בפועל לעסק כמו שלך?' - כך תוכלי לחבר לתוכן העסקי שיש לך."
        else:
            return "\n💡 Behavior: Explain the technology (GPT, Vector DB) based on the detailed information you have. Then ask: 'Want to know how this technology actually helps a business like yours?' - this way you can connect to the business content you have."
    
    # Check for business value/memory questions
    if intent_name == "bot_memory_and_value":
        if detect_language(question) == "he":
            return "\n💡 התנהגות: הסברי את יכולות הזיכרון והערך העסקי מהמידע שיש לך. ואז שאלי: 'איזה סוג עסק יש לך? אשמח להסביר איך הבוט ישפר את השירות והמכירות דווקא בתחום שלך.'"
        else:
            return "\n💡 Behavior: Explain the memory capabilities and business value from your available information. Then ask: 'What type of business do you have? I'd love to explain how the bot will improve service and sales specifically in your field.'"
    
    # Default: only ask questions you can answer
    if detect_language(question) == "he":
        return "\n💡 התנהגות: עני בצורה ידידותית וטבעית מהמידע שזמין לך. אם תשאלי שאלת המשך, וודאי שיש לך מידע מפורט לענות עליה מהמאגר שלך."
    else:
        return "\n💡 Behavior: Answer in a friendly and natural way from your available information. If you ask a follow-up question, make sure you have detailed information to answer it from your knowledge base."

def get_context_from_chroma(question, collection):
    chroma_kwargs = {"query_texts": [question], "n_results": 3, "include": ["documents", "metadatas"]}
    try:
        results = collection.query(**chroma_kwargs)
        chroma_docs = results.get("documents", [[]])[0]
        chroma_metas = results.get("metadatas", [[]])[0]
        logger.debug("[CHROMA] Retrieved documents:")
        for i, (doc, meta) in enumerate(zip(chroma_docs, chroma_metas)):
            logger.debug(f"  Doc {i+1}:\n    Content: {doc[:200]}{'...' if len(doc) > 200 else ''}\n    Metadata: {meta}")
        return "\n---\n".join(chroma_docs)
    except Exception as e:
        logger.error(f"[Chroma ERROR] {e}")
        return ""

def get_knowledge_by_intent(intent_name):
    """
    Retrieve documents from the 'atarize_knowledge' Chroma collection where metadata.intent == intent_name.
    Returns a list of (document, metadata) tuples.
    """
    try:
        results = knowledge_collection.get(where={"intent": intent_name}, include=["documents", "metadatas"])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        logger.debug(f"[KNOWLEDGE RETRIEVAL] Retrieved {len(docs)} documents for intent '{intent_name}'")
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            logger.debug(f"  Doc {i+1}:\n    Content: {doc[:200]}{'...' if len(doc) > 200 else ''}\n    Metadata: {meta}")
        return list(zip(docs, metas))
    except Exception as e:
        logger.error(f"[KNOWLEDGE RETRIEVAL ERROR] {e}")
        return []

def get_examples_by_intent(intent_name, n_examples=3):
    """
    Retrieve up to n_examples from the 'atarize_knowledge' Chroma collection for the given intent.
    Returns a list of example texts.
    """
    try:
        results = knowledge_collection.get(where={"intent": intent_name}, include=["documents", "metadatas"])
        docs = results.get("documents", [])
        ids = results.get("ids", []) if "ids" in results else []
        examples = docs[:n_examples]
        logger.debug(f"[FEW-SHOT] Loaded {len(examples)} example(s) for intent '{intent_name}':")
        for i, doc in enumerate(examples):
            doc_id = ids[i] if i < len(ids) else 'N/A'
            logger.debug(f"  Example {i+1} (ID: {doc_id}): {doc[:120]}{'...' if len(doc) > 120 else ''}")
        return examples
    except Exception as e:
        logger.error(f"[FEW-SHOT ERROR] Failed to load examples for intent '{intent_name}': {e}")
        return []

def get_enhanced_context_retrieval(question, intent_name, lang="he", n_results=4):
    """Enhanced context retrieval that surfaces underutilized content through multiple strategies"""
    logger.debug(f"[ENHANCED_RETRIEVAL] Starting enhanced retrieval for: '{question}'")
    
    # Strategy 1: Intent-based retrieval (existing method)
    knowledge_docs = get_knowledge_by_intent(intent_name)
    
    # Strategy 2: If intent fails or returns insufficient results, try semantic search on question
    if len(knowledge_docs) < 2:
        logger.debug(f"[ENHANCED_RETRIEVAL] Intent retrieval insufficient ({len(knowledge_docs)} docs), trying semantic search")
        try:
            # Semantic search on user question to catch underutilized content
            semantic_results = knowledge_collection.query(
                query_texts=[question],
                n_results=n_results,
                where={"language": lang} if lang else None,
                include=["documents", "metadatas"]
            )
            
            semantic_docs = semantic_results.get("documents", [[]])[0] if semantic_results.get("documents") else []
            semantic_metas = semantic_results.get("metadatas", [[]])[0] if semantic_results.get("metadatas") else []
            
            # Combine and deduplicate by document ID
            seen_ids = set()
            combined_docs = []
            
            # Add intent-based results first (higher priority)
            for doc, meta in knowledge_docs:
                doc_id = meta.get("id", "")
                if doc_id not in seen_ids:
                    combined_docs.append((doc, meta))
                    seen_ids.add(doc_id)
            
            # Add semantic results if not already included
            for doc, meta in zip(semantic_docs, semantic_metas):
                doc_id = meta.get("id", "")
                if doc_id not in seen_ids and len(combined_docs) < n_results:
                    combined_docs.append((doc, meta))
                    seen_ids.add(doc_id)
            
            logger.info(f"[ENHANCED_RETRIEVAL] Combined retrieval: {len(knowledge_docs)} intent + {len(semantic_docs)} semantic = {len(combined_docs)} total")
            return combined_docs
            
        except Exception as e:
            logger.error(f"[ENHANCED_RETRIEVAL] Semantic search failed: {e}")
            return knowledge_docs
    
    logger.debug(f"[ENHANCED_RETRIEVAL] Intent retrieval sufficient ({len(knowledge_docs)} docs)")
    return knowledge_docs

# Define lead collection intent(s) for clarity
LEAD_INTENTS = {"interested_lead", "lead_collection", "contact_request"}
FOLLOWUP_KEYWORDS = ["לקבלת מידע נוסף", "סוג העסק", "פרטים נוספים", "האם תרצה לדעת עוד", "Would you like to know more", "business type"]


# === SMART FALLBACK SYSTEM === #

def handle_intent_failure(question, session, collection, system_prompt, client):
    """
    Intelligent fallback when intent detection completely fails.
    Try multiple approaches before giving up.
    """
    logger.info(f"[SMART_FALLBACK] Intent detection failed, trying intelligent alternatives...")
    
    # Step 1: Try general knowledge retrieval (no intent filter)
    try:
        lang = detect_language(question)
        logger.debug(f"[SMART_FALLBACK] Trying general knowledge search...")
        
        # Query ChromaDB without intent filtering
        general_results = collection.query(
            query_texts=[question], 
            n_results=5,
            where={"language": lang}  # Only filter by language
        )
        
        if general_results and general_results['documents'][0]:
            documents = general_results['documents'][0]
            context = "\n---\n".join(documents[:3])  # Use top 3 results
            
            logger.info(f"[SMART_FALLBACK] ✅ Found general knowledge context ({len(context)} chars)")
            
            # Build prompt with general context
            general_prompt = f"""
{system_prompt}

הקשר רלוונטי מהמאגר:
{context}

שאלה של המשתמש: {question}

ענה בצורה ידידותית ומועילה על בסיס המידע שלעיל. אם המידע לא מכסה את השאלה במלואה, תן מה שאתה יכול ותציע לשאול שאלה נוספת או ליצור קשר לפרטים נוספים.
"""
            
            # Call GPT with general context
            response = call_gpt_with_context(general_prompt, session, client, model="gpt-4-turbo")
            if response and not is_truly_vague(response):
                session["fallback_used"] = "general_knowledge"
                session["history"].append({"role": "assistant", "content": response})
                logger.info(f"[SMART_FALLBACK] ✅ Success with general knowledge")
                return response, session
    
    except Exception as e:
        logger.error(f"[SMART_FALLBACK] General knowledge search failed: {e}")
    
    # Step 2: Try semantic similarity across all content
    try:
        logger.debug(f"[SMART_FALLBACK] Trying broad semantic search...")
        
        # Expand search to all documents, ignore intent completely
        broad_results = collection.query(
            query_texts=[question], 
            n_results=10,
            # No where clause = search everything
        )
        
        if broad_results and broad_results['documents'][0]:
            # Filter by language after retrieval
            lang = detect_language(question)
            relevant_docs = []
            
            for i, doc in enumerate(broad_results['documents'][0]):
                metadata = broad_results['metadatas'][0][i] if broad_results['metadatas'] else {}
                doc_lang = metadata.get('language', lang)
                if doc_lang == lang:
                    relevant_docs.append(doc)
                    if len(relevant_docs) >= 3:  # Limit to top 3
                        break
            
            if relevant_docs:
                context = "\n---\n".join(relevant_docs)
                logger.info(f"[SMART_FALLBACK] ✅ Found broad semantic matches ({len(relevant_docs)} docs)")
                
                fallback_prompt = f"""
{system_prompt}

מידע רלוונטי מהמאגר:
{context}

שאלה: {question}

ענה בהתבסס על המידע שלעיל. אם השאלה לא נענית במלואה, הסבר מה כן ידוע ותציע דרכים לקבל מידע נוסף.
"""
                
                response = call_gpt_with_context(fallback_prompt, session, client, model="gpt-4-turbo")
                if response and not is_truly_vague(response):
                    session["fallback_used"] = "broad_semantic"
                    session["history"].append({"role": "assistant", "content": response})
                    logger.info(f"[SMART_FALLBACK] ✅ Success with broad semantic search")
                    return response, session
    
    except Exception as e:
        logger.error(f"[SMART_FALLBACK] Broad semantic search failed: {e}")
    
    # Step 3: Intelligent GPT-only response (no retrieval)
    try:
        logger.debug(f"[SMART_FALLBACK] Trying intelligent GPT-only response...")
        
        gpt_only_prompt = f"""
{system_prompt}

המשתמש שאל: "{question}"

אין לי מידע ספציפי במאגר שעונה על השאלה הזו. תענה בצורה ידידותית וחכמה:
1. הכר בכך שאין לך מידע ספציפי על השאלה
2. תן תשובה כללית ומועילה אם אפשר (בלי להמציא עובדות)
3. הפנה את המשתמש לשאול על נושאים שכן יש לך מידע עליהם (בוטים, שירות לקוחות, אוטומציה)
4. הציע ליצור קשר לפרטים מדויקים יותר

היה חם, אמפתי ומועיל - לא תתנצל יותר מדי או תיראה חסר ישע.
"""
        
        response = call_gpt_with_context(gpt_only_prompt, session, client, model="gpt-3.5-turbo")
        if response:
            session["fallback_used"] = "gpt_only"
            session["history"].append({"role": "assistant", "content": response})
            logger.info(f"[SMART_FALLBACK] ✅ Generated intelligent GPT-only response")
            return response, session
    
    except Exception as e:
        logger.error(f"[SMART_FALLBACK] GPT-only response failed: {e}")
    
    # Step 4: Final graceful fallback
    lang = detect_language(question)
    if lang == "he":
        final_response = """אני מבין שיש לך שאלה חשובה, ואני רוצה לוודא שתקבל תשובה מדויקת. 
        
🤖 אני מתמחה בעזרה עם בוטים חכמים, שירות לקוחות ואוטומציה לעסקים.

איך אוכל לעזור לך בנושאים האלה? או שתרצה שמישהו מהצוות יחזור אליך עם תשובה מפורטת יותר?"""
    else:
        final_response = """I understand you have an important question, and I want to make sure you get an accurate answer.
        
🤖 I specialize in helping with smart chatbots, customer service, and business automation.

How can I help you with these topics? Or would you like someone from our team to get back to you with a more detailed answer?"""
    
    session["fallback_used"] = "final_graceful"
    session["history"].append({"role": "assistant", "content": final_response})
    logger.info(f"[SMART_FALLBACK] ✅ Using final graceful fallback")
    return final_response, session


def call_gpt_with_context(prompt, session, client, model="gpt-4-turbo"):
    """Helper function to call GPT with error handling"""
    try:
        history = session.get("history", [])
        filtered_history = [msg for msg in history[-6:] if isinstance(msg.get("content"), str)]  # Last 6 messages
        
        messages = [{"role": "system", "content": prompt}] + filtered_history
        
        completion = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[GPT_HELPER] Failed to call {model}: {e}")
        return None


def is_truly_vague(answer):
    """More sophisticated vagueness detection that avoids false positives"""
    if not answer or len(answer.strip()) < 15:
        return True
    
    # Only flag as vague if it's REALLY generic
    truly_vague_patterns = [
        "i don't know anything",
        "i have no information",
        "i cannot help you at all",
        "אין לי שום מידע",
        "לא יכול לעזור"
    ]
    
    answer_lower = answer.lower()
    return any(pattern in answer_lower for pattern in truly_vague_patterns)


def get_enhanced_context_with_fallbacks(question, intent_name, lang, collection):
    """
    Multi-layered knowledge retrieval with intelligent fallbacks
    """
    knowledge_docs = []
    
    # Layer 1: Try intent-specific retrieval
    try:
        logger.debug(f"[KNOWLEDGE] Layer 1: Intent-specific retrieval for '{intent_name}'")
        knowledge_docs = get_enhanced_context_retrieval(question, intent_name, lang)
        if knowledge_docs:
            logger.info(f"[KNOWLEDGE] ✅ Layer 1 success: {len(knowledge_docs)} docs")
            return knowledge_docs
    except Exception as e:
        logger.warning(f"[KNOWLEDGE] Layer 1 failed: {e}")
    
    # Layer 2: Try language-filtered retrieval (no intent)
    try:
        logger.debug(f"[KNOWLEDGE] Layer 2: Language-filtered retrieval")
        results = collection.query(
            query_texts=[question],
            n_results=5,
            where={"language": lang}
        )
        if results and results['documents'][0]:
            docs = results['documents'][0]
            metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(docs)
            knowledge_docs = [(doc, meta) for doc, meta in zip(docs, metadatas)]
            logger.info(f"[KNOWLEDGE] ✅ Layer 2 success: {len(knowledge_docs)} docs")
            return knowledge_docs
    except Exception as e:
        logger.warning(f"[KNOWLEDGE] Layer 2 failed: {e}")
    
    # Layer 3: Try broad search (no filters)
    try:
        logger.debug(f"[KNOWLEDGE] Layer 3: Broad search (no filters)")
        results = collection.query(
            query_texts=[question],
            n_results=10
        )
        if results and results['documents'][0]:
            docs = results['documents'][0]
            metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(docs)
            
            # Post-filter by language
            filtered_docs = []
            for doc, meta in zip(docs, metadatas):
                doc_lang = meta.get('language', lang)
                if doc_lang == lang:
                    filtered_docs.append((doc, meta))
                    if len(filtered_docs) >= 3:
                        break
            
            if filtered_docs:
                logger.info(f"[KNOWLEDGE] ✅ Layer 3 success: {len(filtered_docs)} docs")
                return filtered_docs
    except Exception as e:
        logger.warning(f"[KNOWLEDGE] Layer 3 failed: {e}")
    
    logger.warning(f"[KNOWLEDGE] ❌ All retrieval layers failed")
    return []


def handle_question(question, session, collection, system_prompt, client, intents):
    # Performance timing - overall request (must be at the very beginning)
    overall_start_time = time.time()
    
    # CRITICAL: Initialize variables that might be referenced at the end to prevent UnboundLocalError
    answer = None
    intent_name = "unknown"
    
    logger.debug(f"\n{'='*60}")
    logger.info(f"[HANDLE_QUESTION] Starting processing for: '{question}'")
    
    # Initialize session keys if they don't exist
    if "history" not in session:
        session["history"] = []
        logger.debug(f"[SESSION_INIT] Initialized empty history")
    if "greeted" not in session:
        session["greeted"] = False
    if "intro_given" not in session:
        session["intro_given"] = False
    
    logger.debug(f"[SESSION_DEBUG] Session keys: {list(session.keys())}")
    logger.debug(f"[SESSION_DEBUG] Greeted: {session.get('greeted', False)}")
    logger.debug(f"[SESSION_DEBUG] Lead pending: {session.get('interested_lead_pending', False)}")
    logger.debug(f"[SESSION_DEBUG] Lead request count: {session.get('lead_request_count', 0)}")
    logger.debug(f"[SESSION_DEBUG] History length: {len(session.get('history', []))}")
    logger.debug(f"{'='*60}")
    
    # Step 1: Detect greeting context for GPT enrichment (no early returns)
    is_first_greeting = is_greeting(question) and not session.get("intro_given")
    is_repeat_greeting = is_greeting(question) and session.get("intro_given")
    
    if is_first_greeting:
        logger.info(f"[CONTEXT] First-time greeting detected - will enrich GPT context")
        session["intro_given"] = True
    elif is_repeat_greeting:
        logger.debug(f"[CONTEXT] Repeat greeting detected - will enrich GPT context")
    
    # Store greeting context for GPT
    greeting_context = {
        "is_first_greeting": is_first_greeting,
        "is_repeat_greeting": is_repeat_greeting,
        "intro_given": session.get("intro_given", False)
    }
    # Step 2: Initialize and update chat history
    logger.debug(f"[HISTORY] Initializing chat history")
    session.setdefault("history", [])
    session["history"].append({"role": "user", "content": question})
    logger.debug(f"[HISTORY] Added user message. Total history: {len(session['history'])} messages")
    
    def valid_message(msg):
        return (
            isinstance(msg, dict)
            and msg.get("role") in ("user", "assistant")
            and isinstance(msg.get("content"), str)
        )
    filtered_history = [m for m in session["history"] if valid_message(m)]
    logger.debug(f"[HISTORY] Filtered history: {len(filtered_history)} valid messages")
    
    # 1. Lead collection flow with improved exit logic
    # Define conversation history for use in lead collection logic
    history = session.get("history", [])
    has_conversation_history = len(history) > 0
    
    if session.get("interested_lead_pending"):
        logger.info(f"[LEAD_FLOW] Lead collection is pending - checking if user provided details")
        
        # Initialize lead request count if not present
        lead_request_count = session.get("lead_request_count", 0)
        logger.debug(f"[LEAD_FLOW] Current lead request count: {lead_request_count}")
        
        # Check if this is a greeting that should exit lead mode immediately
        if is_greeting(question):
            logger.info(f"[LEAD_FLOW] ✅ Greeting detected in lead mode: '{question}' - resetting lead mode")
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            logger.debug(f"[LEAD_FLOW] Session after greeting reset: interested_lead_pending={session.get('interested_lead_pending')}")
            # Provide intro message since they're starting over
            lang = detect_language(question)
            return get_natural_greeting(lang, question), session
        
        # Check for exit phrases with STRICT word boundary detection to prevent false positives
        exit_phrases = ["היי", "עזוב", "לא עכשיו", "שכח מזה", "לא רוצה", "תודה לא", "די", "סגור"]
        question_lower = question.lower().strip()
        
        def is_standalone_exit_phrase(phrase, text):
            """Check if phrase appears as standalone word, not as substring"""
            import re
            # For Hebrew single words like "די", ensure they're standalone
            if phrase == "די":
                # "די" must be standalone word, not part of other words
                return bool(re.search(r'\bדי\b|\sדי\s|^די\s|^די$|\sדי$', text))
            elif phrase == "היי":
                # "היי" must be standalone, not part of longer words
                return bool(re.search(r'\bהיי\b|\sהיי\s|^היי\s|^היי$|\sהיי$', text))
            else:
                # For multi-word phrases, use exact phrase matching
                return phrase in text and (
                    text == phrase or  # Exact match
                    text.startswith(phrase + " ") or  # Start of text
                    text.endswith(" " + phrase) or   # End of text  
                    " " + phrase + " " in text       # Middle of text
                )
        
        for phrase in exit_phrases:
            if is_standalone_exit_phrase(phrase, question_lower):
                logger.info(f"[LEAD_FLOW] ✅ STANDALONE exit phrase detected: '{phrase}' - resetting lead mode")
                logger.debug(f"[LEAD_FLOW] Full question for context: '{question}'")
                session.pop("interested_lead_pending", None)
                session.pop("lead_request_count", None)
                logger.debug(f"[LEAD_FLOW] Session after reset: interested_lead_pending={session.get('interested_lead_pending')}, lead_request_count={session.get('lead_request_count')}")
                # Detect language and respond appropriately
                lang = detect_language(question)
                if lang == "he":
                    return "בסדר, בואו נמשיך. אפשר לשאול אותי כל דבר! 😊", session
                else:
                    return "No worries, let's continue. Feel free to ask me anything! 😊", session
            else:
                logger.debug(f"[LEAD_FLOW] ❌ Exit phrase '{phrase}' found as substring but NOT standalone - continuing")
        
        if detect_lead_info(question):
            logger.info(f"[LEAD_FLOW] ✅ Lead info detected - sending email and clearing flag")
            send_email_notification(
                subject="🗣️ New Lead Details from Bot",
                message=f"User left details:\n\n{question}"
            )
            session.pop("interested_lead_pending", None)
            session.pop("lead_request_count", None)
            return "Thank you! We received your details and will get back to you soon 😊", session
        else:
            # Increment request count
            lead_request_count += 1
            session["lead_request_count"] = lead_request_count
            logger.debug(f"[LEAD_FLOW] ❌ No lead info detected - request count now: {lead_request_count}")
            
            # After 2 requests, reset and continue normal flow
            if lead_request_count >= 2:
                logger.info(f"[LEAD_FLOW] 🔄 Max requests reached - resetting lead mode and continuing")
                session.pop("interested_lead_pending", None)
                session.pop("lead_request_count", None)
                # Continue to normal processing instead of returning
    else:
                # If this is an ongoing conversation, continue naturally instead of demanding contact details
                if has_conversation_history:
                    logger.info(f"[LEAD_FLOW] 🔄 Lead collection in ongoing conversation - continuing to GPT instead of demanding contact details")
                    # Continue to normal processing instead of returning
                else:
                    return "Please include your name, phone, and email so we can contact you 🙏", session
    else:
        logger.debug(f"[LEAD_FLOW] No lead collection pending - proceeding to intent detection")

    # 2. Conversation context check - only bypass GPT for truly empty input in new conversations
    
    # If there's conversation history, ALWAYS go to GPT - let it handle context
    if has_conversation_history:
        logger.info(f"[CONTEXT_CHECK] ✅ Conversation history exists ({len(history)} messages) - proceeding to GPT with full context")
    else:
        # Only for completely new conversations with truly meaningless input
        if len(question.strip()) < 2:
            logger.info(f"[VAGUE_CHECK] ✅ New conversation with extremely short input: '{question}'. Using minimal response.")
            lang = detect_language(question)
            if lang == "he":
                return "אפשר לעזור במשהו מסוים? 😊", session
            else:
                return "Can I help with something specific? 😊", session
        else:
            logger.info(f"[CONTEXT_CHECK] ✅ New conversation with valid input - proceeding to GPT")

    # Skip use case detection early exits - let GPT handle with full context
    logger.debug(f"[USE_CASE_DETECTION] Use case detection disabled - proceeding to GPT for contextual response")

    # Skip business type early exits - let GPT handle with full context  
    logger.debug(f"[BUSINESS_DETECTION] Business type detection disabled - proceeding to GPT for contextual response")
    
    # Skip follow-up detection early exits - let GPT handle with full context
    logger.debug(f"[FOLLOW_UP] Follow-up detection disabled - proceeding to GPT for contextual response")
    
    # Skip positive engagement early exits - let GPT handle with full context
    logger.debug(f"[ENGAGEMENT] Positive engagement detection disabled - proceeding to GPT for contextual response")
    
    # 2c. CRITICAL SAFEGUARD: Detect high-value questions that shouldn't be missed
    logger.debug(f"\n[SAFEGUARD_CHECK] ======== CHECKING FOR CRITICAL MISSED OPPORTUNITIES ========")
    question_indicators = [
        # Business pain points
        "מקבל הרבה", "מקבל מלא", "טלפונים", "פניות", "הודעות", "לקוחות", "מועמדים",
        "לסנן", "לסרוק", "לחסוך", "זמן", "להפחיד", "להוריד עומס", "אוטומטי",
        "getting flooded", "too many calls", "overwhelmed", "filter", "screen", "automate",
        # Solution seeking
        "יכול לעזור", "איך זה עובד", "מה זה נותן", "האם אפשר", "רוצה לדעת",
        "can this help", "how does it work", "what does it do", "is it possible", "want to know",
        # Business context with problems
        "עסק שלי", "החברה שלי", "אני מנהל", "אני בעלים", "התחום שלי",
        "my business", "my company", "i manage", "i own", "my field"
    ]
    
    question_lower = question.lower()
    indicator_count = sum(1 for indicator in question_indicators if indicator in question_lower)
    
    if indicator_count >= 2 and len(question.strip()) > 20:
        logger.warning(f"[SAFEGUARD_CHECK] ⚠️ HIGH-VALUE QUESTION DETECTED with {indicator_count} indicators but no use case match!")
        logger.warning(f"[SAFEGUARD_CHECK] Question: '{question}'")
        logger.warning(f"[SAFEGUARD_CHECK] This should NOT result in generic fallback - needs manual review")
        
        # Emergency response for high-value missed opportunities
        lang = detect_language(question)
        if lang == "he":
            emergency_response = f"""נשמע שיש לך צורך ספציפי שחשוב לי לטפל בו! 🎯

מהשאלה שלך אני מבינה שאתה מתמודד עם אתגרים בעסק, והבוט יכול בהחלט לעזור. 

בואו נדבר על זה - איזה סוג עסק יש לך ומה הבעיה העיקרית שאתה רוצה לפתור? כך אוכל לתת לך תשובה מדויקת איך הבוט יעזור דווקא לך.

(אם השאלה שלך לא קיבלה מענה מלא, אשמח שתכתב לי עוד פעם בצורה קצת שונה)"""
        else:
            emergency_response = f"""It sounds like you have a specific need that's important for me to address! 🎯

From your question I understand you're dealing with business challenges, and the bot can definitely help.

Let's talk about it - what type of business do you have and what's the main problem you want to solve? This way I can give you a precise answer about how the bot will help you specifically.

(If your question didn't get a full response, I'd appreciate if you could rephrase it slightly)"""
        
        session["history"].append({"role": "user", "content": question})
        session["history"].append({"role": "assistant", "content": emergency_response})
                session["interested_lead_pending"] = True
        session["safeguard_triggered"] = True
        
        return emergency_response, session
    
    logger.debug(f"[BUSINESS_DETECTION] ❌ No business type, engagement, or critical indicators detected - continuing to context detection")

    # 3. Context-aware intent detection - check for follow-up questions first
    logger.debug(f"\n[CONTEXT_DETECTION] ======== CHECKING CONVERSATION CONTEXT ========")
    contextual_intent, context_info = get_conversation_context(question, session)
    
    # Store context_info for later use in prompt building
    session["current_context_info"] = context_info
    
    if contextual_intent:
        logger.info(f"[CONTEXT_DETECTION] ✅ Context-based intent override: {contextual_intent}")
        logger.info(f"[CONTEXT_DETECTION] Topic: {context_info.get('topic', 'unknown')}")
        # Skip normal intent detection and use contextual intent
        final_intent_result = (contextual_intent, {"source": "context_bridge", "confidence": "high"})
        else:
        # 3. Regular intent detection using Chroma embeddings (only for non-small-talk)
        logger.debug(f"\n[INTENT_DETECTION] ======== STARTING INTENT DETECTION ========")
        logger.info(f"[INTENT_DETECTION] Question: '{question}'")
        logger.debug(f"[INTENT_DETECTION] Chroma threshold: {Config.CHROMA_THRESHOLD}")
        logger.debug(f"[INTENT_DETECTION] Fuzzy threshold: {Config.FUZZY_THRESHOLD}")
        
        logger.debug(f"[INTENT_DETECTION] Calling chroma_detect_intent...")
        chroma_start = time.time()
        chroma_intent_result = chroma_detect_intent(question, threshold=Config.CHROMA_THRESHOLD)
        chroma_time = time.time() - chroma_start
        logger.info(f"[PERFORMANCE] 🔍 Chroma intent detection: {chroma_time:.3f}s")
        logger.debug(f"[INTENT_DETECTION] Chroma result: {chroma_intent_result}")
        
        logger.debug(f"[INTENT_DETECTION] Calling fuzzy detect_intent...")
        fuzzy_start = time.time()
        fuzzy_intent_result = detect_intent(question, intents, threshold=Config.FUZZY_THRESHOLD)
        fuzzy_time = time.time() - fuzzy_start
        logger.info(f"[PERFORMANCE] 🔍 Fuzzy intent detection: {fuzzy_time:.3f}s")
        logger.debug(f"[INTENT_DETECTION] Fuzzy result: {fuzzy_intent_result}")

        # Intent Resolution Priority Logic (only if no contextual intent was found)
        logger.debug(f"[INTENT_RESOLUTION] ======== RESOLVING INTENT CONFLICTS ========")
        final_intent_result = None
        
        # Priority 1: If fuzzy found a strong match (not "faq"), use it
        if fuzzy_intent_result and fuzzy_intent_result.get('intent') != 'faq':
            logger.info(f"[INTENT_RESOLUTION] 🎯 Priority 1: Strong fuzzy match found: {fuzzy_intent_result['intent']}")
            intent_name = fuzzy_intent_result['intent']
            intent_meta = {'intent': intent_name, 'source': 'fuzzy', 'confidence': fuzzy_intent_result.get('confidence', 0)}
            final_intent_result = (intent_name, intent_meta)
        
        # Priority 2: If Chroma found a good match, use it (unless fuzzy already decided)
        elif chroma_intent_result:
            logger.info(f"[INTENT_RESOLUTION] 🎯 Priority 2: Chroma match found: {chroma_intent_result[0]}")
            final_intent_result = chroma_intent_result
        
        # Priority 3: Fallback to fuzzy if it found anything (including "faq")
        elif fuzzy_intent_result:
            logger.info(f"[INTENT_RESOLUTION] 🎯 Priority 3: Fallback to fuzzy result: {fuzzy_intent_result['intent']}")
            intent_name = fuzzy_intent_result['intent']
            intent_meta = {'intent': intent_name, 'source': 'fuzzy_fallback', 'confidence': fuzzy_intent_result.get('confidence', 0)}
            final_intent_result = (intent_name, intent_meta)
        
        # Priority 4: Hybrid - Try Chroma with relaxed threshold
        else:
            logger.debug(f"[INTENT_RESOLUTION] 🎯 Priority 4: Trying hybrid Chroma approach with threshold 1.8...")
            hybrid_start = time.time()
            hybrid_result = chroma_detect_intent(question, threshold=1.8)
            hybrid_time = time.time() - hybrid_start
            logger.info(f"[PERFORMANCE] 🔍 Hybrid Chroma detection: {hybrid_time:.3f}s")
            if hybrid_result:
                chroma_intent_name, chroma_intent_meta = hybrid_result
                logger.info(f"[INTENT_RESOLUTION] ✅ Hybrid: Accepting intent '{chroma_intent_name}' at relaxed threshold")
                final_intent_result = hybrid_result
            else:
                logger.debug(f"[INTENT_RESOLUTION] ❌ Hybrid: Even relaxed threshold failed")
                final_intent_result = None
    
    # Update the main variable for the rest of the function
    chroma_intent_result = final_intent_result
    
    if not chroma_intent_result:
        logger.info(f"[INTENT_FINAL] ❌ No valid intent detected (distance > {Config.CHROMA_THRESHOLD} or no match). Activating smart fallback system.")
        return handle_intent_failure(question, session, collection, system_prompt, client)
    
    logger.info(f"[INTENT_FINAL] ✅ Final intent selected: {chroma_intent_result}")
    intent_name, intent_meta = chroma_intent_result
    logger.debug(f"\n[KNOWLEDGE_RETRIEVAL] ======== STARTING KNOWLEDGE RETRIEVAL ========")
    logger.info(f"[KNOWLEDGE_RETRIEVAL] Intent: '{intent_name}'")
    
    # 3. Enhanced knowledge retrieval with layered fallbacks
    logger.debug(f"[KNOWLEDGE_RETRIEVAL] Calling enhanced context retrieval with fallbacks...")
    knowledge_start = time.time()
    lang = detect_language(question)
    knowledge_docs = get_enhanced_context_with_fallbacks(question, intent_name, lang, collection)
    knowledge_time = time.time() - knowledge_start
    logger.info(f"[PERFORMANCE] 🔍 Enhanced knowledge retrieval with fallbacks: {knowledge_time:.3f}s")
    logger.info(f"[KNOWLEDGE_RETRIEVAL] ✅ Retrieved {len(knowledge_docs)} knowledge documents")
    
    # 3a. Retrieve few-shot examples for this intent
    logger.debug(f"[EXAMPLES] Calling get_examples_by_intent...")
    try:
        examples = get_examples_by_intent(intent_name, n_examples=3)
        logger.debug(f"[EXAMPLES] ✅ Retrieved {len(examples)} examples")
    except Exception as e:
        logger.error(f"[EXAMPLES] ❌ Failed to get examples: {e}")
        examples = []
    
    examples_block = ""
    if examples:
        examples_block = (
            "Here are some examples of how to answer this kind of question (do not copy them verbatim, but use their tone and structure):\n"
            + "\n---\n".join(examples) + "\n---\n"
        )
        logger.debug(f"[EXAMPLES] ✅ Built examples block ({len(examples_block)} chars)")
    else:
        logger.debug(f"[EXAMPLES] ❌ No examples available")
    
    if knowledge_docs:
        logger.debug(f"\n[CONTEXT_BUILDING] ======== BUILDING GPT CONTEXT ========")
        context = "\n---\n".join(doc for doc, meta in knowledge_docs if doc)
        logger.info(f"[CONTEXT_BUILDING] Built context from {len(knowledge_docs)} docs ({len(context)} chars)")
        
        # 4. Build enriched context from all detection signals
        enriched_signals = build_enriched_context(question, session, greeting_context)
        if enriched_signals:
            logger.info(f"[CONTEXT_ENRICHMENT] Added context signals for GPT")
            logger.debug(f"[CONTEXT_ENRICHMENT] Signals: {enriched_signals}")
        
        # 4a. Build GPT prompt with examples, context, and conversational enhancements
        conversational_enhancement = get_conversational_enhancement(question, intent_name)
        logger.debug(f"[CONVERSATIONAL] Enhancement: {conversational_enhancement[:100]}...")
        
        # 4a. Add contextual bridge if this is a follow-up question
        context_info = session.get("current_context_info")
        if context_info:
            logger.info(f"[CONTEXT_BRIDGE] Adding contextual bridge for topic: {context_info.get('topic')}")
            enhanced_context = build_contextual_prompt(question, context_info, context)
        else:
            enhanced_context = context
            
        # Build base prompt with enriched context signals
        base_prompt = (
            f"{system_prompt}\n\n"
            f"הקשר רלוונטי מתוך מסמכי העסק:\n{enhanced_context}\n\n"
            f"{conversational_enhancement}\n\n"
            f"{enriched_signals}\n\n" if enriched_signals else ""
            f"שאלה של המשתמש:\n{question}\n\n"
            f"ענה בצורה טבעית וידידותית בהתבסס על המידע שלעיל. התאמי את התשובה לשאלה הספציפית, הוסיפי ערך אישי, וסיימי עם שאלת המשך רלוונטית כדי להמשיך את השיחה באופן טבעי."
        )
        
        # Check if we can fit examples without exceeding token limit
        base_messages = [{"role": "system", "content": base_prompt}] + filtered_history
        base_tokens = count_tokens(base_messages)
        
        if base_tokens + count_tokens([{"role": "system", "content": examples_block}]) < Config.MAX_PROMPT_TOKENS:
            # Build context prompt with examples and enriched signals
            enriched_section = f"{enriched_signals}\n\n" if enriched_signals else ""
            context_prompt = (
                f"{system_prompt}\n\n"
                f"{examples_block}"
                f"הקשר רלוונטי מתוך מסמכי העסק:\n{enhanced_context}\n\n"
                f"{conversational_enhancement}\n\n"
                f"{enriched_section}"
                f"שאלה של המשתמש:\n{question}\n\n"
                f"ענה בצורה טבעית וידידותית בהתבסס על המידע שלעיל. התאמי את התשובה לשאלה הספציפית, הוסיפי ערך אישי, וסיימי עם שאלת המשך רלוונטית כדי להמשיך את השיחה באופן טבעי."
            )
            logger.debug(f"[TOKEN_MANAGEMENT] ✅ Including examples (total estimated: {base_tokens + len(examples_block)//4} tokens)")
        else:
            context_prompt = base_prompt
            logger.warning(f"[TOKEN_MANAGEMENT] ⚠️ Skipping examples to stay under {Config.MAX_PROMPT_TOKENS} tokens (base: {base_tokens})")
        
        # Final token check
        final_messages = [{"role": "system", "content": context_prompt}] + filtered_history
        final_tokens = count_tokens(final_messages)
        
        if final_tokens > Config.MAX_PROMPT_TOKENS:
            # Truncate context if still too long
            logger.warning(f"[TOKEN_MANAGEMENT] ⚠️ Prompt still too long ({final_tokens} tokens), truncating context...")
            max_context_chars = len(context) - ((final_tokens - Config.MAX_PROMPT_TOKENS) * 4)  # Rough estimate
            truncated_context = context[:max(max_context_chars, 500)] + "..."
            # Apply contextual enhancement to truncated context too
            if context_info:
                enhanced_truncated_context = build_contextual_prompt(question, context_info, truncated_context)
            else:
                enhanced_truncated_context = truncated_context
                
            context_prompt = (
                f"{system_prompt}\n\n"
                f"הקשר רלוונטי מתוך מסמכי העסק:\n{enhanced_truncated_context}\n\n"
                f"{conversational_enhancement}\n\n"
                f"שאלה של המשתמש:\n{question}\n\n"
                f"ענה בצורה טבעית וידידותית בהתבסס על המידע שלעיל. התאמי את התשובה לשאלה הספציפית, הוסיפי ערך אישי, וסיימי עם שאלת המשך רלוונטית כדי להמשיך את השיחה באופן טבעי."
            )
            logger.info(f"[TOKEN_MANAGEMENT] ✅ Context truncated to stay within limits")
        logger.info(f"[CONTEXT_BUILDING] ✅ Final prompt built ({len(context_prompt)} chars)")
        logger.debug(f"[CONTEXT_BUILDING] System prompt: {len(system_prompt)} chars")
        logger.debug(f"[CONTEXT_BUILDING] Examples: {len(examples_block)} chars")
        logger.debug(f"[CONTEXT_BUILDING] Context: {len(context)} chars")
        logger.debug(f"[CONTEXT_BUILDING] History messages: {len(filtered_history)}")
        
        logger.debug(f"\n[GPT_CALL] ======== CALLING GPT-4 ========")
        try:
            start_time = time.time()
            messages = [{"role": "system", "content": context_prompt}] + filtered_history
            
            # Log detailed prompt info
            logger.info(f"[GPT_CALL] 📝 Prompt built successfully")
            logger.debug(f"[GPT_CALL] 📊 Total messages: {len(messages)}")
            logger.debug(f"[GPT_CALL] 📄 System prompt length: {len(context_prompt)} chars")
            logger.debug(f"[GPT_CALL] 💬 History messages: {len(filtered_history)}")
            
            # Count and log tokens
            token_count = log_token_usage(messages, model="gpt-4-turbo")
            
            logger.info(f"[GPT_CALL] 📤 Sending to GPT-4 Turbo...")
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages
            )
            end_time = time.time()
            
            answer = completion.choices[0].message.content.strip()
            
            # Log successful response
            logger.info(f"[GPT_CALL] ✅ GPT-4 Turbo responded successfully!")
            logger.info(f"[GPT_CALL] ⏱️  Response time: {end_time - start_time:.2f}s")
            logger.debug(f"[GPT_CALL] 📏 Answer length: {len(answer)} chars")
            logger.debug(f"[GPT_CALL] 📝 Answer preview: {answer[:100]}...")
            
            # Log token usage stats
            if hasattr(completion, 'usage') and completion.usage:
                logger.info(f"[GPT_CALL] 🎯 Actual tokens used: {completion.usage.total_tokens}")
                logger.debug(f"[GPT_CALL] 📥 Prompt tokens: {completion.usage.prompt_tokens}")
                logger.debug(f"[GPT_CALL] 📤 Completion tokens: {completion.usage.completion_tokens}")
            
        except Exception as e:
            logger.error(f"[GPT_CALL] ❌ GPT-4 error occurred!")
            logger.error(f"[GPT_CALL] ❌ Error type: {type(e).__name__}")
            logger.error(f"[GPT_CALL] ❌ Error message: {str(e)}")
            logger.error(f"[GPT_CALL] ❌ Token count was: {token_count if 'token_count' in locals() else 'Unknown'}")
            # Don't activate lead collection for greetings/small talk even if GPT fails
            if not is_greeting(question) and not is_small_talk(question):
                session["interested_lead_pending"] = True
                return "Sorry, I'm having trouble answering right now. Please leave your name, phone, and email and someone will get back to you.", session
            else:
                logger.debug(f"[GPT_CALL] GPT error for greeting/small talk - providing intro response instead of lead collection")
                # Detect language and respond appropriately
                lang = detect_language(question)
                return get_natural_greeting(lang, question), session
        
        logger.debug(f"[ANSWER_VALIDATION] Checking if answer is vague...")
        if is_vague_gpt_answer(answer):
            logger.info(f"[ANSWER_VALIDATION] ❌ GPT-4 answer is vague, but letting GPT handle with enriched context instead of hardcoded fallbacks.")
            
            # Collect additional context signals but don't return early - let GPT handle everything
            specific_use_case = detect_specific_use_case(question)
            if specific_use_case:
                logger.info(f"[CONTEXT] ✅ Specific use case detected: '{specific_use_case}' - session updated for future context")
                session["specific_use_case"] = specific_use_case
                session["business_info"] = question
                session["conversion_opportunity"] = True
            
            follow_up_topic, business_context = detect_follow_up_context(question, session)
            if follow_up_topic:
                logger.info(f"[CONTEXT] ✅ Follow-up context detected: '{follow_up_topic}' - session updated for future context")
                session["follow_up_context"] = follow_up_topic
            
            if detect_positive_engagement(question):
                logger.info(f"[CONTEXT] ✅ Positive engagement detected - session updated for future context")
                session["positive_engagement"] = True
            
            # For truly vague cases with conversation history, continue to GPT success path
            # Only activate lead collection for new conversations with truly meaningless input
            history = session.get("history", [])
            if len(history) > 0:  # Has conversation history
                logger.info(f"[ANSWER_VALIDATION] ✅ Vague answer but has conversation history - treating as successful GPT response")
                # Continue to success path - don't activate lead collection
            elif is_greeting(question) or is_small_talk(question):
                logger.info(f"[ANSWER_VALIDATION] ✅ Vague answer for greeting/small talk in new conversation - treating as successful GPT response")
                # Continue to success path for greetings
            else:
                logger.info(f"[ANSWER_VALIDATION] ❌ Vague answer in new conversation with no context - activating lead collection")
                session["interested_lead_pending"] = True
                return "Sorry, I couldn't find a good answer. Please leave your name, phone, and email and someone will get back to you.", session
        
        logger.info(f"[ANSWER_VALIDATION] ✅ Answer is good - updating session and returning")
        
        # SAFETY CHECK: Ensure answer is not None before using it
        if answer is not None:
            session["history"].append({"role": "assistant", "content": answer})
        else:
            logger.error("[CRITICAL] Answer is None - this should not happen in success path!")
            answer = "Sorry, I encountered an error processing your request."
            session["history"].append({"role": "assistant", "content": answer})
        
        # Performance summary
        total_time = time.time() - overall_start_time
        logger.info(f"[PERFORMANCE] 🏁 TOTAL REQUEST TIME: {total_time:.3f}s")
        if total_time > 3.0:
            logger.warning(f"[PERFORMANCE] ⚠️  SLOW REQUEST: {total_time:.3f}s > 3.0s threshold")
        
        logger.info(f"[FINAL_SUCCESS] Returning successful answer to user")
        return answer, session
    else:
        logger.warning(f"[KNOWLEDGE_RETRIEVAL] ❌ No knowledge docs found for intent '{intent_name}'. Activating lead collection.")
        # Don't activate lead collection for greetings/small talk even if no knowledge is found
        if not is_greeting(question) and not is_small_talk(question):
            session["interested_lead_pending"] = True
            logger.info(f"[FINAL_FALLBACK] No knowledge available - requesting lead details")
            return "Sorry, I couldn't find a good answer. Please leave your name, phone, and email and someone will get back to you.", session
        else:
            logger.debug(f"[FINAL_FALLBACK] No knowledge for greeting/small talk - providing intro response instead of lead collection")
            # Detect language and respond appropriately
            lang = detect_language(question)
            return get_natural_greeting(lang, question), session



# === Serve React Frontend === #
@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    logger.info(f"🟢 User question (API): {question}")
    answer, updated_session = handle_question(question, dict(session), knowledge_collection, system_prompt, client, intents)
    
    # Update session properly
    for key, value in updated_session.items():
        session[key] = value
    session.modified = True
    
    return jsonify({
        "answer": answer,
        "success": True
    })

@app.route("/api/clear", methods=["POST"])
def api_clear():
    session.pop("history", None)
    session.pop("interested_lead_pending", None)
    session.pop("greeted", None)
    session.modified = True
    return jsonify({"success": True})

@app.route("/clear", methods=["POST"])
def clear_chat():
    session.pop("history", None)
    session.pop("interested_lead_pending", None)
    session.pop("greeted", None)
    session.modified = True
    return redirect(url_for("index"))

@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json()
    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email")
    if not (full_name and phone and email):
        return jsonify({"success": False, "message": "Missing required fields."}), 400
    subject = "📝 ליד חדש מהאתר (טופס צור קשר)"
    body = f"שם מלא: {full_name}\nטלפון: {phone}\nאימייל: {email}"
    success = send_email_notification(subject, body)
    if success:
        return jsonify({"success": True, "message": "Contact details sent successfully!"}), 200
    else:
        return jsonify({"success": False, "message": "Failed to send contact details."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
