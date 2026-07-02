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
