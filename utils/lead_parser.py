import re
import logging

logger = logging.getLogger(__name__)

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
        bool(re.search(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b', text)) or  # English full name pattern
        bool(re.search(r'\b[א-ת]{2,}\s+[א-ת]{2,}\b', text)) or  # Hebrew name pattern
        any(word in text_lower for word in ["שם מלא", "שמי הוא", "השם שלי"])
    )
    
    logger.debug(f"[LEAD_DETECTION] Text: '{text}' | Email: {has_email} | Phone: {has_phone} | Name: {has_name}")
    
    # Require ALL THREE components for complete lead info
    return has_email and has_phone and has_name

def extract_lead_details(text):
    """Extract specific lead details from user text"""
    details = {
        'name': None,
        'phone': None,
        'email': None
    }
    
    # Extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    if email_match:
        details['email'] = email_match.group()
    
    # Extract phone (Israeli format)
    phone_pattern = r'\b0\d{1,2}[-\s]?\d{7}\b'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        details['phone'] = phone_match.group()
    
    # Extract name (basic pattern)
    name_patterns = [
        r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b',  # English names
        r'\b[א-ת]{2,}\s+[א-ת]{2,}\b'  # Hebrew names
    ]
    
    for pattern in name_patterns:
        name_match = re.search(pattern, text)
        if name_match:
            details['name'] = name_match.group()
            break
    
    return details

def format_lead_notification(lead_text):
    """Format lead information for email notification"""
    details = extract_lead_details(lead_text)
    
    formatted_message = f"""
🆕 New Lead from Atarize Chatbot

📋 Lead Details:
👤 Name: {details.get('name', 'Not provided')}
📞 Phone: {details.get('phone', 'Not provided')}
📧 Email: {details.get('email', 'Not provided')}

💬 Original Message:
{lead_text}

⏰ Timestamp: {logger.handlers[0].formatter.formatTime(logger.makeRecord('', 0, '', 0, '', (), None)) if logger.handlers else 'Unknown'}

---
This lead was automatically detected by the Atarize chatbot.
Please follow up promptly!
"""
    
    return formatted_message

def parse_lead_info(text):
    """Extract lead information from text"""
    # This is a placeholder - you can enhance this to extract actual values
    return {
        'has_lead_info': detect_lead_info(text),
        'text': text
    }