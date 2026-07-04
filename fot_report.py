"""ФОТ v1 / ФОТ v2 — фонд оплаты труда по подразделениям и сотрудникам.

Источник — reporting.fot_monthly (period, dept, employee, pf, line, amount),
line IN ('ФОТ переменный','ФОТ постоянный'). Сверено с эталонным Excel до копейки
(Дирекция янв.2022 = 485587.07 руб, Зудин С.А. = 319543.07 руб).
Суммы в рублях (в отличие от pl_report — там всё в тыс.руб).
"""
from db import query

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

DEPT_ORDER = ['Дирекция', 'Commercial', 'Legal', 'Field', 'Soft и прочее']


def _dept_sort_key(dept):
    return (DEPT_ORDER.index(dept), dept) if dept in DEPT_ORDER else (len(DEPT_ORDER), dept)


def get_available_years():
    rows = query('SELECT DISTINCT extract(year FROM period)::int AS y FROM reporting.fot_monthly ORDER BY 1')
    return [r['y'] for r in rows]


def fot1(year, pf='факт', top_n_per_dept=15):
    """ФОТ v1: помесячно за один год, по подразделениям и (топ) сотрудникам.
    Подразделение — из reporting.employees (справочник, редактируется на
    /employees), если сотрудник ещё не докатегоризирован — берётся исходная
    группировка из FinancialData."Контрагент_report" (fm.dept)."""
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

    rows = []
    total_by_month = {m: 0.0 for m in range(1, 13)}
    for dept, employees in sorted(depts.items(), key=lambda kv: _dept_sort_key(kv[0])):
        dept_total = {m: sum(e[m] for e in employees.values()) for m in range(1, 13)}
        for m in range(1, 13):
            total_by_month[m] += dept_total[m]
        rows.append({'kind': 'subtotal', 'label': dept, 'vals': series(dept_total)})
        top_employees = sorted(employees.items(), key=lambda kv: -sum(abs(v) for v in kv[1].values()))[:top_n_per_dept]
        for emp, vals in top_employees:
            rows.append({'kind': 'line', 'label': emp, 'vals': series(vals)})

    rows.insert(0, {'kind': 'total', 'label': 'ФОТ (всего)', 'vals': series(total_by_month)})
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


def _series_row(label, series, deltas, month_map, ytd_map, bold=False):
    sm = [month_map.get(key, 0.0) for key in series]
    sy = [ytd_map.get(key, 0.0) for key in series]
    return {
        'kind': 'subtotal' if bold else 'line',
        'label': label,
        'series_month': sm,
        'series_ytd': sy,
        'delta_month': [sm[i] - sm[j] for i, j in deltas],
        'delta_ytd': [sy[i] - sy[j] for i, j in deltas],
    }


def fot2(month, series, deltas, top_n_per_dept=10):
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

    for dept in depts:
        mmd = {(pf, yr): agg(month_map, pf, yr, dept=dept) for pf, yr in series}
        ymd = {(pf, yr): agg(ytd_map, pf, yr, dept=dept) for pf, yr in series}
        rows.append(_series_row(dept, series, deltas, mmd, ymd, bold=True))

        employees = sorted(
            {e for (p_, y_, d, e) in month_map if p_ == latest_pf and y_ == latest_year and d == dept},
            key=lambda e: -abs(agg(month_map, latest_pf, latest_year, dept=dept, employee=e))
        )[:top_n_per_dept]
        for emp in employees:
            mme = {(pf, yr): agg(month_map, pf, yr, dept=dept, employee=emp) for pf, yr in series}
            yme = {(pf, yr): agg(ytd_map, pf, yr, dept=dept, employee=emp) for pf, yr in series}
            rows.append(_series_row(emp, series, deltas, mme, yme))

    return {'rows': rows, 'series': series, 'deltas': deltas, 'month_name': MONTHS_RU[month - 1]}
