import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    APP_NAME: str = "Smartbot"
    APP_VERSION: str = "1.0.0"

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.db")
    
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./chroma_db")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "chromadb")
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "chromadb_data")
    
    CORS_ORIGINS: list = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding="utf-8"
        case_sensitive = True


settings = Settings()

def validate_settings():
    """Validate that required settings are present"""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in environment variables")