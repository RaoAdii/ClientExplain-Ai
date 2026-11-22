"""Tenant-filtered pgvector cosine retrieval of actual stored passages."""

import math

from app.repositories.sources import evidence_query
from app.schemas.analysis import EvidenceChunk
from app.schemas.sources import RetrievalFilters
from app.services.projects import require_project
from pydantic import TypeAdapter


def validate_query_vector(vector):
    if (
        not isinstance(vector, list)
        or len(vector) != 1536
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)
        or not any(vector)
    ):
        raise ValueError("A finite, nonzero 1536-dimensional vector is required.")
    return vector


def retrieve_evidence(
    db, principal, project_id, query_vector, filters, limit, threshold
) -> list[EvidenceChunk]:
    validate_query_vector(query_vector)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Retrieval limit must be between 1 and 50.")
    if (
        type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError("Similarity threshold must be between zero and one.")
    filters = TypeAdapter(RetrievalFilters).validate_python(filters)
    require_project(db, principal, project_id)
    query = evidence_query(principal.firm_id, project_id, query_vector, filters, threshold).limit(
        limit
    )
    return [
        EvidenceChunk.model_validate(
            {key: value for key, value in row.items() if key != "distance"}
        )
        for row in db.execute(query).mappings()
    ]
