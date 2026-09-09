import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ghumo"
    SECRET_KEY: str = "your_secret_key_here"
    
    # External APIs
    GOOGLE_PLACES_API_KEY: str = ""
    OPENTRIPMAP_API_KEY: str = ""
    YOUTUBE_TRANSCRIPT_API_URL: str = ""
    
    # AI Config
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_MODEL_NAME: str = "mistral"
    AI_SOURCE: str = "groq"  # 'huggingface', 'ollama', 'groq', or 'gemini'
    GROQ_API_KEY: str = ""
    GROQ_MODEL_NAME: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-3.6-flash"

    # Valkey Config
    VALKEY_URL: str = "redis://localhost:6379/0"

    # Webshare Proxy Config
    WEBSHARE_USERNAME: str = ""
    WEBSHARE_PASSWORD: str = ""

    # Cloudflare Browser Rendering API
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_AUTH_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        extra="ignore"
    )

settings = Settings()
