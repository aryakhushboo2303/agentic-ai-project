from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Contract Review System"
    debug: bool = False
    log_level: str = "INFO"
    upload_dir: str = "./uploads"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/contract_review"

    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "contract_chunks"

    llm_provider: str = "gemini"
    google_api_key: str = ""
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/text-embedding-004"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    rag_top_k: int = 5


settings = Settings()
