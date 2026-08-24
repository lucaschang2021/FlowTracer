from __future__ import annotations

import ipaddress
import string
from urllib.parse import urlsplit, urlunsplit

from app.core.errors import AppError

_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")
_PATH_SAFE = _UNRESERVED | frozenset("!$&''()*+,;=:@/")
_QUERY_SAFE = _UNRESERVED | frozenset("!$''()*+,;:@/?=")
_HEX = frozenset(string.hexdigits)


def invalid_url(message: str = "Invalid source URL") -> AppError:
    return AppError(status_code=422, code="invalid_request", message=message)


def _normalize_component(value: str, safe: frozenset[str]) -> str:
    output: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character == "%":
            if index + 2 >= len(value) or not set(value[index + 1 : index + 3]) <= _HEX:
                raise invalid_url()
            byte = int(value[index + 1 : index + 3], 16)
            decoded = chr(byte)
            output.append(decoded if decoded in _UNRESERVED else f"%{byte:02X}")
            index += 3
            continue
        if character in safe:
            output.append(character)
        else:
            output.extend(f"%{byte:02X}" for byte in character.encode("utf-8"))
        index += 1
    return "".join(output)


def _remove_dot_segments(path: str) -> str:
    input_buffer = path
    output = ""
    while input_buffer:
        if input_buffer.startswith("../"):
            input_buffer = input_buffer[3:]
        elif input_buffer.startswith("./"):
            input_buffer = input_buffer[2:]
        elif input_buffer.startswith("/./"):
            input_buffer = "/" + input_buffer[3:]
        elif input_buffer == "/.":
            input_buffer = "/"
        elif input_buffer.startswith("/../"):
            input_buffer = "/" + input_buffer[4:]
            output = output.rsplit("/", maxsplit=1)[0]
        elif input_buffer == "/..":
            input_buffer = "/"
            output = output.rsplit("/", maxsplit=1)[0]
        elif input_buffer in {".", ".."}:
            input_buffer = ""
        else:
            slash = input_buffer.find("/", 1 if input_buffer.startswith("/") else 0)
            if slash == -1:
                output += input_buffer
                input_buffer = ""
            else:
                output += input_buffer[:slash]
                input_buffer = input_buffer[slash:]
    return output


def _normalize_host(host: str) -> str:
    host = host.rstrip(".")
    if not host or any(character.isspace() for character in host):
        raise invalid_url()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            normalized = host.encode("idna").decode("ascii").lower()
        except UnicodeError:
            raise invalid_url() from None
        labels = normalized.split(".")
        if (
            not normalized
            or len(normalized) > 253
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or any(
                    not (character.isascii() and (character.isalnum() or character == "-"))
                    for character in label
                )
                for label in labels
            )
        ):
            raise invalid_url() from None
        return normalized
    if address.version == 6:
        return f"[{address.compressed}]"
    return address.compressed


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    pairs: list[tuple[str, str, bool, int]] = []
    for position, raw_pair in enumerate(query.split("&")):
        has_equals = "=" in raw_pair
        key, value = raw_pair.split("=", maxsplit=1) if has_equals else (raw_pair, "")
        pairs.append((key, value, has_equals, position))
    pairs.sort(key=lambda item: (item[0], item[1], item[3]))
    return "&".join(
        f"{_normalize_component(key, _QUERY_SAFE)}={_normalize_component(value, _QUERY_SAFE)}"
        if has_equals
        else _normalize_component(key, _QUERY_SAFE)
        for key, value, has_equals, _ in pairs
    )


def normalize_source_url(value: str) -> tuple[str, str]:
    original = value.strip()
    if not original or len(original) > 2048:
        raise invalid_url()
    try:
        parsed = urlsplit(original)
        port = parsed.port
    except ValueError:
        raise invalid_url() from None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise invalid_url()
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise invalid_url("Source URL must not contain userinfo")
    if parsed.hostname is None:
        raise invalid_url()
    host = _normalize_host(parsed.hostname)
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    authority = host if port is None or default_port else f"{host}:{port}"

    path = _normalize_component(parsed.path or "/", _PATH_SAFE)
    path = _remove_dot_segments(path) or "/"
    query = _normalize_query(parsed.query)
    normalized = urlunsplit((scheme, authority, path, query, ""))
    if len(normalized) > 2048:
        raise invalid_url()
    return original, normalized
