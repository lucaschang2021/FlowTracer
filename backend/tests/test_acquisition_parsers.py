from __future__ import annotations

import hashlib

import pytest

from app.services.acquisition_parsers import parse_feed, parse_html
from app.services.acquisition_types import CollectionError, FetchResponse


def response(body: bytes, content_type: str = "application/rss+xml") -> FetchResponse:
    return FetchResponse(
        final_url="https://example.com/feed/index.xml",
        content_type=content_type,
        body=body,
    )


def test_rss_and_atom_extract_stable_fields_and_partial_failures() -> None:
    rss = response(
        b"""<?xml version="1.0"?>
        <rss><channel>
          <item><guid>item-1</guid><title> One </title><link>../one#part</link>
            <description> A\r\nB </description><pubDate>Tue, 26 Aug 2025 10:00:00 GMT</pubDate>
            <author>author@example.com</author></item>
          <item><link>https://example.com/empty</link><description> </description></item>
        </channel></rss>"""
    )
    parsed = parse_feed(rss)
    assert parsed.fetched_count == 2
    assert parsed.failed_count == 1
    assert parsed.candidates[0].external_id == "item-1"
    assert parsed.candidates[0].canonical_url == "https://example.com/one"
    assert parsed.candidates[0].raw_text == "A\nB"
    assert parsed.candidates[0].metadata == {"author": "author@example.com"}

    atom = response(
        b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <link href="/entry"/><content>Stable content</content>
        </entry></feed>""",
        "application/atom+xml",
    )
    candidate = parse_feed(atom).candidates[0]
    assert candidate.external_id == "https://example.com/entry"

    without_id_or_link = response(
        b"<rss><channel><item><description>hash me</description></item></channel></rss>"
    )
    candidate = parse_feed(without_id_or_link).candidates[0]
    assert candidate.external_id == hashlib.sha256(b"hash me").hexdigest()


@pytest.mark.parametrize(
    "body",
    [
        b"<rss><broken>",
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><rss>&xxe;</rss>',
    ],
)
def test_feed_rejects_malformed_or_dangerous_xml(body: bytes) -> None:
    with pytest.raises(CollectionError) as raised:
        parse_feed(response(body))
    assert raised.value.code == "invalid_feed"


def test_html_extracts_readable_text_and_never_preserves_executable_content() -> None:
    html = response(
        b"""<html><head><title> Page Title </title>
        <link rel="canonical" href="../canonical#fragment"></head>
        <body onload="steal()"><script>secret()</script><style>.x{}</style>
        <noscript>hidden</noscript><template>also hidden</template>
        <main>Hello <b>world</b></main></body></html>""",
        'text/html; charset="utf-8"',
    )
    candidate = parse_html(html, "https://example.com/source").candidates[0]
    assert candidate.canonical_url == "https://example.com/canonical"
    assert candidate.title == "Page Title"
    assert "Hello" in candidate.raw_text and "world" in candidate.raw_text
    assert all(value not in candidate.raw_text for value in ("secret", "hidden", "onload"))


def test_html_empty_content_is_a_safe_failure_and_charset_falls_back() -> None:
    with pytest.raises(CollectionError) as raised:
        parse_html(
            response(b"<html><script>x()</script></html>", "text/html"), "https://example.com"
        )
    assert raised.value.code == "empty_content"

    parsed = parse_html(
        response("<html><body>café</body></html>".encode("latin-1"), "text/html; charset=latin-1"),
        "https://example.com",
    )
    assert parsed.candidates[0].raw_text == "café"
