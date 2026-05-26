from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "智能面试助手"
    upload_dir: str = "uploads"
    min_pdf_text_chars: int = 80
    cors_origins: list[str] = ["*"]

    llm_provider: str = "chatanywhere"
    chatanywhere_api_key: str | None = None
    chatanywhere_base_url: str = "https://api.chatanywhere.tech/v1"
    chatanywhere_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0
    llm_max_tokens: int = 1800

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
