from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
import time
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

from app.models.entities import SourceType
from app.services.acquisition_types import AcquisitionFetcher, CollectionError, FetchResponse

USER_AGENT = "FlowTracer-Alpha/0.1 (+controlled-acquisition)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_WIRE_BYTES = 10 * 1024 * 1024
WIRE_READ_CHUNK = 64 * 1024
MAX_REDIRECTS = 5
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 15.0
TOTAL_TIMEOUT = 30.0
_METADATA_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.google",
        "instance-data",
        "instance-data.ec2.internal",
        "metadata.azure.internal",
    }
)
_RSS_TYPES = frozenset(
    {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}
)
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})


class Resolver(Protocol):
    async def __call__(self, hostname: str) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class WireResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


@dataclass(slots=True)
class FetchSession:
    """Mutable per-fetch accounting: real requests (hops + retries) and remaining budget.

    ``max_requests``/``max_bytes`` bound the *whole* fetch chain (initial request,
    every redirect hop, every retry), and ``deadline_monotonic`` is the run-level
    absolute deadline. Checks happen *before* issuing the next request and while
    reading the body, so a budget is enforced during execution instead of being
    discovered after a full response was fetched.
    """

    max_requests: int | None = None
    max_bytes: int | None = None
    deadline_monotonic: float | None = None
    requests_made: int = 0
    redirects: int = 0
    bytes_received: int = 0

    def check(self) -> None:
        if self.max_requests is not None and self.requests_made >= self.max_requests:
            raise CollectionError("acquisition_budget_exhausted", "Request budget is exhausted")
        if self.deadline_monotonic is not None and time.monotonic() >= self.deadline_monotonic:
            raise CollectionError("acquisition_budget_exhausted", "Duration budget is exhausted")
        if self.max_bytes is not None and self.bytes_received >= self.max_bytes:
            raise CollectionError("acquisition_budget_exhausted", "Byte budget is exhausted")

    def remaining_seconds(self) -> float | None:
        if self.deadline_monotonic is None:
            return None
        return self.deadline_monotonic - time.monotonic()

    def wait_timeout(self, base: float) -> float:
        remaining = self.remaining_seconds()
        if remaining is None:
            return base
        if remaining <= 0:
            raise CollectionError("acquisition_budget_exhausted", "Duration budget is exhausted")
        return min(base, max(0.1, remaining))


class Transport(Protocol):
    async def __call__(
        self,
        *,
        url: str,
        connect_ip: str,
        hostname: str,
        port: int,
        use_tls: bool,
        session: FetchSession | None = None,
    ) -> WireResponse: ...


async def system_resolver(hostname: str) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        raise CollectionError(
            "dns_resolution_failed", "DNS resolution failed", retryable=True
        ) from None
    return sorted({str(record[4][0]) for record in records})


def _validated_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise CollectionError("dns_resolution_failed", "DNS returned an invalid address") from None
    forbidden = (
        not address.is_global
        or address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or getattr(address, "is_site_local", False)
    )
    if forbidden:
        raise CollectionError("ssrf_blocked", "Target address is not globally routable")
    return address


async def validate_target(url: str, resolver: Resolver) -> tuple[str, int, bool, list[str]]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise CollectionError("unsupported_port", "Target port is invalid") from None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or parsed.hostname is None:
        raise CollectionError("ssrf_blocked", "Only absolute HTTP(S) targets are allowed")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise CollectionError("ssrf_blocked", "Target userinfo is forbidden")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in _METADATA_HOSTS or hostname.endswith(".internal"):
        raise CollectionError("ssrf_blocked", "Metadata targets are forbidden")
    resolved_port = port if port is not None else (443 if scheme == "https" else 80)
    if resolved_port not in {80, 443}:
        raise CollectionError("unsupported_port", "Only ports 80 and 443 are allowed")
    addresses = await resolver(hostname)
    if not addresses:
        raise CollectionError(
            "dns_resolution_failed", "DNS resolution returned no addresses", retryable=True
        )
    validated = [str(_validated_ip(address)) for address in addresses]
    return hostname, resolved_port, scheme == "https", validated


async def _read_with_timeout(
    reader: asyncio.StreamReader, size: int = -1, *, session: FetchSession | None = None
) -> bytes:
    timeout = READ_TIMEOUT if session is None else session.wait_timeout(READ_TIMEOUT)
    try:
        return await asyncio.wait_for(reader.read(size), timeout=timeout)
    except TimeoutError:
        raise CollectionError(
            "request_timeout", "Response read timed out", retryable=True
        ) from None


def _body_decoder(encoding: str) -> Any:
    normalized = encoding.strip().lower()
    if normalized in {"", "identity"}:
        return None
    if normalized == "gzip":
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    if normalized == "deflate":
        return zlib.decompressobj()
    raise CollectionError("unsupported_content_type", "Unsupported response content encoding")


class _BodyReadState:
    """Budget-aware accumulation shared by the chunked and plain body readers."""

    __slots__ = ("body_cap", "budget_limited", "decoder", "output", "wire_bytes", "wire_cap")

    def __init__(self, decoder: Any, *, body_cap: int, budget_limited: bool) -> None:
        self.decoder = decoder
        self.output = bytearray()
        self.wire_bytes = 0
        self.body_cap = body_cap
        self.budget_limited = budget_limited
        self.wire_cap = (
            MAX_WIRE_BYTES
            if not budget_limited
            else min(MAX_WIRE_BYTES, body_cap + WIRE_READ_CHUNK)
        )

    def oversize(self) -> CollectionError:
        if self.budget_limited:
            return CollectionError(
                "acquisition_budget_exhausted", "Response exceeds the remaining byte budget"
            )
        return CollectionError("response_too_large", "Response exceeds 5 MiB")

    def wire_oversize(self) -> CollectionError:
        if self.budget_limited:
            return CollectionError(
                "acquisition_budget_exhausted",
                "Response wire size exceeds the remaining byte budget",
            )
        return CollectionError("response_too_large", "Response wire size is too large")

    def append(self, chunk: bytes) -> None:
        self.wire_bytes += len(chunk)
        if self.wire_bytes > self.wire_cap:
            raise self.wire_oversize()
        decoder = self.decoder
        if decoder is None:
            remaining_plus_one = self.body_cap - len(self.output) + 1
            self.output.extend(chunk[:remaining_plus_one])
            if len(self.output) > self.body_cap:
                raise self.oversize()
            return
        pending = chunk
        try:
            while pending:
                remaining_plus_one = self.body_cap - len(self.output) + 1
                decoded = decoder.decompress(pending, remaining_plus_one)
                self.output.extend(decoded)
                if len(self.output) > self.body_cap:
                    raise self.oversize()
                if decoder.unused_data:
                    raise CollectionError("http_error", "Compressed response has trailing data")
                tail = decoder.unconsumed_tail
                if tail == pending and not decoded:
                    raise CollectionError("http_error", "Response decompression made no progress")
                pending = tail
        except zlib.error:
            raise CollectionError("http_error", "Response decompression failed") from None

    def finish(self) -> bytes:
        decoder = self.decoder
        if decoder is not None:
            if not decoder.eof:
                raise CollectionError("http_error", "Compressed response is incomplete")
            try:
                flush_size = min(self.body_cap - len(self.output) + 1, WIRE_READ_CHUNK)
                flushed = decoder.flush(flush_size)
            except zlib.error:
                raise CollectionError("http_error", "Response decompression failed") from None
            self.output.extend(flushed)
            if len(self.output) > self.body_cap:
                raise self.oversize()
        return bytes(self.output)


async def _read_chunked_body(
    reader: asyncio.StreamReader, state: _BodyReadState, timeout_for: Callable[[], float]
) -> None:
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout_for())
        if len(line) > 128:
            raise CollectionError("http_error", "Malformed chunked response")
        try:
            length = int(line.split(b";", 1)[0].strip(), 16)
        except ValueError:
            raise CollectionError("http_error", "Malformed chunked response") from None
        if length == 0:
            trailer_bytes = 0
            while True:
                trailer = await asyncio.wait_for(reader.readline(), timeout=timeout_for())
                trailer_bytes += len(trailer)
                if trailer_bytes > 64 * 1024:
                    raise CollectionError("http_error", "Chunk trailers are too large")
                if trailer in {b"\r\n", b"\n", b""}:
                    break
            return
        if length < 0 or state.wire_bytes + length > state.wire_cap:
            raise state.wire_oversize()
        remaining = length
        while remaining:
            read_size = min(remaining, WIRE_READ_CHUNK)
            chunk = await asyncio.wait_for(reader.readexactly(read_size), timeout=timeout_for())
            state.append(chunk)
            remaining -= len(chunk)
        terminator = await asyncio.wait_for(reader.readexactly(2), timeout=timeout_for())
        if terminator != b"\r\n":
            raise CollectionError("http_error", "Malformed chunked response")


async def _read_plain_body(
    reader: asyncio.StreamReader,
    headers: dict[str, str],
    state: _BodyReadState,
    session: FetchSession | None,
) -> None:
    content_length = headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            raise CollectionError("http_error", "Malformed Content-Length") from None
        if declared_length < 0:
            raise CollectionError("http_error", "Malformed Content-Length")
        if declared_length > state.wire_cap:
            raise state.wire_oversize()
    while chunk := await _read_with_timeout(reader, WIRE_READ_CHUNK, session=session):
        state.append(chunk)


async def _decode_body(
    reader: asyncio.StreamReader,
    headers: dict[str, str],
    *,
    session: FetchSession | None = None,
) -> bytes:
    decoder = _body_decoder(headers.get("content-encoding", ""))
    body_cap = MAX_RESPONSE_BYTES
    budget_limited = False
    if session is not None and session.max_bytes is not None:
        remaining_bytes = session.max_bytes - session.bytes_received
        if remaining_bytes <= 0:
            raise CollectionError("acquisition_budget_exhausted", "Byte budget is exhausted")
        if remaining_bytes < MAX_RESPONSE_BYTES:
            body_cap = remaining_bytes
            budget_limited = True
    state = _BodyReadState(decoder, body_cap=body_cap, budget_limited=budget_limited)

    def timeout_for() -> float:
        return READ_TIMEOUT if session is None else session.wait_timeout(READ_TIMEOUT)

    if headers.get("transfer-encoding", "").lower() == "chunked":
        await _read_chunked_body(reader, state, timeout_for)
    else:
        await _read_plain_body(reader, headers, state, session)
    body = state.finish()
    if session is not None:
        session.bytes_received += len(body)
    return body


async def default_transport(
    *,
    url: str,
    connect_ip: str,
    hostname: str,
    port: int,
    use_tls: bool,
    session: FetchSession | None = None,
) -> WireResponse:
    context = ssl.create_default_context() if use_tls else None

    def connect_timeout() -> float:
        return CONNECT_TIMEOUT if session is None else session.wait_timeout(CONNECT_TIMEOUT)

    def transport_read_timeout() -> float:
        return READ_TIMEOUT if session is None else session.wait_timeout(READ_TIMEOUT)

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                connect_ip,
                port,
                ssl=context,
                server_hostname=hostname if use_tls else None,
            ),
            timeout=connect_timeout(),
        )
    except TimeoutError:
        raise CollectionError("request_timeout", "Connection timed out", retryable=True) from None
    except OSError:
        raise CollectionError("http_error", "Connection failed", retryable=True) from None
    try:
        parsed = urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target += f"?{parsed.query}"
        default_port = (use_tls and port == 443) or (not use_tls and port == 80)
        host_display = f"[{hostname}]" if ":" in hostname else hostname
        host_header = host_display if default_port else f"{host_display}:{port}"
        request = (
            f"GET {target} HTTP/1.1\r\nHost: {host_header}\r\nUser-Agent: {USER_AGENT}\r\n"
            "Accept: application/rss+xml, application/atom+xml, application/xml, text/xml, "
            "text/html, application/xhtml+xml\r\nAccept-Encoding: gzip, deflate\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await writer.drain()
        try:
            header_bytes = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"), timeout=transport_read_timeout()
            )
        except (asyncio.LimitOverrunError, asyncio.IncompleteReadError):
            raise CollectionError("http_error", "Malformed HTTP response") from None
        if len(header_bytes) > 64 * 1024:
            raise CollectionError("http_error", "Response headers are too large")
        lines = header_bytes.decode("iso-8859-1").split("\r\n")
        try:
            status_code = int(lines[0].split(" ", 2)[1])
        except (IndexError, ValueError):
            raise CollectionError("http_error", "Malformed HTTP status") from None
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line:
                continue
            name, separator, value = line.partition(":")
            if not separator:
                raise CollectionError("http_error", "Malformed HTTP header")
            headers[name.strip().lower()] = value.strip()
        body = await _decode_body(reader, headers, session=session)
        return WireResponse(status_code=status_code, headers=headers, body=body)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


def _allowed_content_types(
    source_type: SourceType, override: frozenset[str] | None
) -> frozenset[str]:
    if override is not None:
        return override
    return _RSS_TYPES if source_type == SourceType.RSS else _HTML_TYPES


def _accepted_response(
    response: WireResponse,
    allowed_types: frozenset[str],
    *,
    final_url: str,
    redirects: int,
) -> FetchResponse:
    """Validate the terminal response content type and build the fetch outcome."""
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in allowed_types:
        raise CollectionError("unsupported_content_type", "Response Content-Type is not supported")
    return FetchResponse(
        final_url=final_url,
        content_type=response.headers.get("content-type", media_type)[:160],
        body=response.body,
        status_code=response.status_code,
        redirects=redirects,
    )


class SafeFetcher:
    def __init__(
        self,
        resolver: Resolver = system_resolver,
        transport: Transport = default_transport,
        target_validator: Callable[[str], None] | None = None,
    ) -> None:
        self._resolver = resolver
        self._transport = transport
        self._target_validator = target_validator

    def with_target_validator(self, validator: Callable[[str], None]) -> SafeFetcher:
        existing = self._target_validator

        def combined(url: str) -> None:
            if existing is not None:
                existing(url)
            validator(url)

        return SafeFetcher(
            resolver=self._resolver,
            transport=self._transport,
            target_validator=combined,
        )

    async def fetch(
        self,
        url: str,
        source_type: SourceType,
        *,
        session: FetchSession | None = None,
        content_types: frozenset[str] | None = None,
    ) -> FetchResponse:
        """Fetch one URL; ``content_types`` overrides the default allowed set
        (robots.txt), with the safety pipeline unchanged."""
        if session is None:
            session = FetchSession()
        allowed_types = _allowed_content_types(source_type, content_types)
        current_url = url
        total_timeout = TOTAL_TIMEOUT
        remaining = session.remaining_seconds()
        if remaining is not None:
            if remaining <= 0:
                raise CollectionError(
                    "acquisition_budget_exhausted", "Duration budget is exhausted"
                )
            total_timeout = min(TOTAL_TIMEOUT, remaining)
        try:
            async with asyncio.timeout(total_timeout):
                for redirect_count in range(MAX_REDIRECTS + 1):
                    # Budget is checked *before* every issued request: hops, retries
                    # and the initial request each consume one request credit.
                    session.check()
                    if self._target_validator is not None:
                        self._target_validator(current_url)
                    hostname, port, use_tls, addresses = await validate_target(
                        current_url, self._resolver
                    )
                    session.requests_made += 1
                    response = await self._transport(
                        url=current_url,
                        connect_ip=addresses[0],
                        hostname=hostname,
                        port=port,
                        use_tls=use_tls,
                        session=session,
                    )
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise CollectionError("http_error", "Redirect is missing Location")
                        if redirect_count == MAX_REDIRECTS:
                            raise CollectionError("http_error", "Too many redirects")
                        session.redirects += 1
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code < 200 or response.status_code >= 300:
                        retryable = (
                            response.status_code in {408, 429} or response.status_code >= 500
                        )
                        raise CollectionError(
                            "http_error",
                            "Upstream HTTP request failed",
                            retryable=retryable,
                            status_code=response.status_code,
                        )
                    return _accepted_response(
                        response,
                        allowed_types,
                        final_url=current_url,
                        redirects=session.redirects,
                    )
        except TimeoutError:
            deadline = session.deadline_monotonic
            if deadline is not None and time.monotonic() >= deadline - 0.05:
                raise CollectionError(
                    "acquisition_budget_exhausted", "Duration budget is exhausted"
                ) from None
            raise CollectionError(
                "request_timeout", "Request exceeded total timeout", retryable=True
            ) from None
        raise CollectionError("http_error", "Collection request did not complete")


Sleep = Callable[[float], Awaitable[None]]


async def fetch_with_retries(
    fetcher: AcquisitionFetcher,
    url: str,
    source_type: SourceType,
    *,
    sleep: Sleep = asyncio.sleep,
    max_retries: int = 3,
    session: FetchSession | None = None,
    min_delay: float = 0.0,
    content_types: frozenset[str] | None = None,
) -> tuple[FetchResponse, int]:
    if session is None:
        session = FetchSession()
    retries = 0
    while True:
        try:
            if isinstance(fetcher, SafeFetcher):
                response = await fetcher.fetch(
                    url, source_type, session=session, content_types=content_types
                )
            else:
                response = await fetcher.fetch(url, source_type)
            return response, retries
        except CollectionError as exc:
            if exc.requests_made is None and session.requests_made:
                exc.requests_made = session.requests_made
            if not exc.retryable or retries >= max_retries:
                exc.retry_count = retries
                raise
            # A retry is itself a real request: it waits at least the site's
            # crawl-delay / RPM spacing floor, or the exponential backoff if longer.
            delay = max(2 ** (retries + 1), min_delay)
            remaining = session.remaining_seconds()
            if remaining is not None and remaining <= delay:
                raise CollectionError(
                    "acquisition_budget_exhausted",
                    "Duration budget cannot cover another retry",
                ) from None
            await sleep(delay)
            retries += 1
