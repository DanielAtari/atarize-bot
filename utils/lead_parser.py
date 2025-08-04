import re
import logging

logger = logging.getLogger(__name__)

def extract_lead_details(text):
    """Extract specific lead details from user text"""
    details = {
        'name': None,
        'phone': None,
        'email': None,
        'raw_text': text
    }
    
    # Extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    if email_match:
        details['email'] = email_match.group()
    
    # Extract phone number
    phone_patterns = [
        r'\b0\d{1,2}[-\s]?\d{7,8}\b',     # Israeli format
        r'\b05\d[-\s]?\d{7}\b',           # Mobile format
        r'\b\+972[-\s]?\d{8,9}\b',        # International format
    ]
    
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            details['phone'] = phone_match.group()
            break
    
    # Extract name (careful patterns, focused on specific indicator contexts)
    name_patterns = [
        r'שמי\s+([א-ת]{2,}(?:\s+[א-ת]{2,})?)',    # "שמי דניאל" or "שמי דניאל כהן"
        r'השם שלי\s+([א-ת]{2,}(?:\s+[א-ת]{2,})?)', # "השם שלי דניאל כהן"
        r'אני\s+([א-ת]{2,}(?:\s+[א-ת]{2,})?)',     # "אני דניאל כהן"
        r'name.*?([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)',  # English name (max 2 words)
        r'([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})',     # Full English name standalone (John Smith)
        # NOTE: Removed problematic Hebrew standalone pattern that captured indicator words
    ]
    
    for pattern in name_patterns:
        name_match = re.search(pattern, text)
        if name_match:
            potential_name = name_match.group(1).strip()
            # Validate extracted name: no phone/email keywords, reasonable length
            excluded_keywords = ["נייד", "טלפון", "פלאפון", "phone", "mobile", "מייל", "אימייל", "email"]
            if (len(potential_name) >= 2 and 
                not any(keyword in potential_name.lower() for keyword in excluded_keywords) and
                len(potential_name.split()) <= 3):  # Max 3 words for a name
                details['name'] = potential_name
                break
    
    # If no structured name found, look for name indicators (improved fallback)
    if not details['name']:
        text_lower = text.lower()
        if any(word in text_lower for word in ["שמי", "name", "קוראים לי"]):
            # Extract potential name after indicators
            words = text.split()
            for i, word in enumerate(words):
                if word.lower() in ["שמי", "name", "קוראים"]:
                    if i + 1 < len(words):
                        # Take only the next word (first name) to avoid phone keywords
                        potential_name = words[i + 1]
                        # Validate: no phone/email keywords, reasonable length
                        excluded_keywords = ["נייד", "טלפון", "פלאפון", "phone", "mobile", "מייל", "אימייל", "email"]
                        if (len(potential_name) >= 2 and 
                            not any(keyword in potential_name.lower() for keyword in excluded_keywords) and
                            re.match(r'^[א-תA-Za-z]+$', potential_name)):  # Only letters
                            details['name'] = potential_name
                            break
    
    logger.debug(f"[LEAD_PARSER] Extracted details: {details}")
    return details

def format_lead_notification(text):
    """Create a formatted email notification for lead details"""
    details = extract_lead_details(text)
    
    # Create formatted message
    message_parts = ["🆕 NEW LEAD FROM CHATBOT", "=" * 40, ""]
    
    if details['name']:
        message_parts.append(f"👤 NAME: {details['name']}")
    
    if details['phone']:
        message_parts.append(f"📞 PHONE: {details['phone']}")
    
    if details['email']:
        message_parts.append(f"📧 EMAIL: {details['email']}")
    
    message_parts.extend(["", "📝 FULL MESSAGE:", "-" * 20, details['raw_text']])
    
    return "\n".join(message_parts)