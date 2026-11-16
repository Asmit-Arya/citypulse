"""Small compatibility layer for CityPulse's qmark-style SQL on PostgreSQL."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import IntegrityError as PostgresIntegrityError
from psycopg.rows import dict_row


class HybridRow(dict):
    """Mapping row that also supports SQLite-style numeric indexing."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)



def _hybrid_row_factory(cursor):
    description = cursor.description

    # CREATE TABLE, INSERT without returned rows, and other
    # commands may not return columns.
    if description is None:
        return None

    names = [column.name for column in description]

    def make_row(values):
        return HybridRow(zip(names, values))

    return make_row



def _adapt_sql(sql: str) -> str:
    sql = re.sub(r"\?\s+COLLATE\s+NOCASE", "?", sql, flags=re.IGNORECASE)
    sql = sql.replace("date(completed_at) = date('now')", "completed_at::date = CURRENT_DATE")
    # CityPulse statements use positional qmark parameters and do not contain
    # question marks inside SQL string literals.
    return sql.replace("?", "%s")


def get_postgres_connection(database_url: str):
    """Open a Neon/PostgreSQL connection. TLS is required for hosted Neon DBs."""
    url = database_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return PostgresCompatConnection(psycopg.connect(url, row_factory=_hybrid_row_factory, connect_timeout=15))


class PostgresCompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None
        self.rowcount = cursor.rowcount

    def execute(self, sql, params=()):
        adapted = _adapt_sql(sql)
        is_insert = bool(re.match(r"\s*INSERT\s+INTO\b", adapted, flags=re.IGNORECASE))
        if is_insert and " RETURNING " not in adapted.upper():
            adapted += " RETURNING id"
            self._cursor.execute(adapted, params or ())
            row = self._cursor.fetchone()
            self.lastrowid = row["id"] if row else None
        else:
            self._cursor.execute(adapted, params or ())
        self.rowcount = self._cursor.rowcount
        return self

    def executemany(self, sql, seq_of_params):
        self._cursor.executemany(_adapt_sql(sql), seq_of_params)
        self.rowcount = self._cursor.rowcount
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class PostgresCompatConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        return PostgresCompatCursor(self._connection.cursor(row_factory=_hybrid_row_factory)).execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return PostgresCompatCursor(self._connection.cursor(row_factory=_hybrid_row_factory)).executemany(sql, seq_of_params)

    def cursor(self):
        return PostgresCompatCursor(self._connection.cursor(row_factory=_hybrid_row_factory))

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()
