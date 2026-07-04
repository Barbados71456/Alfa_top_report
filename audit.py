"""Аудит-лог действий пользователей: вход, правки классификаторов/справочников,
экспорт в Excel, вопросы в чат. Хранится в reporting.audit_log, просматривается
на /admin/log (см. app.py)."""
from flask import request

from db import execute, query


def log_action(username, action, details=None):
    ip = request.remote_addr if request else None
    execute(
        'INSERT INTO reporting.audit_log (username, action, details, ip_address) VALUES (%s, %s, %s, %s)',
        (username, action, details, ip)
    )


def get_log(search='', limit=200):
    sql = 'SELECT * FROM reporting.audit_log'
    params = []
    if search:
        sql += ' WHERE username ILIKE %s OR action ILIKE %s OR details ILIKE %s'
        like = f'%{search}%'
        params = [like, like, like]
    sql += ' ORDER BY created_at DESC LIMIT %s'
    params.append(limit)
    return query(sql, params)
