from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

from app.models.entities import SourceType
from app.services.acquisition_types import CollectionError, FetchResponse

USER_AGENT = "FlowTracer-Alpha/0.1 (+controlled-acquisition)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
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


class Transport(Protocol):
    async def __call__(
        self,
        *,
        url: str,
        connect_ip: str,
        hostname: str,
        port: int,
        use_tls: bool,
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


async def _read_with_timeout(reader: asyncio.StreamReader, size: int = -1) -> bytes:
    try:
        return await asyncio.wait_for(reader.read(size), timeout=READ_TIMEOUT)
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


async def _decode_body(reader: asyncio.StreamReader, headers: dict[str, str]) -> bytes:
    decoder = _body_decoder(headers.get("content-encoding", ""))
    output = bytearray()

    def append(chunk: bytes, *, final: bool = False) -> None:
        try:
            decoded = (
                decoder.flush()
                if final and decoder
                else decoder.decompress(chunk)
                if decoder
                else chunk
            )
        except zlib.error:
            raise CollectionError("http_error", "Response decompression failed") from None
        output.extend(decoded)
        if len(output) > MAX_RESPONSE_BYTES:
            raise CollectionError("response_too_large", "Response exceeds 5 MiB")

    if headers.get("transfer-encoding", "").lower() == "chunked":
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
            try:
                length = int(line.split(b";", 1)[0].strip(), 16)
            except ValueError:
                raise CollectionError("http_error", "Malformed chunked response") from None
            if length == 0:
                await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
                break
            chunk = await asyncio.wait_for(reader.readexactly(length), timeout=READ_TIMEOUT)
            await asyncio.wait_for(reader.readexactly(2), timeout=READ_TIMEOUT)
            append(chunk)
    else:
        while chunk := await _read_with_timeout(reader, 64 * 1024):
            append(chunk)
    append(b"", final=True)
    return bytes(output)


async def default_transport(
    *, url: str, connect_ip: str, hostname: str, port: int, use_tls: bool
) -> WireResponse:
    context = ssl.create_default_context() if use_tls else None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                connect_ip,
                port,
                ssl=context,
                server_hostname=hostname if use_tls else None,
            ),
            timeout=CONNECT_TIMEOUT,
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
                reader.readuntil(b"\r\n\r\n"), timeout=READ_TIMEOUT
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
        body = await _decode_body(reader, headers)
        return WireResponse(status_code=status_code, headers=headers, body=body)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


class SafeFetcher:
    def __init__(
        self, resolver: Resolver = system_resolver, transport: Transport = default_transport
    ) -> None:
        self._resolver = resolver
        self._transport = transport

    async def fetch(self, url: str, source_type: SourceType) -> FetchResponse:
        current_url = url
        try:
            async with asyncio.timeout(TOTAL_TIMEOUT):
                for redirect_count in range(MAX_REDIRECTS + 1):
                    hostname, port, use_tls, addresses = await validate_target(
                        current_url, self._resolver
                    )
                    response = await self._transport(
                        url=current_url,
                        connect_ip=addresses[0],
                        hostname=hostname,
                        port=port,
                        use_tls=use_tls,
                    )
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise CollectionError("http_error", "Redirect is missing Location")
                        if redirect_count == MAX_REDIRECTS:
                            raise CollectionError("http_error", "Too many redirects")
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code < 200 or response.status_code >= 300:
                        retryable = (
                            response.status_code in {408, 429} or response.status_code >= 500
                        )
                        raise CollectionError(
                            "http_error", "Upstream HTTP request failed", retryable=retryable
                        )
                    media_type = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    allowed = _RSS_TYPES if source_type == SourceType.RSS else _HTML_TYPES
                    if media_type not in allowed:
                        raise CollectionError(
                            "unsupported_content_type", "Response Content-Type is not supported"
                        )
                    return FetchResponse(
                        final_url=current_url,
                        content_type=response.headers.get("content-type", media_type)[:160],
                        body=response.body,
                        status_code=response.status_code,
                    )
        except TimeoutError:
            raise CollectionError(
                "request_timeout", "Request exceeded total timeout", retryable=True
            ) from None
        raise CollectionError("http_error", "Collection request did not complete")


Sleep = Callable[[float], Awaitable[None]]


async def fetch_with_retries(
    fetcher: SafeFetcher,
    url: str,
    source_type: SourceType,
    *,
    sleep: Sleep = asyncio.sleep,
) -> tuple[FetchResponse, int]:
    retries = 0
    while True:
        try:
            return await fetcher.fetch(url, source_type), retries
        except CollectionError as exc:
            if not exc.retryable or retries >= 3:
                raise
            await sleep(2 ** (retries + 1))
            retries += 1
