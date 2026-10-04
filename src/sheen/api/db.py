"""Async connection pool for the API (the pipeline uses the sync pool in sheen.db)."""

from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from sheen.config import get_settings

_pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None


async def open_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        get_settings().database_url,
        connection_class=AsyncConnection[DictRow],
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


async def fetch(query: str, params: Any = None) -> list[DictRow]:
    assert _pool is not None, "pool not opened"
    async with _pool.connection() as conn:
        cur = await conn.execute(query, params)
        return await cur.fetchall()


async def fetch_one(query: str, params: Any = None) -> DictRow | None:
    rows = await fetch(query, params)
    return rows[0] if rows else None
