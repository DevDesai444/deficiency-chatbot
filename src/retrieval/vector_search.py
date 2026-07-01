from __future__ import annotations

import numpy as np

from config import get_settings

_model = None


def _get_local_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        s = get_settings()
        _model = SentenceTransformer(s.embedding_model, device="cpu")
    return _model


def _embed_databricks(texts: list[str]) -> np.ndarray:
    from openai import OpenAI

    s = get_settings()
    client = OpenAI(
        base_url=f"{s.databricks_host}/serving-endpoints",
        api_key=s.databricks_token,
    )
    batch_size = 16
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(
            model="databricks-bge-large-en",
            input=batch,
        )
        all_embeddings.extend([d.embedding for d in resp.data])
    return np.array(all_embeddings, dtype=np.float32)


def embed_texts(texts: list[str], batch_size: int = 8) -> np.ndarray:
    s = get_settings()
    if s.is_databricks:
        return _embed_databricks(texts)
    model = _get_local_model()
    return model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=batch_size,
    )


def embed_query(text: str) -> np.ndarray:
    s = get_settings()
    if s.is_databricks:
        return _embed_databricks([text])[0]
    model = _get_local_model()
    return model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
