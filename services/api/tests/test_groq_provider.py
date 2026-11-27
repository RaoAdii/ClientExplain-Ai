import json
from uuid import UUID

import httpx
import pytest
from app.core.config import Settings
from app.integrations.groq_provider import GroqLegalAnalysisProvider
from app.integrations.openai_provider import (
    ProviderInputError,
    ProviderInvalidResponse,
    ProviderRefused,
)
from app.schemas.analysis import AnalysisRequest, EvidenceChunk


def settings():
    return Settings(
        app_env="test",
        auth_mode="development",
        dev_auth_token="x" * 32,
        database_url="postgresql+psycopg://localhost/test",
        ai_provider="groq",
        ai_external_processing_allowed=True,
        groq_api_key="offline-test-key",
        groq_model="openai/gpt-oss-20b",
        _env_file=None,
    )


def request():
    return AnalysisRequest(process_text="Explain the filing process.", jurisdiction="India")


def process():
    return {
        "process_name": "Filing process",
        "jurisdiction": "India",
        "legal_area": "General",
        "summary": "A general explanation for professional review.",
        "applicability_date": None,
        "audience": "Client",
        "complexity": "simple",
        "stages": [{
            "stage_number": 1,
            "title": "Prepare the filing",
            "explanation": "Gather the facts and seek professional review.",
            "responsible_party": "Applicant",
            "required_documents": [],
            "estimated_duration": None,
            "evidence_chunk_ids": [],
            "claims": [],
            "source_backed": False,
            "general_explanation": True,
            "limitations": ["No source evidence was supplied."],
        }],
        "missing_information": [],
        "limitations": ["A lawyer must review this process."],
        "review_required": True,
    }


def test_groq_generates_validated_structured_process_without_embeddings():
    calls = []

    def respond(http_request):
        calls.append(json.loads(http_request.content))
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(process())}}]
        })

    client = httpx.Client(transport=httpx.MockTransport(respond))
    output = GroqLegalAnalysisProvider(settings(), client=client).analyze(request(), [])

    assert output.process_name == "Filing process"
    assert calls[0]["model"] == "openai/gpt-oss-20b"
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[0]["response_format"]["json_schema"]["strict"] is False


def test_groq_rejects_selected_documents_without_their_evidence():
    selected = request().model_copy(
        update={"selected_document_ids": [UUID("f6b243b8-51df-4c67-a270-216f2abbb778")]}
    )
    with pytest.raises(ProviderInputError):
        GroqLegalAnalysisProvider(settings(), client=httpx.Client()).analyze(selected, [])


def test_groq_includes_selected_document_text_and_provenance():
    calls = []
    document_id = "f6b243b8-51df-4c67-a270-216f2abbb778"
    selected = request().model_copy(update={"selected_document_ids": [UUID(document_id)]})
    evidence = [
        EvidenceChunk(
            chunk_id="chunk-1",
            content="Fictional agreement: refundable deposit of INR 45000.",
            document_id=document_id,
            source_filename="fictional-agreement.txt",
            page_number=1,
            heading="Security deposit",
        )
    ]
    payload = process()
    payload["stages"] = [
        {
            "stage_number": 1,
            "title": "Review the agreement",
            "explanation": "Confirm the recorded deposit.",
            "responsible_party": "Parties",
            "required_documents": [],
            "estimated_duration": None,
            "evidence_chunk_ids": ["chunk-1"],
            "claims": [
                {
                    "claim_text": "The agreement records a deposit of INR 45000.",
                    "source_backed": True,
                    "evidence_chunk_id": "chunk-1",
                    "excerpt": "refundable deposit of INR 45000",
                }
            ],
            "inputs": ["Selected agreement excerpt"],
            "actions": ["Confirm the amount recorded in the agreement."],
            "expected_outputs": ["A verified record of the stated deposit."],
            "source_backed": True,
            "general_explanation": False,
            "limitations": [],
        },
        {
            "stage_number": 2,
            "title": "Confirm the refund",
            "explanation": "Verify any proposed deductions before calculating a balance.",
            "responsible_party": "Parties",
            "required_documents": [],
            "estimated_duration": None,
            "evidence_chunk_ids": [],
            "claims": [],
            "inputs": ["Verified deposit record"],
            "actions": ["Check the proposed deductions against supporting records."],
            "expected_outputs": ["A reviewed calculation."],
            "source_backed": False,
            "general_explanation": True,
            "limitations": [],
        },
    ]
    payload["facts"] = [
        {
            "statement": "The agreement records a refundable deposit.",
            "evidence_chunk_id": "chunk-1",
            "excerpt": "refundable deposit of INR 45000",
        }
    ]
    payload["financial_facts"] = [
        {
            "kind": "deposit",
            "label": "Refundable deposit",
            "amount": "45000.00",
            "currency": "INR",
            "evidence_chunk_id": "chunk-1",
            "excerpt": "refundable deposit of INR 45000",
        }
    ]

    def respond(http_request):
        body = json.loads(http_request.content)
        calls.append(body)
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    result = GroqLegalAnalysisProvider(settings(), client=client).analyze(selected, evidence)

    assert len(result.stages) == 2
    packet = json.loads(calls[0]["messages"][1]["content"])
    assert packet["request"]["selected_document_ids"] == [document_id]
    assert packet["evidence"][0]["content"] == evidence[0].content
    assert packet["evidence"][0]["source_filename"] == "fictional-agreement.txt"
    assert result.facts[0].excerpt in evidence[0].content
    assert result.financial_facts[0].amount == 45000


@pytest.mark.parametrize(
    "evidence",
    [
        [
            EvidenceChunk(
                chunk_id="chunk-1",
                content="Verified authority text",
                source_type="legislation",
                verification_status="verified",
                document_id="f6b243b8-51df-4c67-a270-216f2abbb778",
                source_filename="law.txt",
            )
        ],
        [
            EvidenceChunk(
                chunk_id="chunk-1",
                content="Unselected document text",
                document_id="a6b243b8-51df-4c67-a270-216f2abbb779",
                source_filename="other.txt",
            )
        ],
    ],
)
def test_groq_rejects_non_document_or_unselected_evidence(evidence):
    selected = request().model_copy(
        update={"selected_document_ids": [UUID("f6b243b8-51df-4c67-a270-216f2abbb778")]}
    )
    with pytest.raises(ProviderInputError):
        GroqLegalAnalysisProvider(settings(), client=httpx.Client()).analyze(selected, evidence)


@pytest.mark.parametrize(
    ("choice", "error"),
    [
        (
            {"finish_reason": "length", "message": {"content": json.dumps(process())}},
            ProviderInvalidResponse,
        ),
        (
            {"finish_reason": "stop", "message": {"refusal": "declined", "content": None}},
            ProviderRefused,
        ),
    ],
)
def test_groq_rejects_refusal_and_truncated_completion(choice, error):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"choices": [choice]})
        )
    )
    with pytest.raises(error):
        GroqLegalAnalysisProvider(settings(), client=client).analyze(request(), [])
