"""Автообновление reporting.* — без участия пользователя.

Материализованные представления в схеме reporting считаются на снимке
данных на момент REFRESH. Эта функция обновляет их все; регистрируется
в app.py как APScheduler-задача (интервал) + разовый вызов при старте.
"""
import logging

from db import execute, execute_autocommit
import investment_report as ir

logger = logging.getLogger('reporting_refresh')

VIEWS = ['reporting.pl_monthly', 'reporting.pl_monthly_stat3', 'reporting.fot_monthly',
         'reporting.loans_monthly', 'reporting.counterparty_list', 'reporting.dp_monthly']


def _sync_employees():
    """Новых сотрудников, появившихся в fot_monthly, добавляет в reporting.employees
    с подразделением-заготовкой (взято из FinancialData."Контрагент_report" на
    момент появления). Уже существующие строки (в т.ч. поправленные админом
    вручную) не трогает — ON CONFLICT DO NOTHING."""
    execute('''
        INSERT INTO reporting.employees (contragent, department)
        SELECT employee, (array_agg(dept))[1]
        FROM reporting.fot_monthly
        GROUP BY employee
        ON CONFLICT (contragent) DO NOTHING
    ''')


def refresh_all():
    for view in VIEWS:
        try:
            execute_autocommit(f'REFRESH MATERIALIZED VIEW CONCURRENTLY {view}')
            logger.info('Обновлено: %s', view)
        except Exception:
            logger.exception('Не удалось обновить %s', view)

    try:
        # Без CONCURRENTLY: cbr.monthly агрегирует уже готовые статичные-за-месяц
        # таблицы выгрузки (cbr_report_1/2), уникальный индекс под CONCURRENTLY не
        # нужен — обычный REFRESH проще и надёжнее для этого источника.
        execute_autocommit('REFRESH MATERIALIZED VIEW cbr.monthly')
        logger.info('Обновлено: cbr.monthly')
    except Exception:
        logger.exception('Не удалось обновить cbr.monthly')

    try:
        _sync_employees()
        logger.info('Обновлён справочник reporting.employees')
    except Exception:
        logger.exception('Не удалось обновить reporting.employees')

    try:
        ir.sync_aliases()
        logger.info('Обновлены алиасы reporting.dp_portfolio_aliases')
    except Exception:
        logger.exception('Не удалось обновить reporting.dp_portfolio_aliases')
