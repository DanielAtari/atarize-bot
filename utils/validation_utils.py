import re
import logging

logger = logging.getLogger(__name__)

def detect_lead_info(text):
    """Enhanced lead detection - requires name, phone, and email"""
    text_lower = text.lower().strip()
    
    # Email detection (strict validation - must find actual email address)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Only accept if we find an actual valid email address
    email_matches = re.findall(email_pattern, text)
    has_email = len(email_matches) > 0
    
    # Additional validation: check if found emails are reasonable
    if has_email:
        for email in email_matches:
            # Basic validation: not too short, has proper format
            if len(email) < 5 or email.count('@') != 1 or email.count('.') < 1:
                has_email = False
                break
    
    # Phone detection (Israeli and international patterns)
    phone_patterns = [
        r'\b0\d{1,2}[-\s]?\d{7}\b',  # Israeli phone format
        r'\b05\d[-\s]?\d{7}\b',      # Israeli mobile format
        r'\b\+972[-\s]?\d{8,9}\b',   # International Israel format
    ]
    phone_keywords = ["טלפון", "נייד", "phone", "פלאפון", "מספר", "050", "052", "053", "054", "055", "056", "057", "058", "059"]
    
    has_phone = (
        any(re.search(pattern, text) for pattern in phone_patterns) or
        any(keyword in text_lower for keyword in phone_keywords)
    )
    
    # Name detection (strict - must find actual name, not just keywords)
    name_patterns = [
        r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b',  # English full name (John Smith)
        r'\b[א-ת]{2,}\s+[א-ת]{2,}\b',             # Hebrew full name (דניאל כהן)
        r'שמי\s+([א-ת]{2,}(?:\s+[א-ת]{2,})?)',    # "שמי דניאל" or "שמי דניאל כהן"
        r'השם שלי\s+([א-ת]{2,}(?:\s+[א-ת]{2,})?)', # "השם שלי דניאל"
        r'(?:name.*?|my name.*?)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)',  # "name is John Smith"
    ]
    
    has_name = False
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            # For patterns with groups, check if the captured name is reasonable
            if match.groups():
                potential_name = match.group(1).strip()
                # Name should be at least 2 chars and not contain numbers/symbols
                if len(potential_name) >= 2 and re.match(r'^[א-תA-Za-z\s]+$', potential_name):
                    has_name = True
                    break
            else:
                # For full name patterns without groups
                has_name = True
                break
    
    logger.debug(f"[LEAD_DETECTION] Text: '{text}' | Email: {has_email} | Phone: {has_phone} | Name: {has_name}")
    
    # Require ALL THREE components for complete lead info
    return has_email and has_phone and has_name

def is_vague_gpt_answer(answer):
    """Check if a GPT answer is too vague or generic"""
    if not answer or not answer.strip():
        return True
    
    answer_lower = answer.lower()
    
    # Truly vague phrases that indicate the answer lacks substance
    truly_vague_phrases = [
        "תלוי במה שאתה מחפש",
        "זה יכול להיות",
        "זה תלוי",
        "אני יכול לעזור",
        "בואו נדבר על זה",
        "אשמח לעזור",
        "depends on what you're looking for",
        "it depends",
        "i can help",
        "let's talk about"
    ]
    
    # Count vague phrases
    vague_count = sum(1 for phrase in truly_vague_phrases if phrase in answer_lower)
    
    # Only consider vague if multiple vague phrases or very short
    return vague_count >= 2 or (vague_count >= 1 and len(answer) < 30)

def is_truly_vague(answer):
    """Enhanced vagueness detection for fallback scenarios"""
    if not answer or len(answer.strip()) < 10:
        return True
    
    answer_lower = answer.lower()
    
    vague_indicators = [
        "לא יכול לעזור",
        "לא ברור לי",
        "צריך יותר מידע",
        "תלוי במה שאתה מחפש",
        "i can't help",
        "not clear",
        "need more information",
        "depends on what",
        "לא מצאתי מידע",
        "אין לי מידע"
    ]
    
    return any(indicator in answer_lower for indicator in vague_indicators)