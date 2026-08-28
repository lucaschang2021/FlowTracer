from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str


def chunk_text(content: str, *, size: int = 1200, overlap: int = 200) -> tuple[TextChunk, ...]:
    if not 256 <= size <= 4000:
        raise ValueError("chunk size must be between 256 and 4000")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk overlap must be between 0 and size - 1")
    if not content:
        return ()
    step = size - overlap
    chunks: list[TextChunk] = []
    for start in range(0, len(content), step):
        value = content[start : start + size]
        if value:
            chunks.append(TextChunk(len(chunks), value))
        if start + size >= len(content):
            break
    return tuple(chunks)
