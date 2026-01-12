import os
from pydantic_settings import BaseSettings, SettingsConfigDict

def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """Читает секрет из Docker Secret или переменной окружения."""
    # Сначала проверяем переменную окружения
    env_val = os.getenv(secret_name)
    if env_val:
        return env_val
    
    # Затем проверяем файл в /run/secrets/
    secret_path = f"/run/secrets/{secret_name.lower()}"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
            
    return default

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Swarm Project"
    
    SECRET_KEY: str = get_secret("SECRET_KEY", "secret-key")
    
    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = get_secret("DB_USER", "postgres")
    DB_PASSWORD: str = get_secret("DB_PASSWORD", "postgres")
    DB_NAME: str = get_secret("DB_NAME", "postgres")
    DB_SSL_MODE: str = "disable"
    DB_SSL_ROOT_CERT: str | None = None

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = get_secret("REDIS_PASSWORD")
    REDIS_SSL: bool = False
    REDIS_CONNECT_TIMEOUT: float = 1.0
    REDIS_READ_TIMEOUT: float = 1.0

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://tryout.site",
        "http://tryout.site",
        "http://85.198.86.165"
    ]

    DEBUG: bool = False
    
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
