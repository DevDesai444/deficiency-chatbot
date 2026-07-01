from __future__ import annotations

from databricks.delta import query_deficiencies
from databricks.vector import search_similar
from retrieval.vector_search import embed_query
from schemas.flaws import SimilarDeficiency


def find_similar_deficiencies(
    query_text: str,
    top_k: int = 5,
) -> list[SimilarDeficiency]:
    query_vec = embed_query(query_text)
    raw_results = search_similar(query_vec, top_k=top_k)

    return [
        SimilarDeficiency(
            anda_number=r.get("anda_number", ""),
            product_name=r.get("product_name", ""),
            deficiency_text=r.get("deficiency_text", ""),
            similarity_score=r.get("similarity_score", 0.0),
        )
        for r in raw_results
    ]


def get_deficiencies_by_type(deficiency_type: str, limit: int = 20) -> list[dict]:
    return query_deficiencies(filters={"deficiency_type": deficiency_type}, limit=limit)
