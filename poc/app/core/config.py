from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./poc.db"

    # Unset = stub/mock mode for that integration. Set the env var to go live;
    # no code changes required elsewhere.
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    google_places_api_key: str | None = None
    viator_api_base_url: str | None = None
    viator_api_key: str | None = None
    viator_partner_id: str | None = None
    semrush_api_key: str | None = None
    semrush_api_base_url: str = "https://api.semrush.com/"
    semrush_database: str = "us"
    vector_similarity_enabled: bool = True
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Model C tuning (Phase 4) - kept here so thresholds are configurable in one place.
    pool_min_quality_score: float = 0.6
    set_sparse_threshold: int = 2

    @property
    def openai_stub(self) -> bool:
        return not self.openai_api_key

    @property
    def groq_stub(self) -> bool:
        return not self.groq_api_key

    @property
    def google_places_stub(self) -> bool:
        return not self.google_places_api_key

    @property
    def viator_stub(self) -> bool:
        return not self.viator_api_key

    @property
    def semrush_stub(self) -> bool:
        return not self.semrush_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
