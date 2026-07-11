from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str

    db_port: int = 5432
    db_host: str = "localhost"
    db_password: str = "postgres"
    db_user: str = "postgres"
    db_name: str = "quizzard"
    
    gonkagate_base_url: str = "https://api.gonkagate.com/v1"
    gonkagate_api_key: str

    llm_model: str = "moonshotai/kimi-k2.6"
    log_level: str = "INFO"
    
    admin_chat_id: int | None = None
    log_file: str = "bot_logs.txt"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()