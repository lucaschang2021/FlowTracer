from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.models.entities import (
    Analysis,
    AnalysisStatus,
    Document,
    DocumentStatus,
    Radar,
    RadarSource,
    RawItem,
    RawItemStatus,
    ResourceStatus,
)

MAX_CLEANED_CONTENT_BYTES = 5 * 1024 * 1024
PIPELINE_VERSION = "alpha-v1"
PROMPT_VERSION = "intelligence-v1"

_INLINE_WHITESPACE = re.compile(r"[^\S\n]+", re.UNICODE)
_EXCESS_BLANK_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")


class AnalysisDispatch(Protocol):
    def __call__(self, raw_item_id: str, correlation_id: str) -> None: ...


@dataclass(frozen=True)
class CleaningResult:
    document_id: UUID | None
    analysis_ids: tuple[UUID, ...]
    duplicate: bool


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    safe = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or not (ord(character) < 32 or 127 <= ord(character) <= 159)
    )
    lines = [_INLINE_WHITESPACE.sub(" ", line).strip() for line in safe.split("\n")]
    collapsed = "\n".join(lines).strip()
    return _EXCESS_BLANK_LINES.sub("\n\n", collapsed)


def count_words(value: str) -> int:
    count = 0
    in_word = False
    for character in value:
        codepoint = ord(character)
        is_cjk = (
            0x3400 <= codepoint <= 0x4DBF
            or 0x4E00 <= codepoint <= 0x9FFF
            or 0xF900 <= codepoint <= 0xFAFF
            or 0x20000 <= codepoint <= 0x2FA1F
        )
        if is_cjk:
            count += 1
            in_word = False
        elif character.isalpha() or character.isdigit():
            if not in_word:
                count += 1
            in_word = True
        else:
            in_word = False
    return count


def _advisory_key(content_hash: str) -> int:
    return int.from_bytes(bytes.fromhex(content_hash[:16]), "big", signed=True)


async def _set_raw_failure(session: AsyncSession, raw: RawItem, code: str, message: str) -> None:
    raw.status = RawItemStatus.FAILED
    raw.error_code = code
    raw.error_message = message[:500]
    await session.commit()


async def clean_raw_item(
    factory: async_sessionmaker[AsyncSession], raw_item_id: UUID
) -> CleaningResult:
    async with factory() as session:
        raw = await session.scalar(
            select(RawItem).where(RawItem.id == raw_item_id).with_for_update()
        )
        if raw is None or raw.status != RawItemStatus.FETCHED:
            await session.rollback()
            return CleaningResult(None, (), False)
        content = clean_text(raw.raw_text)
        if not content:
            await _set_raw_failure(session, raw, "empty_content", "Cleaned content is empty")
            return CleaningResult(None, (), False)
        if len(content.encode("utf-8")) > MAX_CLEANED_CONTENT_BYTES:
            await _set_raw_failure(
                session,
                raw,
                "cleaned_content_too_large",
                "Cleaned content exceeds the allowed size",
            )
            return CleaningResult(None, (), False)

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_key(content_hash)}
        )
        document = await session.scalar(
            select(Document).where(Document.content_hash == content_hash).with_for_update()
        )
        duplicate = document is not None
        if document is None:
            cleaned_title = clean_text(raw.title or "") or raw.canonical_url
            author_value = raw.item_metadata.get("author")
            author = clean_text(author_value)[:300] if isinstance(author_value, str) else None
            document = Document(
                raw_item_id=raw.id,
                canonical_url=raw.canonical_url,
                title=cleaned_title,
                author=author or None,
                language=None,
                content=content,
                word_count=count_words(content),
                content_hash=content_hash,
                status=DocumentStatus.PENDING,
            )
            session.add(document)
            await session.flush()
            document.status = DocumentStatus.CLEANING
            await session.flush()
            document.status = DocumentStatus.DEDUPLICATING
            raw.status = RawItemStatus.CLEANED
        else:
            raw.status = RawItemStatus.DUPLICATE
        raw.error_code = None
        raw.error_message = None

        radar_ids = list(
            (
                await session.scalars(
                    select(Radar.id)
                    .join(RadarSource, RadarSource.radar_id == Radar.id)
                    .where(
                        RadarSource.source_id == raw.source_id,
                        Radar.status == ResourceStatus.ACTIVE,
                        Radar.deleted_at.is_(None),
                    )
                    .order_by(Radar.id)
                )
            ).all()
        )
        if radar_ids:
            await session.execute(
                insert(Analysis)
                .values(
                    [
                        {
                            "document_id": document.id,
                            "radar_id": radar_id,
                            "pipeline_version": PIPELINE_VERSION,
                            "prompt_version": PROMPT_VERSION,
                            "status": AnalysisStatus.PENDING,
                        }
                        for radar_id in radar_ids
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        Analysis.document_id,
                        Analysis.radar_id,
                        Analysis.pipeline_version,
                    ]
                )
            )
        pending_ids = tuple(
            (
                await session.scalars(
                    select(Analysis.id).where(
                        Analysis.document_id == document.id,
                        Analysis.pipeline_version == PIPELINE_VERSION,
                        Analysis.status == AnalysisStatus.PENDING,
                    )
                )
            ).all()
        )
        statuses = list(
            (
                await session.scalars(
                    select(Analysis.status).where(
                        Analysis.document_id == document.id,
                        Analysis.pipeline_version == PIPELINE_VERSION,
                    )
                )
            ).all()
        )
        if any(status in {AnalysisStatus.PENDING, AnalysisStatus.RUNNING} for status in statuses):
            document.status = DocumentStatus.ANALYZING
            document.error_code = None
            document.error_message = None
        elif not statuses or AnalysisStatus.COMPLETED in statuses:
            document.status = DocumentStatus.EMBEDDING
            document.error_code = None
            document.error_message = None
        else:
            document.status = DocumentStatus.FAILED
            document.error_code = "internal_analysis_error"
            document.error_message = "All analyses failed"
        await session.commit()
        return CleaningResult(document.id, pending_ids, duplicate)


async def dispatch_fetched_raw_items(
    factory: async_sessionmaker[AsyncSession],
    dispatch: AnalysisDispatch,
    *,
    batch_size: int = 100,
) -> int:
    async with factory() as session:
        raw_ids = list(
            (
                await session.scalars(
                    select(RawItem.id)
                    .where(RawItem.status == RawItemStatus.FETCHED)
                    .order_by(RawItem.created_at.asc(), RawItem.id.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
        )
        dispatched = 0
        for raw_id in raw_ids:
            try:
                dispatch(str(raw_id), str(raw_id))
            except Exception as exc:
                get_logger().warning(
                    "cleaning_queue_unavailable",
                    message="Cleaning queue is temporarily unavailable",
                    raw_item_id=str(raw_id),
                    exception_type=type(exc).__name__,
                )
                continue
            dispatched += 1
        await session.commit()
        return dispatched
