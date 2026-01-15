from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    POSTGRES_HOST: str = "dpg-d4im0jh5pdvs73834210-a.oregon-postgres.render.com"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "alfa_collection"
    POSTGRES_USER: str = "alfa_collection_user"
    POSTGRES_PASSWORD: str = "VpjoxZ45dhe6wxXicJEHLMySD6og4loj"
    
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    
    @property
    def DATABASE_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"

settings = Settings()