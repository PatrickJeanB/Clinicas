from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str

    # WhatsApp / Meta
    META_VERIFY_TOKEN: str
    META_APP_SECRET: str
    WHATSAPP_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_BUSINESS_ACCOUNT_ID: str

    # IA
    OPENROUTER_API_KEY: str
    OPENAI_API_KEY: str

    # Google Calendar
    GOOGLE_CALENDAR_ID: str
    GOOGLE_CREDENTIALS_PATH: str

    # Redis
    REDIS_URL: str

    # Ambiente
    APP_ENV: str = "development"
    APP_PORT: int = 8000


settings = Settings()
