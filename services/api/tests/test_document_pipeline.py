import hashlib
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
import pytest
from app.core.auth import DEV_FIRM, DEV_USER, Principal
from app.db.session import SessionLocal
from app.integrations.storage import LocalPrivateStorage
from app.models.entities import Document, DocumentChunk, GenerationJob, Project
from app.schemas.auth import Role
from app.services.jobs import create_job
from celery.exceptions import SoftTimeLimitExceeded
from docx import Document as DocxDocument
from sqlalchemy import delete, event, select
from worker.celery_app import app as celery
from worker.pipelines.chunking import chunk_document
from worker.pipelines.documents import DocumentParseError, parse_document_bytes

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OWNER = Principal(DEV_USER, DEV_FIRM, Role.OWNER)


def pdf_bytes(*texts):
    with pymupdf.open() as pdf:
        for text in texts:
            page = pdf.new_page()
            if text:
                page.insert_text((72, 72), text)
        return pdf.tobytes()


def docx_bytes():
    doc = DocxDocument()
    doc.add_heading("Liability", level=1)
    doc.add_paragraph('The party "shall" pay $5,000. ' * 20)
    doc.add_heading("Remedies", level=2)
    doc.add_paragraph("No waiver applies.")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Term"
    table.cell(0, 1).text = "30 days"
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def test_pdf_preserves_ordered_pages_and_exact_quotes():
    extracted = parse_document_bytes(PDF, pdf_bytes('The party "shall" pay.', "Second page."))
    assert [page.number for page in extracted.pages] == [1, 2]
    assert extracted.pages[0].text.strip() == 'The party "shall" pay.'
    assert extracted.pages[1].text.strip() == "Second page."
    assert extracted.text.index("shall") < extracted.text.index("Second")
    assert not extracted.ocr_required


def test_docx_preserves_heading_offsets_and_table_order():
    extracted = parse_document_bytes(DOCX, docx_bytes())
    assert [heading.text for heading in extracted.headings] == ["Liability", "Remedies"]
    for heading in extracted.headings:
        assert extracted.text[heading.char_start : heading.char_end] == heading.text
    assert '"shall" pay $5,000.' in extracted.text
    assert extracted.text.index("No waiver") < extracted.text.index("Term")
    assert "30 days" in extracted.text


def test_txt_decodes_bom_and_normalizes_controls_without_rewriting_legal_text():
    extracted = parse_document_bytes("text/plain", "\ufeff“Shall”\r\n§ 2\t$5\x00\x0bpaid".encode())
    assert extracted.text == "“Shall”\n§ 2\t$5 paid"


@pytest.mark.parametrize("content", [b"", b" \r\n\t", b"\xffnot utf8"])
def test_empty_or_undecodable_txt_is_rejected(content):
    with pytest.raises(DocumentParseError):
        parse_document_bytes("text/plain", content)


def test_corrupt_pdf_has_safe_actionable_error():
    with pytest.raises(DocumentParseError) as error:
        parse_document_bytes(PDF, b"%PDF-private-corrupt-client-marker")
    assert "private-corrupt" not in str(error.value)
    assert "PDF" in str(error.value)


@pytest.mark.parametrize("texts", [("",), ("Readable page", "")])
def test_any_pdf_page_without_text_requires_ocr(texts):
    extracted = parse_document_bytes(PDF, pdf_bytes(*texts))
    assert extracted.ocr_required
    assert len(extracted.pages) == len(texts)
    assert chunk_document(extracted) == []


def test_chunk_offsets_overlap_filename_and_page_boundaries():
    extracted = parse_document_bytes(PDF, pdf_bytes("0123456789" * 8, "abcdefghij" * 8))
    extracted.metadata["filename"] = "contract.pdf"
    chunks = chunk_document(extracted, target_chars=30, overlap_chars=10)
    assert [chunk.position for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    for chunk in chunks:
        assert chunk.content == extracted.text[chunk.char_start : chunk.char_end]
        assert len(chunk.content) <= 30
        assert chunk.source_filename == "contract.pdf"
    for left, right in zip(chunks, chunks[1:], strict=False):
        assert right.char_start > left.char_start
        if left.page_number == right.page_number:
            assert left.content[-10:] == right.content[:10]


def test_docx_chunks_keep_active_heading():
    extracted = parse_document_bytes(DOCX, docx_bytes())
    chunks = chunk_document(extracted, target_chars=100, overlap_chars=20)
    assert chunks[0].heading == "Liability"
    assert next(chunk for chunk in chunks if "No waiver" in chunk.content).heading == "Remedies"
    assert {chunk.heading for chunk in chunks} == {"Liability", "Remedies"}


@pytest.mark.parametrize("target,overlap", [(0, 0), (20, -1), (20, 20), (True, 0)])
def test_chunking_rejects_nonprogressing_bounds(target, overlap):
    extracted = parse_document_bytes("text/plain", b"Legal text")
    with pytest.raises(ValueError):
        chunk_document(extracted, target_chars=target, overlap_chars=overlap)


def test_large_text_and_pdf_page_count_are_bounded(monkeypatch):
    import worker.pipelines.documents as parsers

    monkeypatch.setattr(parsers, "MAX_TEXT_CHARS", 20)
    with pytest.raises(DocumentParseError):
        parse_document_bytes("text/plain", b"x" * 21)
    monkeypatch.setattr(parsers, "MAX_PAGES", 1)
    with pytest.raises(DocumentParseError):
        parse_document_bytes(PDF, pdf_bytes("one", "two"))


def test_docx_expansion_and_input_bytes_are_bounded(monkeypatch):
    import worker.pipelines.documents as parsers

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "x" * 1025)
    monkeypatch.setattr(parsers, "MAX_DOCX_EXPANDED_BYTES", 1024)
    with pytest.raises(DocumentParseError):
        parse_document_bytes(DOCX, output.getvalue())
    monkeypatch.setattr(parsers, "MAX_INPUT_BYTES", 10)
    with pytest.raises(DocumentParseError):
        parse_document_bytes("text/plain", b"x" * 11)


@pytest.mark.parametrize("media_type,content", [(PDF, b"%PDF-"), (DOCX, docx_bytes())])
def test_parser_never_turns_worker_deadline_into_a_document_failure(
    monkeypatch, media_type, content
):
    import worker.pipelines.documents as parsers

    def deadline(*args, **kwargs):
        raise SoftTimeLimitExceeded()

    if media_type == PDF:
        monkeypatch.setattr(parsers.pymupdf, "open", deadline)
    else:
        monkeypatch.setattr(parsers, "Document", deadline)
    with pytest.raises(SoftTimeLimitExceeded):
        parse_document_bytes(media_type, content)


@pytest.fixture
def stored_document(tmp_path, monkeypatch):
    import worker.tasks.documents as tasks

    storage = LocalPrivateStorage(tmp_path)
    monkeypatch.setattr(tasks, "get_storage", lambda: storage)
    with SessionLocal.begin() as db:
        project = Project(firm_id=DEV_FIRM, created_by=DEV_USER, name="Parser test")
        db.add(project)
        db.flush()
        content = b'The party "shall" pay. ' * 400
        document = Document(
            project_id=project.id,
            firm_id=DEV_FIRM,
            filename="contract.txt",
            storage_key=str(uuid4()),
            media_type="text/plain",
            byte_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        db.add(document)
        db.flush()
        job = create_job(
            db, OWNER, project.id, "parse", document.sha256, None, document_id=document.id
        )
        ids = project.id, document.id, job.id
        storage.put(document.storage_key, BytesIO(content))
    celery.loader.import_default_modules()
    yield ids, storage
    with SessionLocal.begin() as db:
        db.execute(delete(Project).where(Project.id == ids[0]))


def run_parse(ids):
    return celery.tasks["worker.parse_document"].apply(args=[str(ids[1]), str(ids[2])], throw=True)


def test_parse_completes_and_replays_without_replacing_matching_chunks(stored_document):
    ids, storage = stored_document
    run_parse(ids)
    with SessionLocal() as db:
        doc = db.get(Document, ids[1])
        assert (doc.status, doc.ocr_required, doc.parsing_error) == ("completed", False, None)
        assert doc.document_metadata["parsed_sha256"] == doc.sha256
        assert doc.document_metadata["parser_version"]
        chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)).all()
        original_ids = {chunk.id for chunk in chunks}
        assert len(chunks) > 1 and all(chunk.source_filename == "contract.txt" for chunk in chunks)
        assert db.get(GenerationJob, ids[2]).progress == 100
    run_parse(ids)
    with SessionLocal.begin() as db:
        doc = db.get(Document, ids[1])
        storage.delete(doc.storage_key)  # A matching reparse must not reread storage.
        job = create_job(db, OWNER, ids[0], "parse", doc.sha256, None, document_id=doc.id)
    run_parse((ids[0], ids[1], job.id))
    with SessionLocal() as db:
        assert db.get(GenerationJob, job.id).status == "completed"
        assert (
            set(db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == ids[1])))
            == original_ids
        )


def test_parser_version_change_replaces_chunks_transactionally(stored_document):
    ids, _ = stored_document
    run_parse(ids)
    with SessionLocal.begin() as db:
        doc = db.get(Document, ids[1])
        old_ids = set(
            db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == doc.id))
        )
        doc.document_metadata = {**doc.document_metadata, "parser_version": "old"}
        job = create_job(db, OWNER, ids[0], "parse", doc.sha256, None, document_id=doc.id)
    run_parse((ids[0], ids[1], job.id))
    with SessionLocal() as db:
        chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == ids[1])).all()
        assert chunks and old_ids.isdisjoint(chunk.id for chunk in chunks)
        assert [chunk.position for chunk in sorted(chunks, key=lambda c: c.position)] == list(
            range(len(chunks))
        )


def test_overlapping_jobs_keep_the_first_completed_matching_chunks(stored_document, monkeypatch):
    import worker.tasks.documents as tasks

    ids, _ = stored_document
    with SessionLocal.begin() as db:
        doc = db.get(Document, ids[1])
        other = create_job(db, OWNER, ids[0], "parse", doc.sha256, None, document_id=doc.id)
    original = tasks.parse_document_bytes
    already_overlapped = False
    completed_chunks = set()

    def extract(media_type, content):
        nonlocal already_overlapped
        extracted = original(media_type, content)
        if not already_overlapped:
            already_overlapped = True
            run_parse((ids[0], ids[1], other.id))
            with SessionLocal() as db:
                completed_chunks.update(
                    db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == ids[1]))
                )
        return extracted

    monkeypatch.setattr(tasks, "parse_document_bytes", extract)
    run_parse(ids)
    with SessionLocal() as db:
        assert completed_chunks
        assert (
            set(db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == ids[1])))
            == completed_chunks
        )
        assert db.get(GenerationJob, ids[2]).status == "completed"
        assert db.get(GenerationJob, other.id).status == "completed"


@pytest.mark.parametrize("mode", ["document", "project", "cancelled"])
def test_deletion_or_cancellation_during_extraction_prevents_durable_writes(
    stored_document, monkeypatch, mode
):
    import worker.tasks.documents as tasks

    ids, _ = stored_document
    original = tasks.parse_document_bytes

    def extract(media_type, content):
        result = original(media_type, content)
        with SessionLocal.begin() as db:
            if mode == "project":
                db.execute(delete(Project).where(Project.id == ids[0]))
            elif mode == "document":
                db.get(Document, ids[1]).deleted_at = datetime.now(UTC)
            else:
                db.get(GenerationJob, ids[2]).status = "cancelled"
        return result

    monkeypatch.setattr(tasks, "parse_document_bytes", extract)
    run_parse(ids)
    with SessionLocal() as db:
        assert not db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == ids[1])
        ).all()
        doc = db.get(Document, ids[1])
        if doc:
            assert doc.status != "completed"


@pytest.mark.parametrize("case", ["scanned", "corrupt", "hash_mismatch"])
def test_parse_failures_store_safe_document_state(stored_document, case):
    ids, storage = stored_document
    content = pdf_bytes("") if case == "scanned" else b"%PDF-private-client-marker"
    with SessionLocal.begin() as db:
        doc = db.get(Document, ids[1])
        storage.delete(doc.storage_key)
        storage.put(doc.storage_key, BytesIO(content))
        doc.media_type = PDF
        doc.byte_size = len(content)
        if case != "hash_mismatch":
            doc.sha256 = hashlib.sha256(content).hexdigest()
    run_parse(ids)
    with SessionLocal() as db:
        doc = db.get(Document, ids[1])
        assert doc.status == ("ocr_required" if case == "scanned" else "failed")
        assert doc.ocr_required == (case == "scanned")
        assert doc.parsing_error and "private-client" not in doc.parsing_error
        if case == "scanned":
            assert "OCR" in doc.parsing_error
        assert db.get(GenerationJob, ids[2]).status == "failed"


def test_chunk_write_failure_rolls_back_replacement(stored_document):
    from worker.tasks import engine

    ids, _ = stored_document
    run_parse(ids)
    with SessionLocal.begin() as db:
        doc = db.get(Document, ids[1])
        original_ids = set(
            db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == doc.id))
        )
        doc.document_metadata = {**doc.document_metadata, "parser_version": "old"}
        job = create_job(db, OWNER, ids[0], "parse", doc.sha256, None, document_id=doc.id)

    def fail_chunks(conn, cursor, statement, params, context, executemany):
        if statement.startswith("INSERT INTO document_chunks"):
            raise ValueError("private-client-marker")

    event.listen(engine, "before_cursor_execute", fail_chunks)
    try:
        run_parse((ids[0], ids[1], job.id))
    finally:
        event.remove(engine, "before_cursor_execute", fail_chunks)
    with SessionLocal() as db:
        assert (
            set(db.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id == ids[1])))
            == original_ids
        )
        assert db.get(GenerationJob, job.id).status == "failed"
