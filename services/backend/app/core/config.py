from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Swarm Project"
    
    SECRET_KEY: str = "secret-key"
    
    # Database settings
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "postgres"
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
    REDIS_PASSWORD: str | None = None
    REDIS_SSL: bool = False
    REDIS_CONNECT_TIMEOUT: float = 1.0
    REDIS_READ_TIMEOUT: float = 1.0

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://tryout.site",
        "http://tryout.site",
    ]

    DEBUG: bool = True
    
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
