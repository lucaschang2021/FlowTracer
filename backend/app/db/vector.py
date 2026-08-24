from asyncpg import Connection
from pgvector.asyncpg import register_vector


async def register_vector_types(connection: Connection) -> None:
    """Register pgvector codecs on an asyncpg connection when vector access is needed."""
    await register_vector(connection)
