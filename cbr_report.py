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

# Эталонный BI-отчёт (CBR_v4.xlsx) был жёстко зафиксирован на срезе "Тип долга" =
# "Агентский" (см. xl/slicerCaches/slicerCache1.xml) — теперь это тот же смысл,
# но уже как обычный переключаемый фильтр с этим значением по умолчанию (см.
# DEFAULT_DEBT_TYPES ниже), а не зашитое в SQL условие.
DEFAULT_DEBT_TYPES = ['Агентский']
# "Изъятие"/"Изъятие по ИП"/"Хранение ТС" по умолчанию исключены — это не этапы
# взыскания долга, а физическая работа со связанным имуществом (запрошено
# пользователем как набор "рабочих" типов по умолчанию).
DEFAULT_WORK_TYPES = ['Взыскание', 'Взыскание по ИП', 'ДРЗ', 'Реализация', 'Реализация с баланса']
# По умолчанию убран из "Текущего кредитора" (запрошено пользователем) — реализовано
# как исключение по значению, а не список остальных 50 кредиторов, чтобы новые
# кредиторы автоматически попадали в срез по умолчанию.
_ZAYMER_CREDITOR = 'ПАО\xa0МФК «Займер»'


def _core_where(prefix='', creditor=None, debt_type=None, work_type=None):
    """Общий фильтр по Текущему кредитору/Типу долга/Типу работы — применяется на
    всех вкладках CBR (раньше только "Тип долга"='Агентский' было зашито жёстко)."""
    debt_type = debt_type if debt_type is not None else DEFAULT_DEBT_TYPES
    work_type = work_type if work_type is not None else DEFAULT_WORK_TYPES
    where, params = ['1=1'], []
    if creditor is not None:
        where.append(f'{prefix}creditor = ANY(%s)'); params.append(creditor)
    else:
        where.append(f'{prefix}creditor IS DISTINCT FROM %s'); params.append(_ZAYMER_CREDITOR)
    where.append(f'{prefix}debt_type = ANY(%s)'); params.append(debt_type)
    where.append(f'{prefix}work_type = ANY(%s)'); params.append(work_type)
    return ' AND '.join(where), params


def get_available_months():
    rows = query('SELECT DISTINCT month FROM cbr.monthly ORDER BY 1')
    return [r['month'] for r in rows]


def _cbr(payment, base):
    return (payment / base * 100) if base else 0.0


def overall_by_month(creditor=None, debt_type=None, work_type=None):
    """Свод по месяцам — 1:1 со страницей "Таблица" в BI (7 строк: ОСЗ тыс.руб/шт,
    Платежи тыс.руб/шт, Основной долг тыс.руб, CBR от ОСЗ/ОД %)."""
    where, params = _core_where('', creditor, debt_type, work_type)
    rows = query(f'''SELECT month, SUM(total_debt) AS total_debt, SUM(principal_debt) AS principal_debt,
                            SUM(payment_amount) AS payment_amount, SUM(do_count) AS do_count,
                            SUM(payment_count) AS payment_count
                     FROM cbr.monthly WHERE {where} GROUP BY 1 ORDER BY 1''', params)
    months = [r['month'] for r in rows]
    total_debt = [float(r['total_debt'] or 0) for r in rows]
    principal_debt = [float(r['principal_debt'] or 0) for r in rows]
    payment_amount = [float(r['payment_amount'] or 0) for r in rows]
    do_count = [int(r['do_count'] or 0) for r in rows]
    payment_count = [int(r['payment_count'] or 0) for r in rows]
    cbr_osz = [_cbr(payment_amount[i], total_debt[i]) for i in range(len(months))]
    cbr_od = [_cbr(payment_amount[i], principal_debt[i]) for i in range(len(months))]
    return {
        'months_raw': months, 'months': [m.strftime('%m.%Y') for m in months],
        'total_debt': total_debt, 'principal_debt': principal_debt, 'payment_amount': payment_amount,
        'do_count': do_count, 'payment_count': payment_count,
        'cbr_osz': cbr_osz, 'cbr_od': cbr_od,
    }


def _dim_query(dim, creditor=None, debt_type=None, work_type=None):
    if dim == 'department':
        where, params = _core_where('m.', creditor, debt_type, work_type)
        return f'''SELECT m.month, COALESCE(e.department, 'Без отдела') AS key,
                          SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
                   FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
                   WHERE {where} GROUP BY 1, 2 ORDER BY 1''', params
    col = DIM_COLUMNS[dim]
    where, params = _core_where('', creditor, debt_type, work_type)
    return f'''SELECT month, COALESCE("{col}", 'Не указано') AS key,
                      SUM(total_debt) AS total_debt, SUM(payment_amount) AS payment_amount
               FROM cbr.monthly WHERE {where} GROUP BY 1, 2 ORDER BY 1''', params


def by_dim(dim, top_n=8, creditor=None, debt_type=None, work_type=None):
    """CBR от ОСЗ по месяцам для top_n самых крупных (по остатку в последнем месяце)
    значений измерения dim (employee/region/creditor/debt_type/department)."""
    sql, params = _dim_query(dim, creditor, debt_type, work_type)
    rows = query(sql, params)
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


def top_bottom_performers(month, dim, n=5, min_debt=1_000_000, creditor=None, debt_type=None, work_type=None):
    if dim == 'department':
        where, params = _core_where('m.', creditor, debt_type, work_type)
        rows = query(f'''SELECT COALESCE(e.department, 'Без отдела') AS key,
                                SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
                         FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
                         WHERE m.month = %s AND {where} GROUP BY 1''', [month] + params)
    else:
        col = DIM_COLUMNS[dim]
        where, params = _core_where('', creditor, debt_type, work_type)
        rows = query(f'''SELECT COALESCE("{col}", 'Не указано') AS key,
                                 SUM(total_debt) AS total_debt, SUM(payment_amount) AS payment_amount
                          FROM cbr.monthly WHERE month = %s AND {where} GROUP BY 1''', [month] + params)
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


def analysis_and_recommendations(dim='department', creditor=None, debt_type=None, work_type=None):
    """Текстовые выводы, посчитанные правилами (не LLM): тренд CBR, отстающие и
    лидирующие срезы выбранного измерения за последний месяц."""
    overall = overall_by_month(creditor, debt_type, work_type)
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
        perf = top_bottom_performers(latest_month, dim, n=3, creditor=creditor, debt_type=debt_type, work_type=work_type)
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


# "Сеть" — если в строке заполнено поле "Сотрудник", иначе "не Сеть" (правило
# подтверждено пользователем; в исходном BI это срез "Пользовательский", по
# умолчанию выбрано значение 'Сеть').
_IS_NETWORK_SQL = "(m.employee IS NOT NULL AND trim(m.employee) <> '')"


def _cbr_filters_where(dept=None, emp_region=None, employee=None, is_network=None,
                        creditor=None, debt_type=None, work_type=None):
    where, params = _core_where('m.', creditor, debt_type, work_type)
    where = [where]
    if dept:
        where.append('e.department = ANY(%s)'); params.append(dept)
    if emp_region:
        where.append('e.region = ANY(%s)'); params.append(emp_region)
    if employee:
        where.append('m.employee = ANY(%s)'); params.append(employee)
    if is_network is not None:
        where.append(f'{_IS_NETWORK_SQL} = %s'); params.append(is_network)
    return ' AND '.join(where), params


def creditor_pivot(dept=None, emp_region=None, employee=None, is_network=None,
                    creditor=None, debt_type=None, work_type=None):
    """Rows=Текущий кредитор, columns=месяц, values=CBR от ОСЗ % (страница
    "Таблица"/"Партнёры" в BI). Без фильтров — свод по всей компании."""
    where, params = _cbr_filters_where(dept, emp_region, employee, is_network, creditor, debt_type, work_type)
    sql = f'''SELECT m.month, COALESCE(m.creditor, 'Не указано') AS creditor,
                     SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
              FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
              WHERE {where} GROUP BY 1, 2 ORDER BY 1'''
    rows = query(sql, params)
    months = sorted({r['month'] for r in rows})
    creditors = sorted({r['creditor'] for r in rows})
    matrix = defaultdict(dict)
    matrix_debt = defaultdict(dict)
    matrix_payment = defaultdict(dict)
    for r in rows:
        debt, payment = float(r['total_debt'] or 0), float(r['payment_amount'] or 0)
        matrix[r['creditor']][r['month']] = _cbr(payment, debt)
        matrix_debt[r['creditor']][r['month']] = debt
        matrix_payment[r['creditor']][r['month']] = payment
    return {
        'months': [m.strftime('%m.%Y') for m in months],
        'creditors': creditors,
        'matrix': {c: [matrix[c].get(m, 0.0) for m in months] for c in creditors},
        'matrix_debt': {c: [matrix_debt[c].get(m, 0.0) for m in months] for c in creditors},
        'matrix_payment': {c: [matrix_payment[c].get(m, 0.0) for m in months] for c in creditors},
    }


def filtered_monthly(dept=None, emp_region=None, employee=None, is_network=None,
                      creditor=None, debt_type=None, work_type=None):
    """То же, что overall_by_month(), но с фильтрами по Отделу/Региону сотрудника/
    Сотруднику/Сеть (страницы "ОСЗ/ОД Сбор" и "ОСЗ/ОД CBR" в BI)."""
    where, params = _cbr_filters_where(dept, emp_region, employee, is_network, creditor, debt_type, work_type)
    sql = f'''SELECT m.month, SUM(m.total_debt) AS total_debt, SUM(m.principal_debt) AS principal_debt,
                     SUM(m.payment_amount) AS payment_amount
              FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
              WHERE {where} GROUP BY 1 ORDER BY 1'''
    rows = query(sql, params)
    months = [r['month'] for r in rows]
    total_debt = [float(r['total_debt'] or 0) for r in rows]
    principal_debt = [float(r['principal_debt'] or 0) for r in rows]
    payment_amount = [float(r['payment_amount'] or 0) for r in rows]
    return {
        'months': [m.strftime('%m.%Y') for m in months],
        'total_debt': total_debt, 'principal_debt': principal_debt, 'payment_amount': payment_amount,
        'cbr_osz': [_cbr(payment_amount[i], total_debt[i]) for i in range(len(months))],
        'cbr_od': [_cbr(payment_amount[i], principal_debt[i]) for i in range(len(months))],
    }


def region_department_pivot(is_network=None, creditor=None, debt_type=None, work_type=None):
    """Rows = Регион(сотрудника) -> Отдел (2-уровневая иерархия), columns=месяц,
    values=CBR от ОСЗ % (страница "Регионы" в BI)."""
    where, params = _cbr_filters_where(is_network=is_network, creditor=creditor, debt_type=debt_type, work_type=work_type)
    sql = f'''SELECT m.month, COALESCE(e.region, 'Не указано') AS region,
                     COALESCE(e.department, 'Без отдела') AS department,
                     SUM(m.total_debt) AS total_debt, SUM(m.payment_amount) AS payment_amount
              FROM cbr.monthly m LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
              WHERE {where} GROUP BY 1, 2, 3 ORDER BY 1'''
    rows = query(sql, params)
    months = sorted({r['month'] for r in rows})
    tree = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        debt, payment = float(r['total_debt'] or 0), float(r['payment_amount'] or 0)
        tree[r['region']][r['department']][r['month']] = {
            'cbr': _cbr(payment, debt), 'debt': debt, 'payment': payment,
        }
    out = []
    for region in sorted(tree):
        depts = []
        for dept in sorted(tree[region]):
            cell = tree[region][dept]
            depts.append({
                'department': dept,
                'cbr_osz': [cell.get(m, {}).get('cbr', 0.0) for m in months],
                'debt': [cell.get(m, {}).get('debt', 0.0) for m in months],
                'payment': [cell.get(m, {}).get('payment', 0.0) for m in months],
            })
        out.append({'region': region, 'departments': depts})
    return {'months': [m.strftime('%m.%Y') for m in months], 'regions': out}


def get_filter_options():
    """Списки значений для срезов Отдел/Регион(сотрудника)/Сотрудник/Текущий
    кредитор/Тип долга/Тип работы."""
    depts = query("SELECT DISTINCT department FROM cbr.employee_mapping WHERE department IS NOT NULL ORDER BY 1")
    regions = query("SELECT DISTINCT region FROM cbr.employee_mapping WHERE region IS NOT NULL ORDER BY 1")
    employees = query("SELECT DISTINCT employee FROM cbr.employee_mapping WHERE employee IS NOT NULL ORDER BY 1")
    creditors = query("SELECT DISTINCT creditor FROM cbr.monthly WHERE creditor IS NOT NULL ORDER BY 1")
    debt_types = query("SELECT DISTINCT debt_type FROM cbr.monthly WHERE debt_type IS NOT NULL ORDER BY 1")
    work_types = query("SELECT DISTINCT work_type FROM cbr.monthly WHERE work_type IS NOT NULL ORDER BY 1")
    return {
        'departments': [r['department'] for r in depts],
        'emp_regions': [r['region'] for r in regions],
        'employees': [r['employee'] for r in employees],
        'creditors': [r['creditor'] for r in creditors],
        'debt_types': [r['debt_type'] for r in debt_types],
        'work_types': [r['work_type'] for r in work_types],
    }


CELL_METRICS = {'total_debt', 'principal_debt', 'payment_amount', 'do_count', 'payment_count'}


def cell_detail(month, metric, creditor=None, debt_type=None, work_type=None):
    """Детализация ячейки Таблицы CBR (месяц + метрика) -> разбивка по Текущему
    кредитору, Типу долга, Типу работы, Отделу и Сотруднику. metric — один из
    CELL_METRICS (то, что суммируется в ячейке; проценты CBR не декомпозируются,
    поэтому не кликабельны)."""
    if metric not in CELL_METRICS:
        raise ValueError(f'Неизвестная метрика: {metric}')
    where, params = _core_where('m.', creditor, debt_type, work_type)
    rows = query(
        f'''SELECT m.creditor, m.debt_type, m.work_type,
                   COALESCE(e.department, 'Без отдела') AS department, m.employee,
                   SUM(m.{metric}) AS val
            FROM cbr.monthly m
            LEFT JOIN cbr.employee_mapping e ON e.employee = m.employee
            WHERE m.month = %s AND {where}
            GROUP BY 1, 2, 3, 4, 5''',
        [month] + params
    )

    def agg_by(key_fn):
        agg = defaultdict(float)
        for r in rows:
            agg[key_fn(r)] += float(r['val'] or 0)
        return [{'label': k, 'val': v} for k, v in sorted(agg.items(), key=lambda kv: -abs(kv[1]))]

    total = sum(float(r['val'] or 0) for r in rows)
    return {
        'total': total, 'row_count': len(rows),
        'by_creditor': agg_by(lambda r: r['creditor'] or 'Не указано'),
        'by_debt_type': agg_by(lambda r: r['debt_type'] or 'Не указано'),
        'by_work_type': agg_by(lambda r: r['work_type'] or 'Не указано'),
        'by_department': agg_by(lambda r: r['department']),
        'by_employee': agg_by(lambda r: r['employee'] or 'Не указано'),
    }


def get_employee_mapping():
    return query('SELECT * FROM cbr.employee_mapping ORDER BY department NULLS LAST, employee')


def update_employee_mapping(employee, department, region, is_fired, employment_type):
    from db import execute
    execute(
        '''UPDATE cbr.employee_mapping SET department = %s, region = %s, is_fired = %s, employment_type = %s, updated_at = now()
           WHERE employee = %s''',
        (department or None, region or None, is_fired, employment_type or None, employee)
    )


def get_creditor_project_mapping():
    """Все кредиторы из cbr.monthly (даже без пары) + текущий проект, если уже
    сопоставлен. Несопоставленные (project IS NULL) — первыми, чтобы их было видно
    сразу на /cbr/admin/creditors."""
    rows = query(
        '''SELECT m.creditor, p.project, p.updated_at
           FROM (SELECT DISTINCT creditor FROM cbr.monthly WHERE creditor IS NOT NULL) m
           LEFT JOIN cbr.creditor_project_mapping p ON p.creditor = m.creditor
           ORDER BY (p.project IS NULL) DESC, m.creditor'''
    )
    return rows


def set_creditor_project(creditor, project):
    from db import execute
    execute(
        '''INSERT INTO cbr.creditor_project_mapping (creditor, project, updated_at)
           VALUES (%s, %s, now())
           ON CONFLICT (creditor) DO UPDATE SET project = EXCLUDED.project, updated_at = now()''',
        (creditor, project or None)
    )


def export_rows(overall):
    headers = ['Месяц', 'ОСЗ всего', 'ОСЗ всего, шт', 'Основной долг', 'Платежи за месяц',
               'Платежей за месяц, шт', 'CBR от ОСЗ %', 'CBR от ОД %']
    rows = [
        [overall['months'][i], overall['total_debt'][i], overall['do_count'][i], overall['principal_debt'][i],
         overall['payment_amount'][i], overall['payment_count'][i], overall['cbr_osz'][i], overall['cbr_od'][i]]
        for i in range(len(overall['months']))
    ]
    return [('CBR', headers, rows)]
