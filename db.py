import psycopg2
import psycopg2.extras
from flask import g, has_app_context

from config import Config


def _connect():
    if Config.DATABASE_URL:
        return psycopg2.connect(Config.DATABASE_URL, connect_timeout=10)
    return psycopg2.connect(
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        connect_timeout=10,
    )


def _request_connection():
    """Одно соединение на HTTP-запрос, кешируется в flask.g и закрывается в teardown_appcontext."""
    if 'db_conn' not in g:
        g.db_conn = _connect()
    return g.db_conn


def close_connection(exc=None):
    conn = g.pop('db_conn', None)
    if conn is not None:
        conn.close()


def query(sql, params=None):
    if has_app_context():
        conn = _request_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute_autocommit(sql):
    """Для команд, которые не могут идти внутри транзакции (REFRESH MATERIALIZED VIEW CONCURRENTLY и т.п.)."""
    conn = _connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def execute(sql, params=None):
    if has_app_context():
        conn = _request_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
        return
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    finally:
        conn.close()


def execute_returning(sql, params=None):
    """INSERT/UPDATE ... RETURNING — query()/query_one() не коммитят (только
    execute() коммитит), поэтому для write-запросов, которым нужна вернувшаяся
    строка (например id только что вставленной записи), нужен отдельный
    коммитящий путь, а не query_one()."""
    if has_app_context():
        conn = _request_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


def execute_values(sql, rows):
    """INSERT INTO t (...) VALUES %s — одним round-trip для множества строк
    (psycopg2.extras.execute_values), вместо execute() построчно в цикле."""
    if has_app_context():
        conn = _request_connection()
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
        conn.commit()
        return
    conn = _connect()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
        conn.commit()
    finally:
        conn.close()
