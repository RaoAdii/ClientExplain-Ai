"""Local, bounded extraction. No document bytes are sent to external providers."""

import unicodedata
from dataclasses import dataclass, field
from io import BytesIO
from zipfile import ZipFile

import pymupdf
from celery.exceptions import SoftTimeLimitExceeded
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

PARSER_VERSION = "2"
MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
MAX_PAGES = 1000
MAX_DOCX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_DOCX_ENTRIES = 2000
OCR_MESSAGE = "This PDF contains pages without readable text. Run OCR and upload a searchable PDF."


class DocumentParseError(ValueError):
    """Only fixed, client-safe messages belong in this exception."""


@dataclass(frozen=True)
class ExtractedHeading:
    text: str
    char_start: int
    char_end: int
    level: int = 1


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str
    headings: list[ExtractedHeading] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    pages: list[ExtractedPage]
    metadata: dict = field(default_factory=dict)
    headings: list[ExtractedHeading] = field(default_factory=list)
    ocr_required: bool = False


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Keep typography, punctuation, case and spacing in legal quotations intact.
    return "".join(
        " " if char in "\v\f" else char
        for char in text
        if char in "\n\t\v\f" or unicodedata.category(char) != "Cc"
    )


def _check_text_size(size: int) -> None:
    if size > MAX_TEXT_CHARS:
        raise DocumentParseError(
            "The document contains too much text. Split it into smaller files."
        )


def _pdf(content: bytes) -> ExtractedDocument:
    pages = []
    size = 0
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise DocumentParseError("Upload an unlocked PDF without a password.")
            if not 1 <= pdf.page_count <= MAX_PAGES:
                raise DocumentParseError("The PDF has too many pages. Split it into smaller files.")
            for number, page in enumerate(pdf, 1):
                text = _normalize(page.get_text("text", sort=False))
                size += len(text) + (2 if pages else 0)
                _check_text_size(size)
                pages.append(ExtractedPage(number, text))
    except (DocumentParseError, SoftTimeLimitExceeded):
        raise
    except Exception:
        raise DocumentParseError(
            "The PDF could not be read. Export a new PDF and upload it."
        ) from None
    return ExtractedDocument(
        "\n\n".join(page.text for page in pages),
        pages,
        ocr_required=any(not page.text.strip() for page in pages),
    )


def _docx(content: bytes) -> ExtractedDocument:
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_DOCX_ENTRIES
                or sum(entry.file_size for entry in entries) > MAX_DOCX_EXPANDED_BYTES
            ):
                raise DocumentParseError(
                    "The DOCX expands beyond the processing limit. Split it into smaller files."
                )
            if len({entry.filename for entry in entries}) != len(entries):
                raise DocumentParseError(
                    "The DOCX package is invalid. Export a new DOCX and upload it."
                )
        document = Document(BytesIO(content))
        parts, headings = [], []
        size = 0
        # Walk physical paragraphs in XML order, including nested tables and
        # block containers. Table.rows/cells expands grid spans and aliases
        # merged cells; cell.text also omits nested tables. XML traversal visits
        # each stored paragraph once without allocating a rendered cell grid.
        for element in document.element.body.iter(qn("w:p")):
            heading_level = None
            paragraph = Paragraph(element, document)
            text = _normalize(paragraph.text)
            style = paragraph.style.name if paragraph.style else ""
            if style.startswith("Heading ") and style[8:].isdigit():
                heading_level = int(style[8:])
            if not text:
                continue
            start = size + (1 if parts else 0)
            size = start + len(text)
            _check_text_size(size)
            if heading_level is not None:
                headings.append(ExtractedHeading(text, start, size, heading_level))
            parts.append(text)
        text = "\n".join(parts)
    except (DocumentParseError, SoftTimeLimitExceeded):
        raise
    except Exception:
        raise DocumentParseError(
            "The DOCX could not be read. Export a new DOCX and upload it."
        ) from None
    if not text.strip():
        raise DocumentParseError(
            "The document has no readable text. Upload a document containing text."
        )
    # DOCX pagination depends on the rendering engine. Do not invent page numbers.
    return ExtractedDocument(text, [], headings=headings)


def parse_document_bytes(media_type: str, content: bytes) -> ExtractedDocument:
    if not content:
        raise DocumentParseError("The document is empty. Upload a document containing text.")
    if len(content) > MAX_INPUT_BYTES:
        raise DocumentParseError(
            "The document exceeds the processing limit. Split it into smaller files."
        )
    if media_type == "application/pdf":
        extracted = _pdf(content)
    elif media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        extracted = _docx(content)
    elif media_type == "text/plain":
        try:
            text = _normalize(content.decode("utf-8-sig", errors="strict"))
        except UnicodeError:
            raise DocumentParseError(
                "The text file must use UTF-8 encoding. Save it as UTF-8 and upload it."
            ) from None
        _check_text_size(len(text))
        if not text.strip():
            raise DocumentParseError("The document is empty. Upload a document containing text.")
        extracted = ExtractedDocument(text, [])
    else:
        raise DocumentParseError("Upload a PDF, DOCX, or UTF-8 text document.")
    extracted.metadata["parser_version"] = PARSER_VERSION
    return extracted
