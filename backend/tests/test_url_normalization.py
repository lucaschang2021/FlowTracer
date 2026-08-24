import pytest

from app.core.errors import AppError
from app.services.url_normalization import normalize_source_url


@pytest.mark.parametrize(
    ("value", "original", "normalized"),
    [
        (" HTTP://Example.COM ", "HTTP://Example.COM", "http://example.com/"),
        (
            "https://bücher.example.:443/a",
            "https://bücher.example.:443/a",
            "https://xn--bcher-kva.example/a",
        ),
        ("http://example.com:8080", "http://example.com:8080", "http://example.com:8080/"),
        (
            "http://example.com/a/./b/../c/",
            "http://example.com/a/./b/../c/",
            "http://example.com/a/c/",
        ),
        ("http://example.com/%7e/%2f", "http://example.com/%7e/%2f", "http://example.com/~/%2F"),
        (
            "https://example.com?p=2&a=3&a=1#fragment",
            "https://example.com?p=2&a=3&a=1#fragment",
            "https://example.com/?a=1&a=3&p=2",
        ),
        (
            "https://example.com/path?z=1&z=1",
            "https://example.com/path?z=1&z=1",
            "https://example.com/path?z=1&z=1",
        ),
    ],
)
def test_url_normalization_table(value: str, original: str, normalized: str) -> None:
    assert normalize_source_url(value) == (original, normalized)


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.com/file",
        "https://user:password@example.com/",
        "https:///missing-host",
        "https://example.com:invalid/",
        "https://example.com/%zz",
        "https://exa mple.com/",
        "https://bad_host.example/",
        "https://-bad.example/",
        "https://example.com/" + "a" * 2048,
    ],
)
def test_url_normalization_rejects_invalid_input(value: str) -> None:
    with pytest.raises(AppError) as caught:
        normalize_source_url(value)
    assert caught.value.status_code == 422
    assert caught.value.code == "invalid_request"
