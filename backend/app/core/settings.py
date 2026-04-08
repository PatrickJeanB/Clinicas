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

    # Multi-tenant
    DEFAULT_CLINIC_ID: str = "00000000-0000-0000-0000-000000000001"

    # WhatsApp / Meta
    META_APP_SECRET: str
    META_VERIFY_TOKEN: str
    WHATSAPP_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_BUSINESS_ACCOUNT_ID: str

    # Google Calendar
    GOOGLE_CALENDAR_ID: str
    GOOGLE_CREDENTIALS_PATH: str


settings = Settings()
