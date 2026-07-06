"""ФОТ v1 / ФОТ v2 — фонд оплаты труда по подразделениям и сотрудникам.

Источник — reporting.fot_monthly (period, dept, employee, pf, line, amount),
line IN ('ФОТ переменный','ФОТ постоянный'). Сверено с эталонным Excel до копейки
(Дирекция янв.2022 = 485587.07 руб, Зудин С.А. = 319543.07 руб).
Суммы в рублях (в отличие от pl_report — там всё в тыс.руб).
"""
from db import query
import export

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

DEPT_ORDER = ['Дирекция', 'Commercial', 'Legal', 'Field', 'Soft и прочее']


def _dept_sort_key(dept):
    return (DEPT_ORDER.index(dept), dept) if dept in DEPT_ORDER else (len(DEPT_ORDER), dept)


def get_available_years():
    rows = query('SELECT DISTINCT extract(year FROM period)::int AS y FROM reporting.fot_monthly ORDER BY 1')
    return [r['y'] for r in rows]


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
