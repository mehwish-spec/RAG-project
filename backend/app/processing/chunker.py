"""
Configurable text chunking.

Splitting strategy, in order of preference, so we avoid cutting a chunk
mid-sentence whenever possible:

    paragraph  ->  sentence  ->  hard character limit

Each produced chunk respects `chunk_size` (target max characters) with
`chunk_overlap` characters of overlap carried into the next chunk for
context continuity, and is never smaller than `min_chunk_size` (unless
it's the only content available) nor larger than `max_chunk_size`.
"""
import re
from dataclasses import dataclass, field
from typing import Any

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class ChunkConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150
    min_chunk_size: int = 50
    max_chunk_size: int = 2000


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _split_sentences(paragraph: str) -> list[str]:
    sentences = _SENTENCE_SPLIT_RE.split(paragraph.strip())
    return [s.strip() for s in sentences if s.strip()]


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _hard_split(unit: str, max_size: int) -> list[str]:
    """Last-resort split for a single sentence/paragraph longer than max_size."""
    words = unit.split(" ")
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_size and current:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_text(
    text: str,
    config: ChunkConfig | None = None,
    page_number: int | None = None,
    section: str | None = None,
) -> list[TextChunk]:
    """Chunk a single normalized text block (e.g. one PDF page or the whole DOCX)."""
    config = config or ChunkConfig()
    if not text or not text.strip():
        return []

    # Build a flat list of "units" (sentences), preferring paragraph boundaries.
    units: list[str] = []
    for paragraph in _split_paragraphs(text):
        if len(paragraph) <= config.max_chunk_size:
            units.append(paragraph)
            continue
        for sentence in _split_sentences(paragraph):
            if len(sentence) <= config.max_chunk_size:
                units.append(sentence)
            else:
                units.extend(_hard_split(sentence, config.max_chunk_size))

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if len(candidate) <= config.chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = _overlap_tail(current, config.chunk_overlap) + "\n\n" + unit
            current = current.strip()
        else:
            current = unit

        # If a single unit alone exceeds chunk_size (but is <= max_chunk_size),
        # flush it as its own chunk.
        if len(current) > config.max_chunk_size:
            chunks.append(current[: config.max_chunk_size])
            current = current[config.max_chunk_size :]

    if current.strip():
        chunks.append(current.strip())

    # Merge any trailing chunk that's smaller than min_chunk_size into the
    # previous one, unless it's the only chunk or merging would push the
    # previous chunk over the configured maximum size.
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < config.min_chunk_size and len(merged[-1]) + len(c) + 2 <= config.max_chunk_size:
            merged[-1] = f"{merged[-1]}\n\n{c}".strip()
        else:
            merged.append(c)

    return [
        TextChunk(content=c, chunk_index=i, page_number=page_number, section=section)
        for i, c in enumerate(merged)
    ]


def _overlap_tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return text
    return text[-overlap:]
