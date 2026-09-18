from __future__ import annotations

import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://plant:plant_dev_password@localhost:5432/plant_data")
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)


def open_pool() -> None:
    pool.open(wait=True)


def close_pool() -> None:
    pool.close()


@contextmanager
def connection():
    with pool.connection() as conn:
        yield conn


def fetch_all(query: str, params: tuple | dict = ()) -> list[dict]:
    with connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return list(cursor.fetchall())

