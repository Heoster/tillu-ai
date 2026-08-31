from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str
    cerebras_api_key: str
    backend_port: int = 8000
    frontend_port: int = 3000
    frontend_origin: str = "http://localhost:3000"
    scheduler_nightly_hour: int = 22
    scheduler_nightly_minute: int = 0
    default_sleep_start: str = "23:00"
    default_sleep_end: str = "06:00"
    playwright_enabled: bool = False

    # Phase 4 — Sarvam STT/TTS voice interaction
    sarvam_api_key: str = ""
    sarvam_enabled: bool = False

    # Phase 6 — RAG document search (pgvector)
    rag_enabled: bool = False
    # Optional external embedding API (e.g. a local sentence-transformers server).
    # If empty, the built-in sentence-transformers library (or hash stub) is used.
    embedding_api_url: str = ""

    # Phase 6 — Parallel Search MCP
    parallel_mcp_enabled: bool = False
    parallel_search_enabled: bool = False  # alias kept for .env compatibility


settings = Settings()
