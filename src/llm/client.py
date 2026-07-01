from __future__ import annotations

from openai import OpenAI

from config import get_settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        if s.is_databricks:
            _client = OpenAI(
                base_url=f"{s.databricks_host}/serving-endpoints",
                api_key=s.databricks_token,
            )
        else:
            _client = OpenAI(
                base_url=s.llm_base_url,
                api_key="not-needed",
            )
    return _client


def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
) -> str:
    s = get_settings()
    client = get_client()
    response = client.chat.completions.create(
        model=model or s.llm_model,
        messages=messages,
        temperature=temperature if temperature is not None else s.llm_temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
