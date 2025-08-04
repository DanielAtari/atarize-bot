import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Thresholds
    FUZZY_THRESHOLD = 70
    CHROMA_THRESHOLD = 1.4  # Relaxed threshold to catch more valid intents
    MIN_ANSWER_LENGTH = 10
    
    # Token limits for different models
    GPT4_TOKEN_LIMIT = 8192
    GPT4_TURBO_TOKEN_LIMIT = 128000
    GPT35_TOKEN_LIMIT = 4096
    MAX_PROMPT_TOKENS = 100000  # Much higher limit for GPT-4 Turbo
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
    DATA_DIR = os.path.join(BASE_DIR, "data")
    
    # Environment variables
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    EMAIL_TARGET = os.getenv("EMAIL_TARGET")
    
    # Flask config
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)