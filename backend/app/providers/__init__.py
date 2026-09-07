"""External analysis-provider boundary."""

from app.domains.provider_ports import (
    AnalysisProvider,
    AnalysisRequest,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResponse,
    EmbeddingUsage,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
)
from app.providers.analysis import (
    FakeAnalysisProvider,
    OpenAICompatibleProvider,
    build_provider,
)
from app.providers.embedding import (
    FakeEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)

__all__ = [
    "AnalysisProvider",
    "AnalysisRequest",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingResponse",
    "EmbeddingUsage",
    "FakeAnalysisProvider",
    "FakeEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "ProviderResponse",
    "ProviderUsage",
    "build_embedding_provider",
    "build_provider",
]
