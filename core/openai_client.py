from openai import OpenAI
from config.settings import Config

class OpenAIClientManager:
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def get_client(self):
        """Get the OpenAI client"""
        return self.client