from __future__ import annotations

import asyncio
import gzip

import pytest

from app.models.entities import SourceType
from app.services.acquisition_types import CollectionError
from app.services.safe_fetcher import (
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    SafeFetcher,
    WireResponse,
    _decode_body,
    default_transport,
    fetch_with_retries,
    validate_target,
)

PUBLIC_V4 = "93.184.216.34"


async def public_resolver(_hostname: str) -> list[str]:
    return [PUBLIC_V4]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",  # noqa: S104 - an explicit SSRF rejection test vector
        "::1",
        "fc00::1",
        "fe80::1",
        "ff00::1",
        "::",
        "fec0::1",
        "169.254.169.254",
    ],
)
async def test_validate_target_rejects_non_global_address_classes(address: str) -> None:
    async def resolver(_hostname: str) -> list[str]:
        return [address]

    with pytest.raises(CollectionError, match="globally routable") as raised:
        await validate_target("https://example.com/feed", resolver)
    assert raised.value.code == "ssrf_blocked"
    assert not raised.value.retryable


@pytest.mark.asyncio
async def test_validate_target_rejects_mixed_dns_answers_and_metadata_hosts() -> None:
    async def mixed(_hostname: str) -> list[str]:
        return [PUBLIC_V4, "10.0.0.1"]

    with pytest.raises(CollectionError) as mixed_error:
        await validate_target("https://example.com", mixed)
    assert mixed_error.value.code == "ssrf_blocked"

    with pytest.raises(CollectionError) as metadata_error:
        await validate_target("http://metadata.google.internal/", public_resolver)
    assert metadata_error.value.code == "ssrf_blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("ftp://example.com/file", "ssrf_blocked"),
        ("https://user@example.com/", "ssrf_blocked"),
        ("https://example.com:8443/", "unsupported_port"),
        ("https://example.com:invalid/", "unsupported_port"),
    ],
)
async def test_validate_target_rejects_protocol_userinfo_and_ports(url: str, code: str) -> None:
    with pytest.raises(CollectionError) as raised:
        await validate_target(url, public_resolver)
    assert raised.value.code == code


@pytest.mark.asyncio
async def test_redirect_is_revalidated_and_connection_uses_validated_ip() -> None:
    resolutions = iter([[PUBLIC_V4], ["10.0.0.8"]])
    connected: list[tuple[str, str]] = []

    async def resolver(_hostname: str) -> list[str]:
        return next(resolutions)

    async def transport(**kwargs: object) -> WireResponse:
        connected.append((str(kwargs["connect_ip"]), str(kwargs["hostname"])))
        return WireResponse(302, {"location": "https://redirect.example/final"}, b"")

    with pytest.raises(CollectionError) as raised:
        await SafeFetcher(resolver=resolver, transport=transport).fetch(
            "https://example.com/start", SourceType.URL
        )
    assert raised.value.code == "ssrf_blocked"
    assert connected == [(PUBLIC_V4, "example.com")]


@pytest.mark.asyncio
async def test_content_type_redirect_limit_and_http_retry_classification() -> None:
    responses = iter(
        [
            WireResponse(200, {"content-type": "application/json"}, b"{}"),
            WireResponse(404, {"content-type": "text/html"}, b"missing"),
            WireResponse(503, {"content-type": "text/html"}, b"later"),
        ]
    )

    async def transport(**_kwargs: object) -> WireResponse:
        return next(responses)

    fetcher = SafeFetcher(resolver=public_resolver, transport=transport)
    with pytest.raises(CollectionError) as content_type:
        await fetcher.fetch("https://example.com", SourceType.URL)
    assert content_type.value.code == "unsupported_content_type"
    with pytest.raises(CollectionError) as not_found:
        await fetcher.fetch("https://example.com", SourceType.URL)
    assert not not_found.value.retryable
    with pytest.raises(CollectionError) as unavailable:
        await fetcher.fetch("https://example.com", SourceType.URL)
    assert unavailable.value.retryable


@pytest.mark.asyncio
@pytest.mark.parametrize("compressed", [False, True])
async def test_decoded_body_limit_applies_after_decompression(compressed: bool) -> None:
    body = b"x" * (MAX_RESPONSE_BYTES + 1)
    headers: dict[str, str] = {}
    if compressed:
        body = gzip.compress(body)
        headers["content-encoding"] = "gzip"
    reader = asyncio.StreamReader()
    reader.feed_data(body)
    reader.feed_eof()
    with pytest.raises(CollectionError) as raised:
        await _decode_body(reader, headers)
    assert raised.value.code == "response_too_large"


@pytest.mark.asyncio
async def test_decoded_body_accepts_exact_five_mib_boundary() -> None:
    body = b"x" * MAX_RESPONSE_BYTES
    reader = asyncio.StreamReader()
    reader.feed_data(body)
    reader.feed_eof()
    assert await _decode_body(reader, {}) == body


@pytest.mark.asyncio
async def test_transient_retries_use_frozen_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    class FlakyFetcher:
        async def fetch(self, _url: str, _source_type: SourceType) -> object:
            nonlocal attempts
            attempts += 1
            raise CollectionError("request_timeout", "safe timeout", retryable=True)

    async def sleep(delay: float) -> None:
        delays.append(delay)

    with pytest.raises(CollectionError):
        await fetch_with_retries(
            FlakyFetcher(),  # type: ignore[arg-type]
            "https://example.com",
            SourceType.URL,
            sleep=sleep,
        )
    assert attempts == 4
    assert delays == [2, 4, 8]


@pytest.mark.asyncio
async def test_default_transport_uses_fixed_safe_headers_and_decodes_chunked_gzip() -> None:
    received = b""
    plain = b"safe body"
    compressed = gzip.compress(plain)

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal received
        received = await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            b"Content-Encoding: gzip\r\nTransfer-Encoding: chunked\r\n\r\n"
            + f"{len(compressed):x}\r\n".encode()
            + compressed
            + b"\r\n0\r\n\r\n"
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])
    try:
        wire = await default_transport(
            url=f"http://example.com:{port}/path?q=1",
            connect_ip="127.0.0.1",
            hostname="example.com",
            port=port,
            use_tls=False,
        )
    finally:
        server.close()
        await server.wait_closed()
    assert wire.body == plain
    assert b"Host: example.com:" in received
    assert b"User-Agent: FlowTracer-Alpha/0.1" in received
    assert b"Authorization:" not in received
    assert b"Cookie:" not in received
    assert b"private_hint" not in received


@pytest.mark.asyncio
async def test_safe_fetcher_follows_valid_redirect_and_accepts_type_parameters() -> None:
    calls: list[str] = []

    async def transport(**kwargs: object) -> WireResponse:
        calls.append(str(kwargs["url"]))
        if len(calls) == 1:
            return WireResponse(302, {"location": "/final"}, b"")
        return WireResponse(200, {"content-type": "Text/HTML; Charset=UTF-8"}, b"<p>ok</p>")

    fetched = await SafeFetcher(resolver=public_resolver, transport=transport).fetch(
        "https://example.com/start", SourceType.URL
    )
    assert calls == ["https://example.com/start", "https://example.com/final"]
    assert fetched.final_url == "https://example.com/final"
    assert fetched.body == b"<p>ok</p>"


@pytest.mark.asyncio
async def test_redirect_limit_and_total_timeout_are_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redirect_calls = 0

    async def redirecting(**_kwargs: object) -> WireResponse:
        nonlocal redirect_calls
        redirect_calls += 1
        return WireResponse(302, {"location": "/again"}, b"")

    with pytest.raises(CollectionError) as redirect_error:
        await SafeFetcher(resolver=public_resolver, transport=redirecting).fetch(
            "https://example.com/start", SourceType.URL
        )
    assert redirect_error.value.code == "http_error"
    assert redirect_calls == MAX_REDIRECTS + 1

    async def hanging(**_kwargs: object) -> WireResponse:
        await asyncio.sleep(1)
        raise AssertionError("timeout should cancel transport")

    monkeypatch.setattr("app.services.safe_fetcher.TOTAL_TIMEOUT", 0.01)
    with pytest.raises(CollectionError) as timeout_error:
        await SafeFetcher(resolver=public_resolver, transport=hanging).fetch(
            "https://example.com/start", SourceType.URL
        )
    assert timeout_error.value.code == "request_timeout"
    assert timeout_error.value.retryable
