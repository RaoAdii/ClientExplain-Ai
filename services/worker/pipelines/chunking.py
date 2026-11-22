"""Deterministic character windows with offsets into the extracted text."""

from dataclasses import dataclass

from worker.pipelines.documents import ExtractedDocument

MAX_CHUNKS = 20_000


@dataclass(frozen=True)
class DocumentChunkInput:
    position: int
    content: str
    page_number: int | None
    heading: str | None
    source_filename: str | None
    char_start: int
    char_end: int


def chunk_document(
    extracted: ExtractedDocument,
    *,
    target_chars: int = 2400,
    overlap_chars: int = 300,
) -> list[DocumentChunkInput]:
    if (
        type(target_chars) is not int
        or type(overlap_chars) is not int
        or target_chars <= 0
        or not 0 <= overlap_chars < target_chars
    ):
        raise ValueError("Chunk size must be positive and overlap smaller than chunk size.")
    if extracted.ocr_required:
        return []
    chunks = []
    page_ranges = []
    offset = 0
    for page in extracted.pages:
        page_ranges.append((offset, offset + len(page.text), page.number))
        offset += len(page.text) + 2
    if not page_ranges:
        page_ranges = [(0, len(extracted.text), None)]
    headings = sorted(extracted.headings, key=lambda heading: heading.char_start)
    for page_start, page_end, page_number in page_ranges:
        boundaries = (
            [page_start]
            + [h.char_start for h in headings if page_start < h.char_start < page_end]
            + [page_end]
        )
        for section_start, section_end in zip(boundaries, boundaries[1:], strict=False):
            heading = next(
                (h.text for h in reversed(headings) if h.char_start <= section_start), None
            )
            start = section_start
            while start < section_end:
                end = min(start + target_chars, section_end)
                content = extracted.text[start:end]
                if content.strip():
                    if len(chunks) >= MAX_CHUNKS:
                        raise ValueError(
                            "The document produces too many chunks. Split it into smaller files."
                        )
                    chunks.append(
                        DocumentChunkInput(
                            len(chunks),
                            content,
                            page_number,
                            heading,
                            extracted.metadata.get("filename"),
                            start,
                            end,
                        )
                    )
                if end == section_end:
                    break
                start = end - overlap_chars
    return chunks
