from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from config import get_settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        s = get_settings()
        device = "cpu" if not s.is_databricks else None
        _model = SentenceTransformer(s.embedding_model, device=device)
    return _model


def embed_texts(texts: list[str], batch_size: int = 8) -> np.ndarray:
    model = _get_model()
    return model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=batch_size,
    )


def embed_query(text: str) -> np.ndarray:
    model = _get_model()
    return model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
