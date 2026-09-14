"""Отчёты ФОТ по подразделениям и сотрудникам.

Источник — reporting.fot_monthly (period, dept, employee, pf, line, amount),
line IN ('ФОТ переменный','ФОТ постоянный','Премия за изъятие авто').
Сверено с эталонным Excel до копейки
(Дирекция янв.2022 = 485587.07 руб, Зудин С.А. = 319543.07 руб).
Суммы в рублях (в отличие от pl_report — там всё в тыс.руб).
"""
from collections import defaultdict
from datetime import date

from db import query
import export

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
MONTHS_FULL_RU = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

FOT_VARIABLE_LINE = 'ФОТ переменный'
FOT_FIXED_LINE = 'ФОТ постоянный'
REPOSSESSION_BONUS_LINE = 'Премия за изъятие авто'
FOT_LINES = (FOT_VARIABLE_LINE, FOT_FIXED_LINE, REPOSSESSION_BONUS_LINE)

DEPT_ORDER = ['Дирекция', 'Commercial', 'Legal', 'Field', 'Soft и прочее']


def _dept_sort_key(dept):
    return (DEPT_ORDER.index(dept), dept) if dept in DEPT_ORDER else (len(DEPT_ORDER), dept)


def get_available_years():
    rows = query('SELECT DISTINCT extract(year FROM period)::int AS y FROM reporting.fot_monthly ORDER BY 1')
    return [r['y'] for r in rows]


def get_period_bounds(pf='факт'):
    rows = query(
        'SELECT MIN(period) AS mn, MAX(period) AS mx '
        'FROM reporting.fot_monthly WHERE pf = %s',
        (pf,),
    )
    fallback = date.today().replace(day=1)
    if not rows:
        return fallback, fallback
    return rows[0]['mn'] or fallback, rows[0]['mx'] or fallback


def get_employees():
    """Все сотрудники из редактируемого справочника, включая добавленных вручную."""
    rows = query(
        "SELECT contragent FROM reporting.employees "
        "WHERE contragent <> '(без сотрудника)' ORDER BY contragent"
    )
    return [r['contragent'] for r in rows]


def fot3(employee, year, pf='факт'):
    """ФОТ v3: динамика начислений одному сотруднику по месяцам за год —
    ФОТ переменный / ФОТ постоянный / премия за изъятие авто и итого. Ячейки итога кликабельны на
    клиенте через тот же pr.cell_detail(contragent=[employee]), что и
    Свод1/Обзор — статьи и комментарии по месяцу."""
    rows = query(
        '''SELECT extract(month FROM fm.period)::int AS m, fm.line,
                  COALESCE(e.department, fm.dept) AS dept, SUM(fm.amount) AS val
           FROM reporting.fot_monthly fm
           LEFT JOIN reporting.employees e ON e.contragent = fm.employee
           WHERE extract(year FROM fm.period) = %s AND fm.pf = %s AND fm.employee = %s
           GROUP BY 1, 2, 3''',
        (year, pf, employee)
    )
    variable = {m: 0.0 for m in range(1, 13)}
    fixed = {m: 0.0 for m in range(1, 13)}
    repossession_bonus = {m: 0.0 for m in range(1, 13)}
    employee_rows = query(
        'SELECT department FROM reporting.employees WHERE contragent = %s',
        (employee,),
    )
    dept = employee_rows[0]['department'] if employee_rows else None
    for r in rows:
        dept = r['dept'] or dept
        if r['line'] == FOT_VARIABLE_LINE:
            variable[r['m']] += float(r['val'] or 0)
        elif r['line'] == FOT_FIXED_LINE:
            fixed[r['m']] += float(r['val'] or 0)
        elif r['line'] == REPOSSESSION_BONUS_LINE:
            repossession_bonus[r['m']] += float(r['val'] or 0)
    total = {
        m: variable[m] + fixed[m] + repossession_bonus[m]
        for m in range(1, 13)
    }

    def series(d):
        return [d[m] for m in range(1, 13)]

    return {
        'employee': employee, 'dept': dept, 'months': MONTHS_RU,
        'variable': series(variable), 'fixed': series(fixed),
        'repossession_bonus': series(repossession_bonus), 'total': series(total),
        'year_total': sum(total.values()),
    }


def fot1(year, pf='факт'):
    """ФОТ v1: помесячно за один год, по подразделениям и сотрудникам (все,
    ~350 на всю компанию — можно смело показывать целиком, без топ-N).
    Подразделение — из reporting.employees (справочник, редактируется на
    /employees), если сотрудник ещё не докатегоризирован — берётся исходная
    группировка из FinancialData."Контрагент_report" (fm.dept). Сотрудники
    свёрнуты по умолчанию — раскрываются кнопкой на строке подразделения.
    СЗП = ФОТ подразделения / численность (кол-во сотрудников с ненулевым
    начислением в месяце)."""
    rows_raw = query(
        '''SELECT extract(month FROM fm.period)::int AS m, COALESCE(e.department, fm.dept) AS dept,
                  fm.employee, SUM(fm.amount) AS val
           FROM reporting.fot_monthly fm
           LEFT JOIN reporting.employees e ON e.contragent = fm.employee
           WHERE extract(year FROM fm.period) = %s AND fm.pf = %s
           GROUP BY 1, 2, 3''',
        (year, pf)
    )
    depts = {}
    for r in rows_raw:
        d = depts.setdefault(r['dept'], {})
        e = d.setdefault(r['employee'], {m: 0.0 for m in range(1, 13)})
        e[r['m']] = float(r['val'] or 0)

    def series(d):
        return [d[m] for m in range(1, 13)]

    total_by_month = {m: 0.0 for m in range(1, 13)}
    total_headcount_sets = {m: set() for m in range(1, 13)}
    dept_rows = []
    for di, (dept, employees) in enumerate(sorted(depts.items(), key=lambda kv: _dept_sort_key(kv[0]))):
        dept_total = {m: sum(e[m] for e in employees.values()) for m in range(1, 13)}
        dept_headcount = {m: sum(1 for e in employees.values() if e[m] != 0.0) for m in range(1, 13)}
        dept_szp = {m: (dept_total[m] / dept_headcount[m] if dept_headcount[m] else 0.0) for m in range(1, 13)}
        for m in range(1, 13):
            total_by_month[m] += dept_total[m]
            for emp_name, vals in employees.items():
                if vals[m] != 0.0:
                    total_headcount_sets[m].add((dept, emp_name))

        row_id = f'dept-{di}'
        dept_rows.append({'kind': 'subtotal', 'label': dept, 'row_id': row_id, 'vals': series(dept_total)})
        dept_rows.append({'kind': 'metric', 'label': 'СЗП', 'unit': 'руб', 'vals': series(dept_szp)})
        dept_rows.append({'kind': 'metric', 'label': 'Численность', 'unit': 'чел', 'vals': series(dept_headcount)})
        all_employees = sorted(employees.items(), key=lambda kv: -sum(abs(v) for v in kv[1].values()))
        for emp, vals in all_employees:
            dept_rows.append({'kind': 'line', 'label': emp, 'parent_id': row_id, 'vals': series(vals)})

    total_headcount = {m: len(total_headcount_sets[m]) for m in range(1, 13)}
    total_szp = {m: (total_by_month[m] / total_headcount[m] if total_headcount[m] else 0.0) for m in range(1, 13)}

    rows = [
        {'kind': 'total', 'label': 'ФОТ (всего)', 'vals': series(total_by_month)},
        {'kind': 'metric', 'label': 'СЗП (всего)', 'unit': 'руб', 'vals': series(total_szp)},
        {'kind': 'metric', 'label': 'Численность (всего)', 'unit': 'чел', 'vals': series(total_headcount)},
    ] + dept_rows
    return {'rows': rows, 'months': MONTHS_RU}


def get_available_pf():
    rows = query('SELECT DISTINCT pf FROM reporting.fot_monthly ORDER BY 1')
    return [r['pf'] for r in rows]


def default_series_deltas(years):
    """Тот же дефолт, что в pl_report: факт(N-1), прогноз(N), факт(N) + 2 отклонения."""
    if not years:
        return [], []
    latest = max(years)
    sorted_years = sorted(years)
    prev = latest - 1 if (latest - 1) in years else (sorted_years[-2] if len(sorted_years) > 1 else latest)
    return [('факт', prev), ('прогноз', latest), ('факт', latest)], [(2, 0), (2, 1)]


def _batched_fetch(years, month, pf):
    def run(month_cmp):
        sql = f'''SELECT extract(year FROM fm.period)::int AS y, COALESCE(e.department, fm.dept) AS dept,
                         fm.employee, SUM(fm.amount) AS val
                  FROM reporting.fot_monthly fm
                  LEFT JOIN reporting.employees e ON e.contragent = fm.employee
                  WHERE fm.pf = %s AND extract(year FROM fm.period) = ANY(%s)
                    AND extract(month FROM fm.period) {month_cmp} %s
                  GROUP BY 1, 2, 3'''
        return query(sql, (pf, years, month))

    def to_map(rows):
        return {(r['y'], r['dept'], r['employee']): float(r['val'] or 0) for r in rows}

    return to_map(run('=')), to_map(run('<='))


def _series_row(label, series, deltas, month_map, ytd_map, bold=False, row_id=None, parent_id=None, kind=None, polarity=1):
    sm = [month_map.get(key, 0.0) for key in series]
    sy = [ytd_map.get(key, 0.0) for key in series]
    row = {
        'kind': kind or ('subtotal' if bold else 'line'),
        'label': label,
        'series_month': sm,
        'series_ytd': sy,
        'delta_month': [sm[i] - sm[j] for i, j in deltas],
        'delta_ytd': [sy[i] - sy[j] for i, j in deltas],
        'polarity': polarity,
    }
    if row_id:
        row['row_id'] = row_id
    if parent_id:
        row['parent_id'] = parent_id
    return row


def _headcount(data, pf, yr, dept=None):
    emps = set()
    for (p_, y_, d_, e_), v in data.items():
        if p_ == pf and y_ == yr and (dept is None or d_ == dept) and v != 0:
            emps.add(e_)
    return len(emps)


def fot2(month, series, deltas):
    """ФОТ v2: один месяц, настраиваемые колонки сравнения (см. pl_report.dashboard2)."""
    by_pf = {}
    for pf, year in series:
        by_pf.setdefault(pf, set()).add(year)

    month_map, ytd_map = {}, {}
    for pf, years_set in by_pf.items():
        m, y = _batched_fetch(sorted(years_set), month, pf)
        for (yr, d, e), v in m.items():
            month_map[(pf, yr, d, e)] = v
        for (yr, d, e), v in y.items():
            ytd_map[(pf, yr, d, e)] = v

    def agg(data, pf, yr, dept=None, employee=None):
        total = 0.0
        for (p_, y_, d_, e_), v in data.items():
            if p_ == pf and y_ == yr and (dept is None or d_ == dept) and (employee is None or e_ == employee):
                total += v
        return total

    latest_pf, latest_year = series[-1]
    depts = sorted(
        {d for (p_, y_, d, e) in month_map if p_ == latest_pf and y_ == latest_year},
        key=_dept_sort_key
    )

    rows = []
    mm = {(pf, yr): agg(month_map, pf, yr) for pf, yr in series}
    ym = {(pf, yr): agg(ytd_map, pf, yr) for pf, yr in series}
    rows.append(_series_row('ФОТ (всего)', series, deltas, mm, ym, bold=True))

    hc_mm = {(pf, yr): _headcount(month_map, pf, yr) for pf, yr in series}
    hc_ym = {(pf, yr): _headcount(ytd_map, pf, yr) for pf, yr in series}
    szp_mm = {(pf, yr): (mm[(pf, yr)] / hc_mm[(pf, yr)] if hc_mm[(pf, yr)] else 0.0) for pf, yr in series}
    szp_ym = {(pf, yr): (ym[(pf, yr)] / hc_ym[(pf, yr)] if hc_ym[(pf, yr)] else 0.0) for pf, yr in series}
    rows.append(_series_row('СЗП (всего)', series, deltas, szp_mm, szp_ym, kind='metric'))
    rows.append(_series_row('Численность (всего)', series, deltas, hc_mm, hc_ym, kind='metric'))

    for di, dept in enumerate(depts):
        row_id = f'dept-{di}'
        mmd = {(pf, yr): agg(month_map, pf, yr, dept=dept) for pf, yr in series}
        ymd = {(pf, yr): agg(ytd_map, pf, yr, dept=dept) for pf, yr in series}
        rows.append(_series_row(dept, series, deltas, mmd, ymd, bold=True, row_id=row_id))

        hc_mmd = {(pf, yr): _headcount(month_map, pf, yr, dept=dept) for pf, yr in series}
        hc_ymd = {(pf, yr): _headcount(ytd_map, pf, yr, dept=dept) for pf, yr in series}
        szp_mmd = {(pf, yr): (mmd[(pf, yr)] / hc_mmd[(pf, yr)] if hc_mmd[(pf, yr)] else 0.0) for pf, yr in series}
        szp_ymd = {(pf, yr): (ymd[(pf, yr)] / hc_ymd[(pf, yr)] if hc_ymd[(pf, yr)] else 0.0) for pf, yr in series}
        rows.append(_series_row('СЗП', series, deltas, szp_mmd, szp_ymd, kind='metric'))
        rows.append(_series_row('Численность', series, deltas, hc_mmd, hc_ymd, kind='metric'))

        employees = sorted(
            {e for (p_, y_, d, e) in month_map if p_ == latest_pf and y_ == latest_year and d == dept},
            key=lambda e: -abs(agg(month_map, latest_pf, latest_year, dept=dept, employee=e))
        )
        for emp in employees:
            mme = {(pf, yr): agg(month_map, pf, yr, dept=dept, employee=emp) for pf, yr in series}
            yme = {(pf, yr): agg(ytd_map, pf, yr, dept=dept, employee=emp) for pf, yr in series}
            rows.append(_series_row(emp, series, deltas, mme, yme, parent_id=row_id))

    return {'rows': rows, 'series': series, 'deltas': deltas, 'month_name': MONTHS_RU[month - 1]}


def _months_between(start, end):
    return (end.year - start.year) * 12 + end.month - start.month + 1


def _period_label(start, end, mode='period'):
    if start == end:
        label = f'{MONTHS_FULL_RU[start.month - 1]} {start.year}'
    elif start.year == end.year:
        label = f'{MONTHS_FULL_RU[start.month - 1]} — {MONTHS_FULL_RU[end.month - 1]} {end.year}'
    else:
        label = (
            f'{MONTHS_FULL_RU[start.month - 1]} {start.year} — '
            f'{MONTHS_FULL_RU[end.month - 1]} {end.year}'
        )
    return f'{label} · накопительно' if mode == 'ytd' else label


def _comparison_period(start, end, mode):
    start = start.replace(day=1)
    end = end.replace(day=1)
    if start > end:
        raise ValueError('Начало периода не может быть позже окончания')
    effective_start = date(end.year, 1, 1) if mode == 'ytd' else start
    return {
        'selected_start': start,
        'selected_end': end,
        'start': effective_start,
        'end': end,
        'months_count': _months_between(effective_start, end),
        'label': _period_label(effective_start, end, mode),
    }


def _comparison_delta(value_a, value_b):
    delta = value_b - value_a
    if abs(value_a) < 0.005:
        percent = 0.0 if abs(value_b) < 0.005 else None
    else:
        percent = delta / abs(value_a) * 100.0
    return delta, percent


def _comparison_row(label, value_a, value_b, period_a, period_b, *, kind='line',
                    unit='руб.', row_id=None, parent_id=None, department=None,
                    employee=None, can_detail=True):
    delta, delta_percent = _comparison_delta(value_a, value_b)
    row = {
        'kind': kind,
        'label': label,
        'unit': unit,
        'value_a': value_a,
        'value_b': value_b,
        'delta': delta,
        'delta_percent': delta_percent,
        'monthly_average_a': (
            value_a / period_a['months_count'] if can_detail else None
        ),
        'monthly_average_b': (
            value_b / period_b['months_count'] if can_detail else None
        ),
        'department': department,
        'employee': employee,
        'can_detail': can_detail,
        'lines': list(FOT_LINES),
    }
    if row_id:
        row['row_id'] = row_id
    if parent_id:
        row['parent_id'] = parent_id
    return row


def period_comparison(start_a, end_a, start_b, end_b, mode='period'):
    """Сравнивает два произвольных периода фактического ФОТ в структуре ФОТ v2."""
    if mode not in ('period', 'ytd'):
        raise ValueError('Неизвестный режим расчёта')

    period_a = _comparison_period(start_a, end_a, mode)
    period_b = _comparison_period(start_b, end_b, mode)
    rows_raw = query(
        '''SELECT COALESCE(e.department, fm.dept) AS dept, fm.employee,
                  COALESCE(SUM(fm.amount) FILTER (
                      WHERE fm.period BETWEEN %s AND %s), 0) AS value_a,
                  COALESCE(SUM(fm.amount) FILTER (
                      WHERE fm.period BETWEEN %s AND %s), 0) AS value_b,
                  COUNT(DISTINCT fm.period) FILTER (
                      WHERE fm.period BETWEEN %s AND %s AND fm.amount <> 0) AS active_months_a,
                  COUNT(DISTINCT fm.period) FILTER (
                      WHERE fm.period BETWEEN %s AND %s AND fm.amount <> 0) AS active_months_b
           FROM reporting.fot_monthly fm
           LEFT JOIN reporting.employees e ON e.contragent = fm.employee
           WHERE fm.pf = 'факт'
             AND ((fm.period BETWEEN %s AND %s) OR (fm.period BETWEEN %s AND %s))
           GROUP BY 1, 2''',
        (
            period_a['start'], period_a['end'],
            period_b['start'], period_b['end'],
            period_a['start'], period_a['end'],
            period_b['start'], period_b['end'],
            period_a['start'], period_a['end'],
            period_b['start'], period_b['end'],
        ),
    )

    employees = {}
    departments = defaultdict(list)
    for raw in rows_raw:
        dept = raw['dept'] or '(без подразделения)'
        employee = raw['employee']
        values = {
            'department': dept,
            'employee': employee,
            'value_a': float(raw['value_a'] or 0),
            'value_b': float(raw['value_b'] or 0),
            'active_months_a': (
                int(raw['active_months_a'] or 0)
                if employee != '(без сотрудника)' else 0
            ),
            'active_months_b': (
                int(raw['active_months_b'] or 0)
                if employee != '(без сотрудника)' else 0
            ),
        }
        employees[(dept, employee)] = values
        departments[dept].append(values)

    total_a = sum(item['value_a'] for item in employees.values())
    total_b = sum(item['value_b'] for item in employees.values())
    employee_months_a = sum(item['active_months_a'] for item in employees.values())
    employee_months_b = sum(item['active_months_b'] for item in employees.values())
    headcount_a = employee_months_a / period_a['months_count']
    headcount_b = employee_months_b / period_b['months_count']
    salary_a = total_a / employee_months_a if employee_months_a else 0.0
    salary_b = total_b / employee_months_b if employee_months_b else 0.0

    total_row = _comparison_row(
        'ФОТ (всего)', total_a, total_b, period_a, period_b, kind='total'
    )
    salary_row = _comparison_row(
        'СЗП (всего)', salary_a, salary_b, period_a, period_b,
        kind='metric', can_detail=False,
    )
    headcount_row = _comparison_row(
        'Средняя численность (всего)', headcount_a, headcount_b, period_a, period_b,
        kind='metric', unit='чел.', can_detail=False,
    )
    rows = [total_row, salary_row, headcount_row]
    employee_rows = []
    department_rows = []

    for index, dept in enumerate(sorted(departments, key=_dept_sort_key)):
        dept_employees = departments[dept]
        dept_a = sum(item['value_a'] for item in dept_employees)
        dept_b = sum(item['value_b'] for item in dept_employees)
        dept_employee_months_a = sum(
            item['active_months_a'] for item in dept_employees
        )
        dept_employee_months_b = sum(
            item['active_months_b'] for item in dept_employees
        )
        dept_hc_a = dept_employee_months_a / period_a['months_count']
        dept_hc_b = dept_employee_months_b / period_b['months_count']
        dept_salary_a = (
            dept_a / dept_employee_months_a if dept_employee_months_a else 0.0
        )
        dept_salary_b = (
            dept_b / dept_employee_months_b if dept_employee_months_b else 0.0
        )
        row_id = f'dept-{index}'
        dept_row = _comparison_row(
            dept, dept_a, dept_b, period_a, period_b, kind='subtotal',
            row_id=row_id, department=dept,
        )
        rows.append(dept_row)
        department_rows.append(dept_row)
        rows.append(_comparison_row(
            'СЗП', dept_salary_a, dept_salary_b, period_a, period_b,
            kind='metric', department=dept, can_detail=False,
        ))
        rows.append(_comparison_row(
            'Средняя численность', dept_hc_a, dept_hc_b, period_a, period_b,
            kind='metric', unit='чел.', department=dept, can_detail=False,
        ))

        sorted_employees = sorted(
            dept_employees,
            key=lambda item: (
                -abs(item['value_b'] - item['value_a']),
                -max(abs(item['value_a']), abs(item['value_b'])),
                item['employee'],
            ),
        )
        for item in sorted_employees:
            employee_row = _comparison_row(
                item['employee'], item['value_a'], item['value_b'],
                period_a, period_b, parent_id=row_id, department=dept,
                employee=item['employee'],
            )
            rows.append(employee_row)
            employee_rows.append(employee_row)

    drivers = sorted(employee_rows, key=lambda row: -abs(row['delta']))[:10]
    return {
        'rows': rows,
        'kpis': [total_row, salary_row, headcount_row],
        'drivers': drivers,
        'department_rows': department_rows,
        'period_a': period_a,
        'period_b': period_b,
        'mode': mode,
        'fact_only': True,
    }


def _fot_detail_result(rows, period):
    by_stat3 = {}
    by_project = defaultdict(float)
    total = 0.0
    row_count = 0
    for row in rows:
        amount = float(row['amount'] or 0)
        operations = int(row['operation_count'] or 0)
        total += amount
        row_count += operations
        project = (row['project'] or '').strip() or '(без проекта)'
        by_project[project] += amount
        stat3 = (row['stat3'] or '').strip() or '(без статьи)'
        contragent = (row['contragent'] or '').strip() or '(без сотрудника)'
        comment = (row['comment'] or '').strip()
        section = by_stat3.setdefault(stat3, {'total': 0.0, 'contragents': {}})
        section['total'] += amount
        employee = section['contragents'].setdefault(
            contragent, {'total': 0.0, 'comments': []}
        )
        employee['total'] += amount
        if comment:
            if operations > 1:
                comment = f'{comment} · {operations} оп.'
            employee['comments'].append({
                'comment': comment, 'amount': amount, 'project': project,
            })

    stat3_list = []
    for stat3, section in by_stat3.items():
        counterparties = []
        for contragent, employee in section['contragents'].items():
            employee['comments'].sort(key=lambda item: -abs(item['amount']))
            counterparties.append({
                'contragent': contragent,
                'total': employee['total'],
                'comments': employee['comments'][:50],
            })
        counterparties.sort(key=lambda item: -abs(item['total']))
        stat3_list.append({
            'stat3': stat3,
            'total': section['total'],
            'contragents': counterparties,
        })
    stat3_list.sort(key=lambda item: -abs(item['total']))
    projects_list = sorted(
        ({'project': project, 'total': amount} for project, amount in by_project.items()),
        key=lambda item: -abs(item['total']),
    )
    return {
        'total': total,
        'by_statya3': stat3_list,
        'by_project': projects_list,
        'row_count': row_count,
        'period_label': period['label'],
    }


def period_detail(start, end, department=None, employee=None):
    """Детализация фактического ФОТ за диапазон до статьи, сотрудника и операции."""
    period = _comparison_period(start, end, 'period')
    dept_expr = (
        "COALESCE(e.department, COALESCE(NULLIF(TRIM(fd.\"Контрагент_report\"), ''), "
        "'(без подразделения)'))"
    )
    employee_expr = "COALESCE(NULLIF(TRIM(fd.\"Контрагент\"), ''), '(без сотрудника)')"
    sql = f'''SELECT fd."Строка отчета" AS stat3, {employee_expr} AS contragent,
                     fd."Комментарии" AS comment, fd."Проект" AS project,
                     SUM(fd."Сумма") AS amount, COUNT(*) AS operation_count
              FROM public."FinancialData" fd
              LEFT JOIN reporting.employees e ON e.contragent = {employee_expr}
              WHERE fd."Строка отчета" = ANY(%s)
                AND fd."Период" BETWEEN %s AND %s AND fd."п_ф" = 'факт' '''
    params = [list(FOT_LINES), period['start'], period['end']]
    if department:
        sql += f' AND {dept_expr} = %s'
        params.append(department)
    if employee:
        sql += f' AND {employee_expr} = %s'
        params.append(employee)
    sql += ' GROUP BY 1, 2, 3, 4'
    return _fot_detail_result(query(sql, params), period)


def _raw_group_period(start, end, department=None, employee=None):
    dept_expr = (
        "COALESCE(e.department, COALESCE(NULLIF(TRIM(fd.\"Контрагент_report\"), ''), "
        "'(без подразделения)'))"
    )
    employee_expr = "COALESCE(NULLIF(TRIM(fd.\"Контрагент\"), ''), '(без сотрудника)')"
    sql = f'''SELECT fd."Проект" AS project, fd."Строка отчета" AS stat3,
                     {employee_expr} AS contragent, SUM(fd."Сумма") AS amount
              FROM public."FinancialData" fd
              LEFT JOIN reporting.employees e ON e.contragent = {employee_expr}
              WHERE fd."Строка отчета" = ANY(%s)
                AND fd."Период" BETWEEN %s AND %s AND fd."п_ф" = 'факт' '''
    params = [list(FOT_LINES), start, end]
    if department:
        sql += f' AND {dept_expr} = %s'
        params.append(department)
    if employee:
        sql += f' AND {employee_expr} = %s'
        params.append(employee)
    sql += ' GROUP BY 1, 2, 3'
    result = {}
    for row in query(sql, params):
        key = (
            (row['project'] or '').strip() or '(без проекта)',
            (row['stat3'] or '').strip() or '(без статьи)',
            (row['contragent'] or '').strip() or '(без сотрудника)',
        )
        result[key] = result.get(key, 0.0) + float(row['amount'] or 0)
    return result


def period_deviation_detail(start_a, end_a, start_b, end_b, department=None,
                            employee=None, top_n=30):
    """Крупнейшие первичные драйверы отклонения ФОТ B − A."""
    period_a = _comparison_period(start_a, end_a, 'period')
    period_b = _comparison_period(start_b, end_b, 'period')
    values_a = _raw_group_period(
        period_a['start'], period_a['end'], department, employee
    )
    values_b = _raw_group_period(
        period_b['start'], period_b['end'], department, employee
    )
    drivers = []
    for key in set(values_a) | set(values_b):
        value_a = values_a.get(key, 0.0)
        value_b = values_b.get(key, 0.0)
        delta = value_b - value_a
        if abs(delta) < 0.5:
            continue
        drivers.append({
            'project': key[0], 'stat3': key[1], 'contragent': key[2],
            'a': value_a, 'b': value_b, 'delta': delta,
        })
    total_delta = sum(values_b.values()) - sum(values_a.values())
    drivers.sort(
        key=lambda item: (
            0 if (item['delta'] >= 0) == (total_delta >= 0) else 1,
            -abs(item['delta']),
        )
    )
    return {
        'total_delta': total_delta,
        'drivers': drivers[:top_n],
        'label_a': period_a['label'],
        'label_b': period_b['label'],
    }


def export_fot1(data):
    headers = ['Подразделение/сотрудник'] + data['months']
    return [('ФОТ v1', headers, export.flatten_rows(data['rows'], ('vals',)))]


def export_fot2(data):
    series_headers = [f'{pf} {y}' for pf, y in data['series']]
    delta_headers = [f'Δ ({data["series"][i][0]}{data["series"][i][1]}-{data["series"][j][0]}{data["series"][j][1]})'
                      for i, j in data['deltas']]
    headers = ['Подразделение/сотрудник'] + series_headers + delta_headers
    month_rows = export.flatten_rows(data['rows'], ('series_month', 'delta_month'))
    ytd_rows = export.flatten_rows(data['rows'], ('series_ytd', 'delta_ytd'))
    return [('ФОТ v2 Месяц', headers, month_rows), ('ФОТ v2 Накопительно', headers, ytd_rows)]


def export_period_comparison(data):
    label_a = data['period_a']['label']
    label_b = data['period_b']['label']
    headers = [
        'Подразделение / сотрудник', 'Единица', f'A: {label_a}', f'B: {label_b}',
        'Δ B−A', 'Δ, %', 'Среднее/мес. A', 'Среднее/мес. B',
    ]
    rows = []
    for row in data['rows']:
        label = f'    {row["label"]}' if row.get('parent_id') else row['label']
        rows.append([
            label, row['unit'], row['value_a'], row['value_b'], row['delta'],
            row['delta_percent'], row['monthly_average_a'], row['monthly_average_b'],
        ])
    parameters = [
        ['Источник', 'Только факт'],
        ['Период A', label_a],
        ['Период B', label_b],
        ['Режим', (
            'Накопительно с начала года'
            if data['mode'] == 'ytd' else 'За выбранный период'
        )],
        ['Состав ФОТ', ', '.join(FOT_LINES)],
    ]
    return [
        ('ФОТ анализ изменений', headers, rows),
        ('Параметры', ['Параметр', 'Значение'], parameters),
    ]


def export_fot3(data, year=None, pf=None):
    """Экспорт карточки сотрудника: параметры и помесячная структура ФОТ."""
    headers = ['Показатель'] + data['months'] + ['Итого']
    rows = [
        [FOT_VARIABLE_LINE, *data['variable'], sum(data['variable'])],
        [FOT_FIXED_LINE, *data['fixed'], sum(data['fixed'])],
        [REPOSSESSION_BONUS_LINE, *data['repossession_bonus'], sum(data['repossession_bonus'])],
        ['Итого', *data['total'], data['year_total']],
    ]
    parameters = [
        ['Сотрудник', data['employee']],
        ['Подразделение', data.get('dept') or '—'],
        ['Год', year],
        ['Сценарий', pf],
    ]
    return [
        ('ФОТ v3', headers, rows),
        ('Параметры', ['Параметр', 'Значение'], parameters),
    ]
