from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from sheen.config import get_settings

_pool: ConnectionPool[psycopg.Connection[DictRow]] | None = None


def get_pool() -> ConnectionPool[psycopg.Connection[DictRow]]:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            connection_class=psycopg.Connection[DictRow],
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def connect() -> Iterator[psycopg.Connection[DictRow]]:
    """Borrow a database connection. Changes are saved if the block ends without
    an error, and undone if it doesn't."""
    with get_pool().connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
