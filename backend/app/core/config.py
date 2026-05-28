from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "智能面试助手"
    upload_dir: str = "uploads"
    min_pdf_text_chars: int = 80
    cors_origins: list[str] = ["*"]
    database_path: str = "interview_assistant.sqlite3"

    llm_provider: str = "chatanywhere"
    chatanywhere_api_key: str | None = None
    chatanywhere_base_url: str = "https://api.chatanywhere.tech/v1"
    chatanywhere_model: str = "gpt-5-mini"
    chatanywhere_embedding_model: str = "text-embedding-ada-002"
    llm_timeout_seconds: float = 20.0
    llm_max_tokens: int = 1800
    rag_vector_dir: str = ".rag"

    xfyun_app_id: str | None = None
    xfyun_api_key: str | None = None
    xfyun_api_secret: str | None = None
    xfyun_spark_api_password: str | None = None
    xfyun_spark_base_url: str = "https://spark-api-open.xf-yun.com/v2"
    xfyun_spark_model: str = "spark-x"
    xfyun_embedding_url: str = "https://emb-cn-huabei-1.xf-yun.com/"
    xfyun_iat_url: str = "wss://iat-api.xfyun.cn/v2/iat"
    audio_chunk_seconds: int = 55

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
