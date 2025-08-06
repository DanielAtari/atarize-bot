import re
import logging

logger = logging.getLogger(__name__)

def detect_language(text):
    """Detect if text is Hebrew or English"""
    hebrew_chars = len(re.findall(r'[א-ת]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if hebrew_chars > english_chars:
        return "he"
    else:
        return "en"

def is_greeting(text):
    """Detect if text is a greeting"""
    greetings_he = ["היי", "שלום", "בוקר טוב", "ערב טוב", "מה שלומך", "מה נשמע"]
    greetings_en = ["hi", "hello", "hey", "good morning", "good evening", "how are you"]
    
    text_lower = text.lower().strip()
    return any(greeting in text_lower for greeting in greetings_he + greetings_en)

def get_natural_greeting(language, greeting_text=""):
    """Generate a natural greeting response"""
    if language == "he":
        return "היי! איך אפשר לעזור? 😊 אני Atara מ-Atarize, ואני כאן כדי לעזור לך עם כל מה שקשור לצ'אטבוטים חכמים לעסק שלך."
    else:
        return "Hi! How can I help? 😊 I'm Atara from Atarize, and I'm here to help you with everything related to smart chatbots for your business."

def is_small_talk(text):
    """Detect if text is small talk"""
    small_talk_patterns = [
        "מה שלומך", "איך אתה", "מה נשמע", "איך הולך",
        "how are you", "how's it going", "what's up", "how do you do"
    ]
    
    text_lower = text.lower().strip()
    return any(pattern in text_lower for pattern in small_talk_patterns)

def should_continue_conversation(question, session):
    """Determine if conversation should continue based on context"""
    # Check if user wants to continue
    continue_indicators = [
        "כן", "בטח", "אפשר", "למה לא", "בואו נמשיך", "אני רוצה",
        "yes", "sure", "okay", "why not", "let's continue", "i want"
    ]
    
    question_lower = question.lower()
    wants_to_continue = any(indicator in question_lower for indicator in continue_indicators)
    
    # Check conversation history length
    history_length = len(session.get("history", []))
    
    # Continue if user explicitly wants to or if conversation is still young
    return wants_to_continue or history_length < 10

def get_conversation_context(question, session):
    """Build conversation context from session history"""
    history = session.get("history", [])
    
    if not history:
        return "New conversation"
    
    # Get last few messages for context
    recent_messages = history[-6:]  # Last 6 messages (3 exchanges)
    
    context_parts = []
    for msg in recent_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            context_parts.append(f"{role}: {content[:100]}...")
    
    return "\n".join(context_parts)

def build_enriched_context(question, session, greeting_context=None):
    """Build enriched context for AI processing"""
    base_context = get_conversation_context(question, session)
    
    # Add language detection
    lang = detect_language(question)
    
    # Add business context if available
    business_context = ""
    if session.get("business_type"):
        business_context = f"Business type: {session['business_type']}"
    
    # Add use case context if available
    use_case_context = ""
    if session.get("use_case"):
        use_case_context = f"Use case: {session['use_case']}"
    
    # Combine all context
    enriched_context = f"""
Language: {lang}
{base_context}
{business_context}
{use_case_context}
{greeting_context or ""}
"""
    
    return enriched_context.strip()

def build_contextual_prompt(question, context_info, base_context):
    """Build a contextual prompt for AI"""
    lang = detect_language(question)
    
    if lang == "he":
        language_instruction = "ענה בעברית"
    else:
        language_instruction = "Answer in English"
    
    prompt = f"""
{base_context}

Context Information:
{context_info}

Current Question: {question}

Instructions:
- {language_instruction}
- Be helpful and informative
- If you don't know something, suggest connecting with the team
- Keep responses conversational and engaging
"""
    
    return prompt.strip()

def get_conversational_enhancement(question, intent_name):
    """Get conversational enhancements based on intent"""
    enhancements = {
        "pricing": {
            "he": "אני אשמח לספר לך על המחירים שלנו. יש לנו כמה חבילות שונות שמתאימות לעסקים שונים.",
            "en": "I'd be happy to tell you about our pricing. We have several different packages that suit different businesses."
        },
        "about_atarize": {
            "he": "Atarize היא פלטפורמה מתקדמת לבניית צ'אטבוטים חכמים. יש לך שאלות ספציפיות?",
            "en": "Atarize is an advanced platform for building smart chatbots. Do you have any specific questions?"
        },
        "work_process": {
            "he": "התהליך שלנו פשוט ויעיל. אשמח להסביר לך איך זה עובד בדיוק.",
            "en": "Our process is simple and efficient. I'd be happy to explain exactly how it works."
        }
    }
    
    lang = detect_language(question)
    return enhancements.get(intent_name, {}).get(lang, "")