import tiktoken
import logging
from config.settings import Config

logger = logging.getLogger(__name__)

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