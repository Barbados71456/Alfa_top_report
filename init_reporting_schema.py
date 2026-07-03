"""Разовое применение schema.sql (создание схемы reporting и материализованных
представлений). Дальше они обновляются автоматически через reporting_refresh.py.

Использование: python init_reporting_schema.py
"""
import pathlib

from db import execute

SCHEMA_FILE = pathlib.Path(__file__).parent / 'schema.sql'


def main():
    sql = SCHEMA_FILE.read_text(encoding='utf-8')
    execute(sql)
    print('Схема reporting применена.')


if __name__ == '__main__':
    main()
