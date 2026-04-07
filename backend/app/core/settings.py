from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "AppClinicas"
    APP_URL: str = ""
    APP_SUPPORT_EMAIL: str = ""
    APP_ENV: str = "development"
    APP_PORT: int = 8000

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str

    # IA
    OPENROUTER_API_KEY: str
    OPENAI_API_KEY: str

    # Redis
    REDIS_URL: str

    # Criptografia
    ENCRYPTION_KEY: str


settings = Settings()
