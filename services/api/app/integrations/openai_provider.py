"""Server-only OpenAI adapters. Runtime configuration never falls back to synthetic output."""

import json
from collections.abc import Callable
from typing import Protocol, TypeVar

from app.core.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, Settings
from app.schemas.analysis import AnalysisRequest, EmbeddingBatch, EvidenceChunk, LegalProcess
from app.services.prompting import REPAIR_INSTRUCTIONS, analysis_messages
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError


class ProviderError(Exception):
    code = "provider_error"
    retryable = False
    message = "AI processing failed. Please try again later."

    def __init__(self):
        super().__init__(self.message)


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    message = "AI processing is unavailable. Configure a supported provider before submitting."


class ProviderConfigurationError(ProviderError):
    code = "provider_configuration_error"
    message = "AI provider configuration requires operator attention."


class ProviderInputError(ProviderError):
    code = "provider_invalid_input"
    message = "AI input is invalid or exceeds the processing limits."


class ProviderInvalidResponse(ProviderError):
    code = "provider_invalid_response"
    message = "The AI response could not be validated. No result was published."


class ProviderRefused(ProviderError):
    code = "provider_refused"
    message = "The AI provider declined this request. Review the input before trying again."


class ProviderTimeout(ProviderError):
    code = "provider_timeout"
    retryable = True
    message = "The AI provider timed out. Please try again later."


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limited"
    retryable = True
    message = "The AI provider is temporarily rate limited. Please try again later."


class ProviderTransportError(ProviderError):
    code = "provider_transport_error"
    retryable = True
    message = "The AI provider is temporarily unreachable. Please try again later."


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> EmbeddingBatch: ...


class LegalAnalysisProvider(Protocol):
    def analyze(self, request: AnalysisRequest, evidence: list[EvidenceChunk]) -> LegalProcess: ...


T = TypeVar("T")


def _call(operation: Callable[[], T]) -> T:
    """Sanitize SDK failures and let the durable job owner handle transient retries."""
    try:
        return operation()
    except APITimeoutError:
        raise ProviderTimeout() from None
    except RateLimitError:
        raise ProviderRateLimited() from None
    except APIConnectionError:
        raise ProviderTransportError() from None
    except APIStatusError as error:
        if error.code in {"content_policy_violation", "content_filter", "safety_violation"}:
            raise ProviderRefused() from None
        if error.status_code >= 500 or error.status_code in {408, 409}:
            raise ProviderTransportError() from None
        raise ProviderConfigurationError() from None
    except APIResponseValidationError:
        raise ProviderInvalidResponse() from None


def _ensure_available(settings: Settings) -> None:
    if (
        settings.ai_provider != "openai"
        or not settings.ai_external_processing_allowed
        or not settings.openai_api_key.get_secret_value().strip()
        or not settings.openai_analysis_model.strip()
        or (settings.embedding_model, settings.embedding_dimensions)
        != (EMBEDDING_MODEL, EMBEDDING_DIMENSIONS)
    ):
        raise ProviderUnavailable()


def provider_is_configured(settings: Settings) -> bool:
    if settings.ai_provider == "ollama":
        return bool(
            settings.ollama_analysis_model.strip() and settings.ollama_embedding_model.strip()
        )
    return bool(
        settings.ai_external_processing_allowed
        and settings.openai_api_key.get_secret_value().strip()
        and settings.openai_analysis_model.strip()
    )


class _OpenAIProvider:
    def __init__(self, settings: Settings, *, client: OpenAI | None = None):
        _ensure_available(settings)
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=60,
            max_retries=0,
        )


class OpenAIEmbeddingProvider(_OpenAIProvider):
    provider_name = "openai"
    model_name = EMBEDDING_MODEL

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
        response = _call(
            lambda: self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input=texts,
                encoding_format="float",
            )
        )
        try:
            if response.model != EMBEDDING_MODEL:
                raise ValueError("Embedding model does not match the configured contract")
            if len(response.data) != len(texts) or [item.index for item in response.data] != list(
                range(len(texts))
            ):
                raise ValueError("Embedding count or order does not match input")
            return EmbeddingBatch(
                provider="openai",
                model=response.model,
                dimensions=EMBEDDING_DIMENSIONS,
                vectors=[item.embedding for item in response.data],
            )
        except (ValidationError, ValueError, AttributeError, TypeError):
            raise ProviderInvalidResponse() from None


class OpenAILegalAnalysisProvider(_OpenAIProvider):
    provider_name = "openai"
    model_name = ""

    def analyze(self, request: AnalysisRequest, evidence: list[EvidenceChunk]) -> LegalProcess:
        try:
            request = AnalysisRequest.model_validate(request.model_dump())
            if not isinstance(evidence, list) or len(evidence) > 50:
                raise ValueError("Invalid evidence count")
            evidence = [EvidenceChunk.model_validate(chunk.model_dump()) for chunk in evidence]
            passages = {chunk.chunk_id: chunk.content for chunk in evidence}
            if len(passages) != len(evidence) or sum(map(len, passages.values())) > 200000:
                raise ValueError("Duplicate or oversized evidence packet")
        except (ValidationError, ValueError, AttributeError, TypeError):
            raise ProviderInputError() from None

        messages = analysis_messages(request, evidence)
        for attempt in range(2):
            try:
                raw_response = _call(
                    lambda: self.client.responses.with_raw_response.parse(
                        model=self.settings.openai_analysis_model,
                        input=messages,
                        text_format=LegalProcess,
                        store=False,
                        max_output_tokens=16000,
                    )
                )
                # Inspect the envelope before the SDK eagerly validates output text.
                # Refusal and truncation must never become validation-repair inputs.
                envelope = raw_response.http_response.json()
                if any(
                    content.get("type") == "refusal"
                    for output in envelope.get("output", [])
                    if output.get("type") == "message"
                    for content in output.get("content", [])
                ):
                    raise ProviderRefused()
                if (
                    envelope.get("status") != "completed"
                    or envelope.get("incomplete_details") is not None
                ):
                    raise ProviderInvalidResponse()
                response = _call(raw_response.parse)
                if response.output_parsed is None:
                    raise ValueError("Missing structured output")
                return LegalProcess.model_validate(
                    response.output_parsed.model_dump(),
                    context={"jurisdiction": request.jurisdiction, "evidence": passages},
                )
            except (ValidationError, json.JSONDecodeError, ValueError, AttributeError, TypeError):
                if attempt:
                    raise ProviderInvalidResponse() from None
                # Never echo the provider's output, exception text, or evidence into a policy message.
                messages.append({"role": "system", "content": REPAIR_INSTRUCTIONS})
        raise ProviderInvalidResponse()


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.ai_provider == "ollama":
        from app.integrations.ollama_provider import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(settings)
    return OpenAIEmbeddingProvider(settings)


def get_analysis_provider(settings: Settings) -> LegalAnalysisProvider:
    if settings.ai_provider == "ollama":
        from app.integrations.ollama_provider import OllamaLegalAnalysisProvider

        return OllamaLegalAnalysisProvider(settings)
    return OpenAILegalAnalysisProvider(settings)
