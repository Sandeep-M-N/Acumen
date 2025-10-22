from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str
    BASE_BLOB_PATH: str
    AZURE_TENANT_ID: str
    AZURE_CLIENT_ID: str
    DATABASE_URL_FILES: str
    BASE_RAW_PATH:str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str 
    AZURE_OPENAI_DEPLOYMENT_NAME: str
    OPENAI_API_VERSION: str
    LANGSMITH_TRACING : bool
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str 
    LANGSMITH_PROJECT: str
    LLMProvider: str
    REDIS_URL: str
    REDIS_CONFIG: int
    
    class Config:
        env_file = ".env"

settings = Settings()