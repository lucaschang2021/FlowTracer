from contextvars import ContextVar, Token

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_context(
    request_id: str, correlation_id: str
) -> tuple[Token[str | None], Token[str | None]]:
    return request_id_context.set(request_id), correlation_id_context.set(correlation_id)


def reset_context(tokens: tuple[Token[str | None], Token[str | None]]) -> None:
    request_id_context.reset(tokens[0])
    correlation_id_context.reset(tokens[1])
