"""Local Ollama adapters implementing the shared analysis and embedding contracts."""

import json

import httpx
from app.core.config import EMBEDDING_DIMENSIONS, Settings
from app.integrations.openai_provider import (
    ProviderConfigurationError,
    ProviderInputError,
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderTransportError,
    ProviderUnavailable,
)
from app.schemas.analysis import (
    AnalysisRequest,
    EmbeddingBatch,
    EvidenceChunk,
    LegalProcess,
)
from app.services.prompting import REPAIR_INSTRUCTIONS, analysis_messages
from pydantic import ValidationError


class _OllamaProvider:
    provider_name = "ollama"

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        if (
            settings.ai_provider != "ollama"
            or not settings.ollama_analysis_model.strip()
            or not settings.ollama_embedding_model.strip()
        ):
            raise ProviderUnavailable()
        self.settings = settings
        self.client = client or httpx.Client(
            base_url=settings.ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120, connect=3),
        )

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self.client.post(path, json=payload)
        except httpx.TimeoutException:
            raise ProviderTimeout() from None
        except httpx.RequestError:
            raise ProviderTransportError() from None
        if response.status_code == 429:
            raise ProviderRateLimited()
        if response.status_code in {408, 409}:
            raise ProviderTimeout()
        if response.status_code >= 500:
            raise ProviderTransportError()
        if not response.is_success:
            raise ProviderConfigurationError()
        try:
            result = response.json()
        except (json.JSONDecodeError, ValueError):
            raise ProviderInvalidResponse() from None
        if not isinstance(result, dict):
            raise ProviderInvalidResponse()
        return result


class OllamaEmbeddingProvider(_OllamaProvider):
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        super().__init__(settings, client=client)
        self.model_name = settings.ollama_embedding_model

    def embed(self, texts: list[str]) -> EmbeddingBatch:
        if (
            not isinstance(texts, list)
            or not 1 <= len(texts) <= 128
            or any(
                not isinstance(text, str) or not text.strip() or len(text) > 12000 for text in texts
            )
            or sum(len(text) for text in texts) > 200000
        ):
            raise ProviderInputError()
        result = self._post(
            "/api/embed",
            {
                "model": self.model_name,
                "input": texts,
                "dimensions": EMBEDDING_DIMENSIONS,
            },
        )
        try:
            return EmbeddingBatch(
                provider=self.provider_name,
                model=self.model_name,
                dimensions=EMBEDDING_DIMENSIONS,
                vectors=result["embeddings"],
            )
        except (ValidationError, KeyError, TypeError):
            raise ProviderInvalidResponse() from None


class OllamaLegalAnalysisProvider(_OllamaProvider):
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        super().__init__(settings, client=client)
        self.model_name = settings.ollama_analysis_model

    def analyze(self, request: AnalysisRequest, evidence: list[EvidenceChunk]) -> LegalProcess:
        try:
            request = AnalysisRequest.model_validate(request.model_dump())
            if not isinstance(evidence, list) or len(evidence) > 50:
                raise ValueError("Invalid evidence count")
            evidence = [EvidenceChunk.model_validate(item.model_dump()) for item in evidence]
            passages = {chunk.chunk_id: chunk.content for chunk in evidence}
            if len(passages) != len(evidence) or sum(map(len, passages.values())) > 200000:
                raise ValueError("Duplicate or oversized evidence packet")
        except (ValidationError, ValueError, AttributeError, TypeError):
            raise ProviderInputError() from None

        messages = analysis_messages(request, evidence)
        for attempt in range(2):
            response = self._post(
                "/api/chat",
                {
                    "model": self.model_name,
                    "messages": messages,
                    "format": LegalProcess.model_json_schema(),
                    "stream": False,
                    "options": {"num_predict": 16000},
                },
            )
            try:
                if response.get("done") is not True:
                    raise ValueError("Incomplete model response")
                content = response["message"]["content"]
                parsed = LegalProcess.model_validate_json(content)
                return LegalProcess.model_validate(
                    parsed.model_dump(),
                    context={
                        "jurisdiction": request.jurisdiction,
                        "language": request.language,
                        "evidence": passages,
                    },
                )
            except (ValidationError, json.JSONDecodeError, ValueError, KeyError, TypeError):
                if attempt:
                    raise ProviderInvalidResponse() from None
                messages.append({"role": "system", "content": REPAIR_INSTRUCTIONS})
        raise ProviderInvalidResponse()


def ollama_status(settings: Settings, *, client: httpx.Client | None = None) -> dict:
    if (
        settings.ai_provider != "ollama"
        or not settings.ollama_analysis_model.strip()
        or not settings.ollama_embedding_model.strip()
    ):
        return {"provider": settings.ai_provider, "available": False, "reason": "not_configured"}
    owned_client = client is None
    http = client or httpx.Client(
        base_url=settings.ollama_base_url.rstrip("/"),
        timeout=httpx.Timeout(2, connect=1),
    )
    try:
        response = http.get("/api/tags")
        if not response.is_success:
            return {"provider": "ollama", "available": False, "reason": "unreachable"}
        models = response.json().get("models", [])
        names = {item.get("name") or item.get("model") for item in models if isinstance(item, dict)}
        available = {
            settings.ollama_analysis_model,
            settings.ollama_embedding_model,
        }.issubset(names)
        return {
            "provider": "ollama",
            "available": available,
            "reason": None if available else "models_not_installed",
        }
    except (httpx.RequestError, json.JSONDecodeError, ValueError, AttributeError, TypeError):
        return {"provider": "ollama", "available": False, "reason": "unreachable"}
    finally:
        if owned_client:
            http.close()
