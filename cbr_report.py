"""CBR (cash back rate) — собираемость помесячно по сотрудникам-взыскателям, регионам,
текущим кредиторам и типам долга. Источник — cbr.monthly (материализованное
представление поверх public.cbr_report_1/cbr_report_2, см. schema.sql), и
cbr.employee_mapping (сотрудник -> отдел, для среза "Отдел").

CBR от ОСЗ % = Платежи за месяц / Остаток общей задолженности на конец месяца.
CBR от ОД % = Платежи за месяц / Остаток основного долга на конец месяца.
"""
from collections import defaultdict

from db import query

DIM_COLUMNS = {
    'employee': 'employee',
    'region': 'region',
    'creditor': 'creditor',
    'debt_type': 'debt_type',
}
DIM_LABELS = {
    'employee': 'Сотрудник', 'region': 'Регион', 'creditor': 'Текущий кредитор',
    'debt_type': 'Тип долга', 'department': 'Отдел',
}


def get_available_months():
    rows = query('SELECT DISTINCT month FROM cbr.monthly ORDER BY 1')
    return [r['month'] for r in rows]


def _cbr(payment, base):
    return (payment / base * 100) if base else 0.0


def overall_by_month():
    rows = query('''SELECT month, SUM(total_debt) AS total_debt, SUM(principal_debt) AS principal_debt,
                            SUM(payment_amount) AS payment_amount
                     FROM cbr.monthly GROUP BY 1 ORDER BY 1''')
    months = [r['month'] for r in rows]
    total_debt = [float(r['total_debt'] or 0) for r in rows]
    principal_debt = [float(r['principal_debt'] or 0) for r in rows]
    payment_amount = [float(r['payment_amount'] or 0) for r in rows]
    cbr_osz = [_cbr(payment_amount[i], total_debt[i]) for i in range(len(months))]
    cbr_od = [_cbr(payment_amount[i], principal_debt[i]) for i in range(len(months))]
    return {
        'months_raw': months, 'months': [m.strftime('%m.%Y') for m in months],
        'total_debt': total_debt, 'principal_debt': principal_debt, 'payment_amount': payment_amount,
        'cbr_osz': cbr_osz, 'cbr_od': cbr_od,
    }


def _dim_query(dim):
    if dim == 'department':
        return '''SELECT m.month, COALESCE(e.department, 'Без отдела') AS key,
                          SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
                   FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
                   GROUP BY 1, 2 ORDER BY 1'''
    col = DIM_COLUMNS[dim]
    return f'''SELECT month, COALESCE("{col}", 'Не указано') AS key,
                      SUM(total_debt) AS total_debt, SUM(payment_amount) AS payment_amount
               FROM cbr.monthly GROUP BY 1, 2 ORDER BY 1'''


def by_dim(dim, top_n=8):
    """CBR от ОСЗ по месяцам для top_n самых крупных (по остатку в последнем месяце)
    значений измерения dim (employee/region/creditor/debt_type/department)."""
    rows = query(_dim_query(dim))
    by_key = defaultdict(dict)
    months_set = set()
    for r in rows:
        months_set.add(r['month'])
        by_key[r['key']][r['month']] = {
            'total_debt': float(r['total_debt'] or 0), 'payment_amount': float(r['payment_amount'] or 0),
        }
    months = sorted(months_set)
    latest = months[-1] if months else None
    top_keys = sorted(by_key.keys(), key=lambda k: -by_key[k].get(latest, {}).get('total_debt', 0))[:top_n]
    dim_rows = []
    for k in top_keys:
        series = by_key[k]
        cbr_series = [_cbr(series.get(m, {}).get('payment_amount', 0), series.get(m, {}).get('total_debt', 0)) for m in months]
        dim_rows.append({'key': k, 'cbr_osz': cbr_series})
    return {'months': [m.strftime('%m.%Y') for m in months], 'rows': dim_rows}


def top_bottom_performers(month, dim, n=5, min_debt=1_000_000):
    if dim == 'department':
        rows = query('''SELECT COALESCE(e.department, 'Без отдела') AS key,
                                SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
                         FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
                         WHERE m.month = %s GROUP BY 1''', (month,))
    else:
        col = DIM_COLUMNS[dim]
        rows = query(f'''SELECT COALESCE("{col}", 'Не указано') AS key,
                                 SUM(total_debt) AS total_debt, SUM(payment_amount) AS payment_amount
                          FROM cbr.monthly WHERE month = %s GROUP BY 1''', (month,))
    items = []
    for r in rows:
        total_debt = float(r['total_debt'] or 0)
        if total_debt < min_debt:
            continue
        payment = float(r['payment_amount'] or 0)
        items.append({'key': r['key'], 'cbr': _cbr(payment, total_debt), 'total_debt': total_debt})
    items.sort(key=lambda x: -x['cbr'])
    bottom = list(reversed(items[-n:])) if len(items) > n else list(reversed(items))
    return {'top': items[:n], 'bottom': bottom}


def analysis_and_recommendations(dim='department'):
    """Текстовые выводы, посчитанные правилами (не LLM): тренд CBR, отстающие и
    лидирующие срезы выбранного измерения за последний месяц."""
    overall = overall_by_month()
    months, cbr_osz = overall['months'], overall['cbr_osz']
    bullets = []
    if len(cbr_osz) >= 2:
        delta = cbr_osz[-1] - cbr_osz[-2]
        direction = 'выросла' if delta > 0.01 else 'снизилась' if delta < -0.01 else 'не изменилась'
        bullets.append(f'CBR от ОСЗ за {months[-1]} {direction} до {cbr_osz[-1]:.2f}% (было {cbr_osz[-2]:.2f}% в {months[-2]}).')
    if len(cbr_osz) >= 6:
        avg_recent = sum(cbr_osz[-3:]) / 3
        avg_prior = sum(cbr_osz[-6:-3]) / 3
        trend = 'растёт' if avg_recent > avg_prior else 'снижается'
        bullets.append(f'Тренд за последние 3 месяца: CBR {trend} ({avg_recent:.2f}% против {avg_prior:.2f}% в предыдущие 3 месяца).')

    months_raw = overall['months_raw']
    if months_raw:
        latest_month = months_raw[-1]
        perf = top_bottom_performers(latest_month, dim, n=3)
        avg_cbr = cbr_osz[-1] if cbr_osz else 0
        for item in perf['bottom']:
            if avg_cbr - item['cbr'] > 2:
                bullets.append(
                    f'{DIM_LABELS.get(dim, dim)} «{item["key"]}»: CBR {item["cbr"]:.2f}% — ниже среднего '
                    f'({avg_cbr:.2f}%) на {avg_cbr - item["cbr"]:.1f} п.п., стоит разобраться в причинах.'
                )
        for item in perf['top'][:2]:
            if item['cbr'] - avg_cbr > 2:
                bullets.append(
                    f'{DIM_LABELS.get(dim, dim)} «{item["key"]}»: CBR {item["cbr"]:.2f}% — заметно выше среднего, '
                    f'практику стоит тиражировать на отстающих.'
                )
    if not bullets:
        bullets.append('Недостаточно данных для анализа.')
    return bullets


def get_employee_mapping():
    return query('SELECT * FROM cbr.employee_mapping ORDER BY department NULLS LAST, employee')


def update_employee_mapping(employee, department, region, is_fired, employment_type):
    from db import execute
    execute(
        '''UPDATE cbr.employee_mapping SET department = %s, region = %s, is_fired = %s, employment_type = %s, updated_at = now()
           WHERE employee = %s''',
        (department or None, region or None, is_fired, employment_type or None, employee)
    )


def export_rows(overall):
    headers = ['Месяц', 'ОСЗ всего', 'Основной долг', 'Платежи за месяц', 'CBR от ОСЗ %', 'CBR от ОД %']
    rows = [
        [overall['months'][i], overall['total_debt'][i], overall['principal_debt'][i],
         overall['payment_amount'][i], overall['cbr_osz'][i], overall['cbr_od'][i]]
        for i in range(len(overall['months']))
    ]
    return [('CBR', headers, rows)]
