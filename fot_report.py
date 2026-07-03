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
    """ФОТ v1: помесячно за один год, по подразделениям и (топ) сотрудникам."""
    rows_raw = query(
        '''SELECT extract(month FROM period)::int AS m, dept, employee, SUM(amount) AS val
           FROM reporting.fot_monthly
           WHERE extract(year FROM period) = %s AND pf = %s
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


def _batched_fetch(years, month, pf, top_dept_employee=None):
    where = ['pf = %s', 'extract(year FROM period) = ANY(%s)']
    params = [pf, years]
    if top_dept_employee:
        where.append('dept = %s AND employee = %s')
        params += list(top_dept_employee)

    def run(month_cmp):
        sql = f'''SELECT extract(year FROM period)::int AS y, dept, employee, SUM(amount) AS val
                  FROM reporting.fot_monthly
                  WHERE {' AND '.join(where)} AND extract(month FROM period) {month_cmp} %s
                  GROUP BY 1, 2, 3'''
        return query(sql, params + [month])

    def to_map(rows):
        return {(r['y'], r['dept'], r['employee']): float(r['val'] or 0) for r in rows}

    return to_map(run('=')), to_map(run('<='))


def fot2(month, years, plan_year=None, top_n_per_dept=10):
    """ФОТ v2: один месяц, годы в столбцах (факт) + план/факт текущего года + Δ."""
    plan_year = plan_year or max(years)
    fact_month, fact_ytd = _batched_fetch(years, month, 'факт')
    plan_month, plan_ytd = _batched_fetch([plan_year], month, 'план')

    depts = sorted({d for (y, d, e) in fact_month if y == plan_year}, key=_dept_sort_key)

    def agg(data, year, dept=None, employee=None):
        total = 0.0
        for (y, d, e), v in data.items():
            if y == year and (dept is None or d == dept) and (employee is None or e == employee):
                total += v
        return total

    def yoy_row(label, fm, fy, pm, py, bold=False):
        fact_m = fm.get(plan_year, 0.0)
        fact_y = fy.get(plan_year, 0.0)
        plan_m = pm.get(plan_year, 0.0)
        plan_y = py.get(plan_year, 0.0)
        prev_years = [y for y in years if y != plan_year]
        prev_year = max(prev_years) if prev_years else None
        return {
            'kind': 'subtotal' if bold else 'line',
            'label': label,
            'month_vals': [fm.get(y, 0.0) for y in years],
            'ytd_vals': [fy.get(y, 0.0) for y in years],
            'plan_month': plan_m,
            'plan_ytd': plan_y,
            'delta_pf_month': fact_m - plan_m,
            'delta_pf_ytd': fact_y - plan_y,
            'delta_ff_month': (fact_m - fm.get(prev_year, 0.0)) if prev_year else None,
            'delta_ff_ytd': (fact_y - fy.get(prev_year, 0.0)) if prev_year else None,
        }

    rows = []
    fm_all = {y: agg(fact_month, y) for y in years}
    fy_all = {y: agg(fact_ytd, y) for y in years}
    pm_all = {plan_year: agg(plan_month, plan_year)}
    py_all = {plan_year: agg(plan_ytd, plan_year)}
    rows.append(yoy_row('ФОТ (всего)', fm_all, fy_all, pm_all, py_all, bold=True))

    for dept in depts:
        fm = {y: agg(fact_month, y, dept=dept) for y in years}
        fy = {y: agg(fact_ytd, y, dept=dept) for y in years}
        pm = {plan_year: agg(plan_month, plan_year, dept=dept)}
        py = {plan_year: agg(plan_ytd, plan_year, dept=dept)}
        rows.append(yoy_row(dept, fm, fy, pm, py, bold=True))

        employees = sorted(
            {e for (y, d, e) in fact_month if y == plan_year and d == dept},
            key=lambda e: -abs(agg(fact_month, plan_year, dept=dept, employee=e))
        )[:top_n_per_dept]
        for emp in employees:
            fme = {y: agg(fact_month, y, dept=dept, employee=emp) for y in years}
            fye = {y: agg(fact_ytd, y, dept=dept, employee=emp) for y in years}
            pme = {plan_year: agg(plan_month, plan_year, dept=dept, employee=emp)}
            pye = {plan_year: agg(plan_ytd, plan_year, dept=dept, employee=emp)}
            rows.append(yoy_row(emp, fme, fye, pme, pye))

    return {'rows': rows, 'years': years, 'plan_year': plan_year, 'month_name': MONTHS_RU[month - 1]}
