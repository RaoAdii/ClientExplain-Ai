"""Analysis runs real database/job/provider paths with offline SDK HTTP responses."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import httpx
import pytest
from app.db.session import SessionLocal
from app.integrations.openai_provider import OpenAIEmbeddingProvider, OpenAILegalAnalysisProvider
from app.models.entities import (
    Document,
    DocumentChunk,
    Firm,
    GenerationJob,
    ProcessStage,
    Project,
    ProjectVersion,
    StageCitation,
)
from app.schemas.analysis import AnalysisRequest
from app.services.analysis import AnalysisProviders
from app.services.jobs import create_job, transition_job
from sqlalchemy import delete, event, func, select, text, update
from test_analysis_provider import backed_process, process, response_body, sdk_client, settings
from test_rag import OWNER, VECTOR, document, source
from worker.celery_app import app as celery
from worker.pipelines.analysis import run_analysis_job
from worker.tasks import engine as worker_engine
from worker.tasks import record_failure


@pytest.fixture
def project_id():
    with SessionLocal.begin() as db:
        project = Project(
            firm_id=OWNER.firm_id,
            created_by=OWNER.user_id,
            name="Analysis",
            jurisdiction="India",
            review_status="approved",
        )
        db.add(project)
        db.flush()
        project_id = project.id
    yield project_id
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id == project_id))


def job_for(project_id, selected=(), *, claim=True, process_text="Explain filing"):
    with SessionLocal.begin() as db:
        job = create_job(db, OWNER, project_id, "analysis", "a" * 64, None)
        request = AnalysisRequest(
            process_text=process_text,
            jurisdiction="India",
            selected_document_ids=list(selected),
        )
        job.request_metadata = {
            "analysis_request": request.model_dump(mode="json"),
            "worker_task_id": "offline-task",
        }
        db.flush()
        if claim:
            transition_job(db, job.id, "queued", "running", stage="starting", progress=0)
        return job.id


def providers(*, callback=None, invalid=False, responses=None, embedding_vectors=None):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if callback:
            callback(request.url.path, body)
        if request.url.path.endswith("embeddings"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "text-embedding-3-small",
                    "data": [
                        {
                            "object": "embedding",
                            "index": i,
                            "embedding": embedding_vectors[i] if embedding_vectors else VECTOR,
                        }
                        for i, _ in enumerate(body["input"])
                    ],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )
        packet = json.loads(body["input"][1]["content"])
        evidence = packet["evidence"]
        payload = backed_process(evidence[0]["chunk_id"]) if evidence else process()
        if invalid:
            payload["stages"].append({"stage_number": 2})
        if responses:
            return responses(request, body)
        return httpx.Response(200, json=response_body(payload))

    client = sdk_client(handler)
    config = settings()
    return AnalysisProviders(
        OpenAIEmbeddingProvider(config, client=client),
        OpenAILegalAnalysisProvider(config, client=client),
        worker_task_id="offline-task",
    ), calls


def test_selected_chunks_embed_on_demand_and_publish_atomically_once(project_id):
    with SessionLocal.begin() as db:
        selected, chunk = document(db, project_id, vector=None)
        unselected, _ = document(db, project_id, vector=None)
        ids = selected.id, unselected.id, chunk.id
    job_id = job_for(project_id, [ids[0]])
    provider, calls = providers()
    run_analysis_job(job_id, provider)
    run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        assert db.get(DocumentChunk, ids[2]).embedding is not None
        assert (
            db.scalar(select(DocumentChunk.embedding).where(DocumentChunk.document_id == ids[1]))
            is None
        )
        stage = db.scalar(select(ProcessStage).where(ProcessStage.project_id == project_id))
        assert (stage.position, stage.verification_status, stage.source_backed) == (
            0,
            "unverified",
            True,
        )
        citation = db.scalar(select(StageCitation).where(StageCitation.stage_id == stage.id))
        assert citation.document_chunk_id == ids[2]
        assert (citation.excerpt, citation.validation_status) == (
            "File the application",
            "unverified",
        )
        version = db.scalar(select(ProjectVersion).where(ProjectVersion.project_id == project_id))
        assert version.generation_job_id == job_id and version.version == 1
        assert version.snapshot["stages"][0]["verification_status"] == "unverified"
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 1
        assert db.get(Project, project_id).review_status == "requires_review"
        assert db.get(GenerationJob, job_id).status == "completed"
    assert [body["input"] for path, body in calls if path.endswith("embeddings")] == [
        ["File the application with the registry."],
        ["Explain filing"],
    ]


def test_no_selected_documents_produces_unverified_general_results(project_id):
    with SessionLocal.begin() as db:
        document(db, project_id, vector=None)
        source(db, project_id=project_id)
    job_id = job_for(project_id)
    provider, calls = providers()
    run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        stage = db.scalar(select(ProcessStage).where(ProcessStage.project_id == project_id))
        assert (stage.verification_status, stage.general_explanation) == ("unverified", True)
        assert (
            db.scalar(
                select(func.count())
                .select_from(StageCitation)
                .where(StageCitation.project_id == project_id)
            )
            == 0
        )
    assert all(
        body["input"] == ["Explain filing"] for path, body in calls if path.endswith("embeddings")
    )


@pytest.mark.parametrize("length", [12000, 12001, 20000])
def test_analysis_accepts_long_requests_with_bounded_query_embeddings(project_id, length):
    text = "a" * 12000 + "b" * (length - 12000)
    job_id = job_for(project_id, process_text=text)
    provider, calls = providers()
    run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        assert db.get(GenerationJob, job_id).status == "completed"
        assert db.get(Project, project_id).processing_status == "completed"
    inputs = [body["input"] for path, body in calls if path.endswith("embeddings")]
    assert len(inputs) == 1
    assert "".join(inputs[0]) == text
    assert all(1 <= len(part) <= 12000 for part in inputs[0])
    packets = [
        json.loads(body["input"][1]["content"])
        for path, body in calls
        if path.endswith("responses")
    ]
    assert packets[0]["request"]["process_text"] == text


def test_query_embedding_uses_both_parts_of_a_long_request_for_retrieval(project_id):
    tail_vector = [0.0, 1.0] + [0.0] * 1534
    with SessionLocal.begin() as db:
        first, _ = document(db, project_id)
        last, _ = document(db, project_id, vector=tail_vector)
        selected = [first.id, last.id]
    job_id = job_for(project_id, selected, process_text="a" * 12000 + "b" * 8000)
    provider, calls = providers(embedding_vectors=[VECTOR, tail_vector])
    run_analysis_job(job_id, provider)
    packet = next(
        json.loads(body["input"][1]["content"])
        for path, body in calls
        if path.endswith("responses")
    )
    assert {chunk["document_id"] for chunk in packet["evidence"]} == {
        str(document_id) for document_id in selected
    }


@pytest.mark.parametrize("text", [" " * 12000 + "query", "query" + " " * 12000])
def test_long_query_ignores_whitespace_only_embedding_segments(project_id, text):
    job_id = job_for(project_id, process_text=text)
    provider, _ = providers()
    run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        assert db.get(GenerationJob, job_id).status == "completed"


@pytest.mark.parametrize(
    "state",
    ["failed", "ocr_required", "pending", "deleted", "other_project", "cross_firm", "foreign_id"],
)
def test_unavailable_selected_document_blocks_before_external_processing(project_id, state):
    with SessionLocal.begin() as db:
        item, _ = document(db, project_id, vector=None)
        selected = item.id
        if state == "deleted":
            from datetime import UTC, datetime

            item.deleted_at = datetime.now(UTC)
        elif state in {"other_project", "cross_firm"}:
            firm_id = OWNER.firm_id
            if state == "cross_firm":
                firm = Firm(name="Foreign analysis")
                db.add(firm)
                db.flush()
                firm_id = firm.id
            other = Project(firm_id=firm_id, created_by=OWNER.user_id, name="Other")
            db.add(other)
            db.flush()
            if state == "cross_firm":
                # Move the fixture's whole document ancestry, preserving FKs.
                db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == item.id))
                item.firm_id = firm_id
            item.project_id = other.id
            other_id = other.id
        elif state == "foreign_id":
            selected = uuid4()
        else:
            item.status = state
            item.ocr_required = state == "ocr_required"
    job_id = job_for(project_id, [selected])
    provider, calls = providers()
    with pytest.raises(ValueError):
        run_analysis_job(job_id, provider)
    assert calls == []
    if state in {"other_project", "cross_firm"}:
        with SessionLocal.begin() as db:
            db.execute(delete(Project).where(Project.id == other_id))
            if state == "cross_firm":
                db.execute(delete(Firm).where(Firm.id == firm_id))


def test_invalid_partial_output_never_replaces_existing_stages(project_id):
    with SessionLocal.begin() as db:
        db.add(
            ProcessStage(
                firm_id=OWNER.firm_id,
                project_id=project_id,
                position=0,
                title="Existing",
                explanation="Keep the old result",
            )
        )
    job_id = job_for(project_id)
    provider, _ = providers(invalid=True)
    from app.integrations.openai_provider import ProviderInvalidResponse

    with pytest.raises(ProviderInvalidResponse):
        run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        assert (
            db.scalar(select(ProcessStage.title).where(ProcessStage.project_id == project_id))
            == "Existing"
        )
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 0


@pytest.mark.parametrize(
    "mutation", ["delete_project", "delete_document", "cancel", "supersede", "change_chunk"]
)
def test_inflight_changes_prevent_stale_publication(project_id, mutation):
    with SessionLocal.begin() as db:
        selected, chunk = document(db, project_id, vector=None)
        selected_id, chunk_id = selected.id, chunk.id
    job_id = job_for(project_id, [selected_id])

    def change(path, body):
        if not path.endswith("responses"):
            return
        with SessionLocal.begin() as db:
            if mutation == "delete_project":
                db.execute(delete(Project).where(Project.id == project_id))
            elif mutation == "delete_document":
                db.execute(delete(Document).where(Document.id == selected_id))
            elif mutation == "change_chunk":
                db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk_id)
                    .values(content="Changed")
                )
            else:
                transition_job(db, job_id, "running", "cancelled", stage="cancelled", progress=50)
                if mutation == "supersede":
                    create_job(db, OWNER, project_id, "analysis", "b" * 64, None)

    provider, _ = providers(callback=change)
    try:
        run_analysis_job(job_id, provider)
    except ValueError:
        pass
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).where(ProcessStage.project_id == project_id)) == 0
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 0


def test_publication_failure_rolls_back_replacement_citations_version_and_completion(project_id):
    with SessionLocal.begin() as db:
        db.add(
            ProcessStage(
                firm_id=OWNER.firm_id,
                project_id=project_id,
                position=0,
                title="Existing",
                explanation="Keep",
            )
        )
    job_id = job_for(project_id)
    provider, _ = providers()

    def fail_snapshot(mapper, connection, target):
        raise RuntimeError("snapshot storage failure")

    event.listen(ProjectVersion, "before_insert", fail_snapshot)
    try:
        with pytest.raises(RuntimeError, match="snapshot"):
            run_analysis_job(job_id, provider)
    finally:
        event.remove(ProjectVersion, "before_insert", fail_snapshot)
    with SessionLocal() as db:
        assert (
            db.scalar(select(ProcessStage.title).where(ProcessStage.project_id == project_id))
            == "Existing"
        )
        assert db.get(Project, project_id).review_status == "approved"
        assert db.get(GenerationJob, job_id).status == "running"
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 0


def test_registered_task_runs_provider_chain_and_sanitizes_disabled_provider(project_id):
    job_id = job_for(project_id, claim=False)
    celery.loader.import_default_modules()
    result = celery.tasks["worker.analyze_project"].apply(args=[str(job_id)], throw=False)
    assert result.successful(), result.result
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        assert job.status == "failed"
        assert job.error_code == "job_failed"
        assert db.get(Project, project_id).processing_status == "failed"
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 0


@pytest.mark.parametrize("new_status", ["running", "completed"])
def test_old_terminal_failure_does_not_overwrite_newer_analysis_status(project_id, new_status):
    old_job_id = job_for(project_id)
    record_failure(old_job_id, "analysis", None, "job_failed", 0)
    new_job_id = job_for(project_id)
    with SessionLocal.begin() as db:
        if new_status == "completed":
            transition_job(db, new_job_id, "running", "completed", stage="completed", progress=100)
        db.get(Project, project_id).processing_status = new_status
    record_failure(old_job_id, "analysis", None, "job_failed", 0)
    with SessionLocal() as db:
        assert db.get(Project, project_id).processing_status == new_status


def test_old_failure_waiting_on_project_lock_preserves_new_queued_submission(project_id):
    old_job_id = job_for(project_id)
    record_failure(old_job_id, "analysis", None, "job_failed", 0)
    update_started = Event()
    worker_pid = None

    def observe_project_update(connection, cursor, statement, parameters, context, executemany):
        nonlocal worker_pid
        if statement.startswith("UPDATE projects"):
            worker_pid = connection.connection.driver_connection.info.backend_pid
            update_started.set()

    event.listen(worker_engine, "before_cursor_execute", observe_project_update)
    try:
        with ThreadPoolExecutor(1) as pool:
            with SessionLocal.begin() as db:
                project = db.scalar(
                    select(Project).where(Project.id == project_id).with_for_update()
                )
                project.processing_status = "queued"
                db.flush()
                new_job = create_job(db, OWNER, project_id, "analysis", "b" * 64, None)
                new_job_id = new_job.id
                # Keep the new job and queued project invisible while the old
                # failure's project UPDATE takes its READ COMMITTED snapshot.
                failure = pool.submit(record_failure, old_job_id, "analysis", None, "job_failed", 0)
                assert update_started.wait(timeout=5)
                deadline = monotonic() + 2
                while monotonic() < deadline:
                    blockers = db.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": worker_pid})
                    if blockers:
                        break
                    sleep(0.01)
                assert blockers, "Old failure did not wait on the new submission's project lock"
            # Committing releases the project lock only after its new queued
            # state and job are committed. Let the stale UPDATE resume.
            failure.result(timeout=5)
    finally:
        event.remove(worker_engine, "before_cursor_execute", observe_project_update)
    with SessionLocal() as db:
        assert db.get(GenerationJob, old_job_id).status == "failed"
        assert db.get(GenerationJob, new_job_id).status == "queued"
        assert db.get(Project, project_id).processing_status == "queued"


def test_watchdog_marks_abandoned_analysis_project_failed(project_id):
    from test_jobs import age_job, run_watchdog_for

    celery.loader.import_default_modules()
    job_id = job_for(project_id)
    with SessionLocal.begin() as db:
        db.get(Project, project_id).processing_status = "running"
    age_job(job_id)
    run_watchdog_for(project_id)
    with SessionLocal() as db:
        assert db.get(GenerationJob, job_id).status == "failed"
        assert db.get(Project, project_id).processing_status == "failed"


def test_existing_embeddings_are_reused_and_verified_source_citations_are_persisted(project_id):
    with SessionLocal.begin() as db:
        selected, _ = document(db, project_id, vector=[0.0, 1.0] + [0.0] * 1534)
        _, chunk = source(db, project_id=project_id)
        selected_id, chunk_id = selected.id, chunk.id
    job_id = job_for(project_id, [selected_id])
    provider, calls = providers()
    run_analysis_job(job_id, provider)
    with SessionLocal() as db:
        stage = db.scalar(select(ProcessStage).where(ProcessStage.project_id == project_id))
        assert stage.verification_status == "supported"
        citation = db.scalar(select(StageCitation).where(StageCitation.stage_id == stage.id))
        assert citation.source_chunk_id == chunk_id
        assert citation.document_chunk_id is None
        assert citation.validation_status == "supported"
    assert [body["input"] for path, body in calls if path.endswith("embeddings")] == [
        ["Explain filing"]
    ]


@pytest.mark.parametrize(
    "status,attempts,retries", [(429, 4, 3), (503, 4, 3), (401, 1, 0), (400, 1, 0)]
)
@pytest.mark.parametrize("failure_stage", ["embeddings", "responses"])
def test_registered_task_retries_only_typed_transient_provider_failures(
    project_id, monkeypatch, status, attempts, retries, failure_stage
):
    import worker.tasks.analysis as task_module

    celery.loader.import_default_modules()
    job_id = job_for(project_id, claim=False)
    calls = []

    def handler(request):
        if not request.url.path.endswith(failure_stage):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "text-embedding-3-small",
                    "data": [{"object": "embedding", "index": 0, "embedding": VECTOR}],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )
        calls.append(request)
        return httpx.Response(
            status,
            json={
                "error": {"message": "private provider marker", "type": "api_error", "code": None}
            },
        )

    config, client = settings(), sdk_client(handler)
    monkeypatch.setattr(
        task_module,
        "get_embedding_provider",
        lambda _: OpenAIEmbeddingProvider(config, client=client),
    )
    monkeypatch.setattr(
        task_module,
        "get_analysis_provider",
        lambda _: OpenAILegalAnalysisProvider(config, client=client),
    )
    result = celery.tasks["worker.analyze_project"].apply(args=[str(job_id)], throw=False)
    assert result.successful(), result.result
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        assert (job.status, job.retry_count, job.error_code) == ("failed", retries, "job_failed")
        assert db.get(Project, project_id).processing_status == "failed"
        assert "private provider marker" not in job.error_message
        assert db.scalar(select(func.count()).where(ProjectVersion.project_id == project_id)) == 0
    assert len(calls) == attempts
