"""Автообновление reporting.* — без участия пользователя.

Материализованные представления в схеме reporting считаются на снимке
данных на момент REFRESH. Эта функция обновляет их все; регистрируется
в app.py как APScheduler-задача (интервал) + разовый вызов при старте.
"""
import logging

from db import execute_autocommit

logger = logging.getLogger('reporting_refresh')

VIEWS = ['reporting.pl_monthly', 'reporting.fot_monthly', 'reporting.loans_monthly']


def refresh_all():
    for view in VIEWS:
        try:
            execute_autocommit(f'REFRESH MATERIALIZED VIEW CONCURRENTLY {view}')
            logger.info('Обновлено: %s', view)
        except Exception:
            logger.exception('Не удалось обновить %s', view)
