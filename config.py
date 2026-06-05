import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Piyush Joshi AI Representative"
    
    PROVIDER_OVERRIDE: str = os.getenv("LLM_PROVIDER", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_BEDROCK_MODEL: str = os.getenv("AWS_BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")

    @property
    def LLM_PROVIDER(self) -> str:
        if self.PROVIDER_OVERRIDE:
            return self.PROVIDER_OVERRIDE.lower()
        if self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY:
            return "bedrock"
        elif self.OPENAI_API_KEY:
            return "openai"
        elif self.GEMINI_API_KEY:
            return "gemini"
        else:
            return "ollama"
            
    CAL_API_KEY: str = os.getenv("CAL_API_KEY", "")
    CAL_EVENT_TYPE_ID: str = os.getenv("CAL_EVENT_TYPE_ID", "")
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "")
    
    VAPI_PUBLIC_KEY: str = os.getenv("VAPI_PUBLIC_KEY", "")
    VAPI_ASSISTANT_ID: str = os.getenv("VAPI_ASSISTANT_ID", "")

    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
