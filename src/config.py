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

    # structured output (defense-in-depth for LLM JSON parsing)
    structured_output_strict: bool = True
    structured_output_max_repair_calls: int = 1
    max_tokens_ceiling: int = 8000

    @property
    def is_databricks(self) -> bool:
        return self.environment == "databricks"

    @property
    def resolved_llm_model(self) -> str:
        if self.is_databricks:
            return "databricks-meta-llama-3-1-8b-instruct"
        return self.llm_model

    @property
    def moderator_model(self) -> str:
        if self.is_databricks:
            return "databricks-meta-llama-3-3-70b-instruct"
        return self.resolved_llm_model

    @property
    def detector_model(self) -> str:
        """Detection sub-agents run on the strong model — the 8B is too weak for the
        domain/regulatory reasoning these agents do."""
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


# Detection models the analyst can pick from in the UI. Endpoint id -> display label.
# The default (when no model is chosen) stays whatever Settings.detector_model resolves to.
DETECTOR_MODELS: dict[str, str] = {
    "databricks-meta-llama-3-3-70b-instruct": "Llama 3.3 70B",
    "databricks-qwen35-122b-a10b": "Qwen3.5 122B · A10B (MoE)",
    "databricks-qwen3-next-80b-a3b-instruct": "Qwen3-Next 80B · A3B (MoE)",
}


def resolve_detector_model(model: str | None) -> str:
    """A requested model is used only if it is in the allow-list; otherwise fall back
    to the configured default. Never lets an arbitrary client string reach the LLM call."""
    if model and model in DETECTOR_MODELS:
        return model
    return get_settings().detector_model
