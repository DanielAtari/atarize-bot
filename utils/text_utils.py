import re

def detect_language(text):
    """Detect if text is Hebrew or English"""
    return "en" if re.search(r'[a-zA-Z]', text) else "he"

def is_greeting(text):
    """Check if text is a greeting"""
    greetings_he = ["שלום", "היי", "הי", "אהלן", "בוקר טוב", "ערב טוב", "שלום לך"]
    greetings_en = ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"]
    
    text_lower = text.lower().strip()
    
    # Check Hebrew greetings
    for greeting in greetings_he:
        if greeting in text_lower:
            return True
    
    # Check English greetings  
    for greeting in greetings_en:
        if greeting in text_lower:
            return True
            
    return False

def is_small_talk(text):
    """Check if text is small talk"""
    small_talk_patterns = [
        "תודה", "thanks", "thank you", "יפה", "נחמד", "כן", "yes", "לא", "no", 
        "אוקיי", "okay", "ok", "בסדר", "fine", "great", "נהדר"
    ]
    
    text_lower = text.lower().strip()
    
    # Very short responses are likely small talk
    if len(text.strip()) <= 2:
        return True
        
    return any(pattern in text_lower for pattern in small_talk_patterns)

def get_natural_greeting(language, greeting_text=""):
    """Generate a natural greeting response"""
    if language == "he":
        # Hebrew greetings
        base_greeting = "היי! תודה על הפנייה 😊"
        
        if "בוקר" in greeting_text.lower():
            base_greeting = "בוקר טוב! איך אפשר לעזור? 😊"
        elif "ערב" in greeting_text.lower():
            base_greeting = "ערב טוב! איך אפשר לעזור? 😊"
        else:
            base_greeting = "שלום! איך אפשר לעזור? 😊"
            
        intro = " אני עטרה מ־Atarize - אשמח לעזור לך עם כל מה שקשור לבוטים חכמים לעסקים. מה מעניין אותך לדעת?"
        return base_greeting + intro
    else:
        # English greetings
        base_greeting = "Hello! Thank you for reaching out 😊"
        
        if "morning" in greeting_text.lower():
            base_greeting = "Good morning! How can I help? 😊"
        elif "evening" in greeting_text.lower():
            base_greeting = "Good evening! How can I help? 😊"
        else:
            base_greeting = "Hello! How can I help? 😊"
            
        intro = " I'm Atara from Atarize - I'd be happy to help you with everything related to smart business bots. What would you like to know?"
        return base_greeting + intro