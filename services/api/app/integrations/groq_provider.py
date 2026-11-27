"""Server-only Groq structured generation adapter."""

import json

import httpx
from app.core.config import Settings
from app.integrations.openai_provider import (
    ProviderConfigurationError,
    ProviderInputError,
    ProviderInvalidResponse,
    ProviderRateLimited,
    ProviderRefused,
    ProviderTimeout,
    ProviderTransportError,
    ProviderUnavailable,
)
from app.schemas.analysis import AnalysisRequest, EvidenceChunk, LegalProcess
from app.services.prompting import REPAIR_INSTRUCTIONS, analysis_messages
from pydantic import ValidationError


class GroqLegalAnalysisProvider:
    provider_name = "groq"

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        if (
            settings.ai_provider != "groq"
            or not settings.ai_external_processing_allowed
            or not settings.groq_api_key.get_secret_value().strip()
            or not settings.groq_model.strip()
        ):
            raise ProviderUnavailable()
        self.settings = settings
        self.model_name = settings.groq_model
        self.client = client or httpx.Client(
            base_url="https://api.groq.com/openai/v1",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120, connect=10),
        )

    def _generate(self, messages: list[dict]) -> dict:
        try:
            response = self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "legal_process",
                            "strict": False,
                            "schema": LegalProcess.model_json_schema(),
                        },
                    },
                    "max_completion_tokens": 16000,
                },
            )
        except httpx.TimeoutException:
            raise ProviderTimeout() from None
        except httpx.RequestError:
            raise ProviderTransportError() from None
        if response.status_code == 429:
            raise ProviderRateLimited()
        if response.status_code in {408, 409} or response.status_code >= 500:
            raise ProviderTransportError()
        if response.status_code == 403:
            raise ProviderRefused()
        if not response.is_success:
            raise ProviderConfigurationError()
        try:
            payload = response.json()
            choice = payload["choices"][0]
            message = choice["message"]
            if message.get("refusal"):
                raise ProviderRefused()
            if choice.get("finish_reason") != "stop":
                raise ProviderInvalidResponse()
            content = message["content"]
            parsed = json.loads(content)
        except (ProviderRefused, ProviderInvalidResponse):
            raise
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
            raise ProviderInvalidResponse() from None
        return parsed

    def analyze(self, request: AnalysisRequest, evidence: list[EvidenceChunk]) -> LegalProcess:
        if not isinstance(evidence, list) or len(evidence) > 50:
            raise ProviderInputError()
        try:
            request = AnalysisRequest.model_validate(request.model_dump())
            evidence = [EvidenceChunk.model_validate(chunk) for chunk in evidence]
        except (ValidationError, ValueError, AttributeError, TypeError):
            raise ProviderInputError() from None
        if sum(len(chunk.content) for chunk in evidence) > 200_000:
            raise ProviderInputError()
        selected_ids = {str(document_id) for document_id in request.selected_document_ids}
        evidence_document_ids = {
            str(chunk.document_id) for chunk in evidence if chunk.document_id is not None
        }
        if (
            (selected_ids and evidence_document_ids != selected_ids)
            or (not selected_ids and evidence)
            or any(
                chunk.source_type != "user_document"
                or chunk.verification_status != "unverified"
                or chunk.document_id is None
                or chunk.source_id is not None
                or chunk.source_filename is None
                for chunk in evidence
            )
            or len({chunk.chunk_id for chunk in evidence}) != len(evidence)
        ):
            raise ProviderInputError()
        messages = analysis_messages(request, evidence)
        for attempt in range(2):
            try:
                return LegalProcess.model_validate(
                    self._generate(messages),
                    context={
                        "jurisdiction": request.jurisdiction,
                        "language": request.language,
                        "evidence": {chunk.chunk_id: chunk.content for chunk in evidence},
                        "require_complete_workflow": bool(evidence),
                    },
                )
            except ValidationError:
                if attempt:
                    raise ProviderInvalidResponse() from None
                messages.append({"role": "system", "content": REPAIR_INSTRUCTIONS})
        raise ProviderInvalidResponse()
