from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"  # "local" or "databricks"

    # databricks
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = "defpredict"
    databricks_schema: str = "main"

    # model serving -- OpenAI-compatible for both local (Ollama) and Databricks
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "mistral:7b-instruct"
    llm_temperature: float = 0.1

    # fine-tuned endpoints (fall back to base model if empty)
    suggestor_model: str = ""
    evaluator_model: str = ""

    # embeddings
    embedding_model: str = "BAAI/bge-m3"

    # vector search
    vector_search_endpoint: str = ""
    vector_search_index: str = "deficiency_kb_index"

    # data
    data_dir: str = ""

    # api
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    log_level: str = "INFO"

    # agent tuning
    max_consensus_rounds: int = 3
    max_inner_loops: int = 3
    max_outer_loops: int = 1

    @property
    def is_databricks(self) -> bool:
        return self.environment == "databricks"

    @property
    def resolved_llm_model(self) -> str:
        if self.is_databricks and self.llm_model.startswith("mistral"):
            return "databricks-meta-llama-3-1-8b-instruct"
        return self.llm_model

    @property
    def moderator_model(self) -> str:
        if self.is_databricks:
            return "databricks-meta-llama-3-3-70b-instruct"
        return self.resolved_llm_model

    @property
    def suggestor_endpoint(self) -> str:
        return self.suggestor_model or self.resolved_llm_model

    @property
    def evaluator_endpoint(self) -> str:
        return self.evaluator_model or self.resolved_llm_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
