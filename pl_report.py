"""П&Л-отчётность: Свод1, Свод2, Dashboard1, Dashboard2, UNIT+PL.

Структура строк построчно снята с формул эталонного Excel-отчёта
(02_Отчетность_202606_fin_new.xlsx, листы Свод1/Свод2) и сверена с БД
до копейки — см. контекст в ~/.claude/plans/inherited-twirling-dawn.md.
Источник данных — reporting.pl_monthly (period, line, project, pf, amount),
материализованное представление поверх public."FinancialData".
"""
from collections import defaultdict

from db import query

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

REVENUE_LINES = [
    'Выручка DP (цессия)',
    'Выручка DCA (агентская)',
    'Депозиты',
    'Прочая выручка (перепродажа)',
]

VARIABLE_LINES = [
    'Агентское вознаграждение',
    'Гос. пошлина (ВПК)',
    'Нотариус и регистрация',
    'ФОТ переменный',
    'Заработная плата (кэшбэк)',
    'Премия за изъятие авто',
    'Стоянка авто (служба изъятия)',
    'Эвакуатор (служба изъятия)',
    'ГСМ (служба изъятия)',
    'Почтовые расходы',
    'Банковские расходы',
    'Прочие операционные расходы',
    'Информация',
    'Командировка',
    'Офисные Расходы',
    'Представительские Расходы, Поездки',
    'Прочие Доходы',
    'Прочие Расходы',
    'Связь',
    'Штраф',
    'Экспертиза',
    'Прочие',
    'Налоги на дивиденды',
    'Штрафы',
]

FIXED_LINES = [
    'ФОТ постоянный',
    'Аренда',
    'IT и оборудование',
    'Налог на прибыль',
    'Внутренние перемещения (нетто)',
    'Лизинг и авто',
    'Не в отчёте (остатки на начало)',
    'Обслуживание долга (проценты)',
]

BONUS_LINES = ['Бонус Генерального директора', 'Бонус Руководитель взыскания']
INVESTMENT_LINE = 'Покупка портфелей (цессия)'
FINANCING_LINES = ['Займ приход', 'Возврат тела займа', 'Дивиденды учредителям']

ALL_LINES = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES + BONUS_LINES + [INVESTMENT_LINE] + FINANCING_LINES

SECTIONS = [
    ('  ВЫРУЧКА', REVENUE_LINES, 'Итого выручка'),
    ('  РАСХОДЫ ПЕРЕМЕННЫЕ', VARIABLE_LINES, 'Итого переменные'),
    ('  РАСХОДЫ ПОСТОЯННЫЕ', FIXED_LINES, 'Итого постоянные'),
]


def _empty_months():
    return {m: 0.0 for m in range(1, 13)}


def _fetch_year(year, pf):
    """{line: {month: amount_thousands}} для всех ALL_LINES за год."""
    rows = query(
        '''SELECT extract(month FROM period)::int AS m, line, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = %s AND pf = %s AND line = ANY(%s)
           GROUP BY 1, 2''',
        (year, pf, ALL_LINES)
    )
    by_line = defaultdict(_empty_months)
    for r in rows:
        by_line[r['line']][r['m']] = r['val']
    return by_line


def _fetch_all_years(years, pf):
    """{year: {line: {month: amount_thousands}}} одним запросом на все года сразу."""
    rows = query(
        '''SELECT extract(year FROM period)::int AS y, extract(month FROM period)::int AS m,
                  line, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = ANY(%s) AND pf = %s AND line = ANY(%s)
           GROUP BY 1, 2, 3''',
        (years, pf, ALL_LINES)
    )
    by_year = {y: defaultdict(_empty_months) for y in years}
    for r in rows:
        by_year[r['y']][r['line']][r['m']] = r['val']
    return by_year


def _sum_lines(by_line, lines, months=range(1, 13)):
    total = _empty_months()
    for line in lines:
        vals = by_line.get(line, {})
        for m in months:
            total[m] += vals.get(m, 0.0)
    return total


def _series(d):
    return [d[m] for m in range(1, 13)]


def svod1(year, pf='факт'):
    """Свод1: П&Л по месяцам одного года."""
    by_line = _fetch_year(year, pf)
    rows = []
    section_totals = {}

    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            rows.append({'kind': 'line', 'label': line, 'vals': _series(by_line.get(line, _empty_months()))})
        total = _sum_lines(by_line, lines)
        section_totals[total_label] = total
        rows.append({'kind': 'subtotal', 'label': total_label, 'vals': _series(total)})

    profit = _empty_months()
    for m in range(1, 13):
        profit[m] = (section_totals['Итого выручка'][m] + section_totals['Итого переменные'][m]
                     + section_totals['Итого постоянные'][m])
    rows.append({'kind': 'total', 'label': 'ПРИБЫЛЬ', 'vals': _series(profit)})

    rows.append({'kind': 'header', 'label': '  БОНУСЫ МЕНЕДЖЕРОВ (% от ЧП) — с июня 2026'})
    for line in BONUS_LINES:
        rows.append({'kind': 'line', 'label': line, 'vals': _series(by_line.get(line, _empty_months()))})
    profit_after_bonus = _sum_lines(by_line, BONUS_LINES)
    rows.append({'kind': 'subtotal', 'label': 'Прибыль после бонусов', 'vals': _series(profit_after_bonus)})

    rows.append({'kind': 'header', 'label': '  ИНВЕСТИЦИИ В ПОРТФЕЛИ'})
    investment = by_line.get(INVESTMENT_LINE, _empty_months())
    rows.append({'kind': 'line', 'label': INVESTMENT_LINE, 'vals': _series(investment)})

    rows.append({'kind': 'header', 'label': '  ФИНАНСИРОВАНИЕ'})
    for line in FINANCING_LINES:
        rows.append({'kind': 'line', 'label': line, 'vals': _series(by_line.get(line, _empty_months()))})
    financing_total = _sum_lines(by_line, FINANCING_LINES)
    rows.append({'kind': 'subtotal', 'label': 'Итого финансирование', 'vals': _series(financing_total)})

    net_profit = _empty_months()
    for m in range(1, 13):
        net_profit[m] = profit_after_bonus[m] + financing_total[m] + investment[m] + profit[m]
    rows.append({'kind': 'total', 'label': '💰 ЧИСТАЯ ПРИБЫЛЬ / КЭШ ФЛОУ', 'vals': _series(net_profit)})

    return {'rows': rows, 'months': MONTHS_RU, 'profit': _series(profit), 'net_profit': _series(net_profit)}


def get_available_years():
    rows = query('SELECT DISTINCT extract(year FROM period)::int AS y FROM reporting.pl_monthly ORDER BY 1')
    return [r['y'] for r in rows]


def get_pf_values():
    rows = query('SELECT DISTINCT pf FROM reporting.pl_monthly ORDER BY 1')
    return [r['pf'] for r in rows]


def get_projects():
    rows = query(
        '''SELECT DISTINCT project FROM reporting.pl_monthly
           WHERE project ILIKE '(DCA)%%' OR project ILIKE '(DP)%%' ORDER BY 1'''
    )
    return [r['project'] for r in rows]


def _fetch_year_by_project(year, pf, lines):
    rows = query(
        '''SELECT extract(month FROM period)::int AS m, project, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = %s AND pf = %s AND line = ANY(%s)
           GROUP BY 1, 2''',
        (year, pf, lines)
    )
    by_project = defaultdict(_empty_months)
    for r in rows:
        by_project[r['project']][r['m']] = r['val']
    return by_project


def _project_breakdown(year, pf, lines, section_total, top_n=15):
    by_project = _fetch_year_by_project(year, pf, lines)
    dca = [p for p in by_project if p.startswith('(DCA)')]
    dp = [p for p in by_project if p.startswith('(DP)')]

    def rank(projects):
        return sorted(projects, key=lambda p: -sum(abs(v) for v in by_project[p].values()))[:top_n]

    dca_shown = rank(dca)
    dp_shown = rank(dp)

    dca_total = _sum_lines(by_project, dca)
    dp_total = _sum_lines(by_project, dp)
    other_total = _empty_months()
    for m in range(1, 13):
        other_total[m] = section_total[m] - dca_total[m] - dp_total[m]

    block = []
    block.append({'kind': 'subtotal', 'label': 'DCA', 'vals': _series(dca_total)})
    for p in dca_shown:
        block.append({'kind': 'line', 'label': p, 'vals': _series(by_project[p])})
    block.append({'kind': 'subtotal', 'label': 'DP', 'vals': _series(dp_total)})
    for p in dp_shown:
        block.append({'kind': 'line', 'label': p, 'vals': _series(by_project[p])})
    block.append({'kind': 'line', 'label': 'Прочие', 'vals': _series(other_total)})
    return block


def svod2(year, pf='факт'):
    """Свод2: Свод1, но ВЫРУЧКА/ПЕРЕМЕННЫЕ/ПОСТОЯННЫЕ разбиты по портфелям (DCA/DP)."""
    by_line = _fetch_year(year, pf)
    revenue_total = _sum_lines(by_line, REVENUE_LINES)
    variable_total = _sum_lines(by_line, VARIABLE_LINES)
    fixed_total = _sum_lines(by_line, FIXED_LINES)

    rows = []
    rows.append({'kind': 'header', 'label': '  ВЫРУЧКА'})
    rows.append({'kind': 'total', 'label': 'Итого выручка', 'vals': _series(revenue_total)})
    rows.extend(_project_breakdown(year, pf, REVENUE_LINES, revenue_total))

    rows.append({'kind': 'header', 'label': '  РАСХОДЫ ПЕРЕМЕННЫЕ'})
    rows.append({'kind': 'total', 'label': 'Итого переменные', 'vals': _series(variable_total)})
    rows.extend(_project_breakdown(year, pf, VARIABLE_LINES, variable_total))

    gm_total = _empty_months()
    for m in range(1, 13):
        gm_total[m] = revenue_total[m] + variable_total[m]
    rows.append({'kind': 'header', 'label': '  GM (Выручка + Переменные)'})
    rows.append({'kind': 'total', 'label': 'GM', 'vals': _series(gm_total)})

    rows.append({'kind': 'header', 'label': '  РАСХОДЫ ПОСТОЯННЫЕ'})
    rows.append({'kind': 'total', 'label': 'Итого постоянные', 'vals': _series(fixed_total)})
    rows.extend(_project_breakdown(year, pf, FIXED_LINES, fixed_total))

    profit = _empty_months()
    for m in range(1, 13):
        profit[m] = revenue_total[m] + variable_total[m] + fixed_total[m]
    rows.append({'kind': 'total', 'label': 'ПРИБЫЛЬ', 'vals': _series(profit)})

    return {'rows': rows, 'months': MONTHS_RU, 'profit': _series(profit)}


def unit_pl(pf_history='факт', pf_forecast='план'):
    """UNIT+PL: непрерывный ряд по всей истории — факт там, где он есть, иначе план."""
    years = get_available_years()
    rows_by_line = {line: [] for line in ALL_LINES}
    period_labels = []

    fact_by_year = _fetch_all_years(years, pf_history)
    plan_by_year = _fetch_all_years(years, pf_forecast)

    profit_series = []
    net_profit_series = []
    source_series = []

    for y in years:
        fact = fact_by_year[y]
        plan = plan_by_year[y]
        for m in range(1, 13):
            has_fact = any(fact.get(line, {}).get(m, 0.0) != 0.0 for line in ALL_LINES)
            src = fact if has_fact else plan
            source_series.append('факт' if has_fact else 'план')
            period_labels.append(f'{MONTHS_RU[m - 1]} {y}')
            for line in ALL_LINES:
                rows_by_line[line].append(src.get(line, {}).get(m, 0.0))

    def col_sum(lines, idx):
        return sum(rows_by_line[line][idx] for line in lines)

    n = len(period_labels)
    for i in range(n):
        rev = col_sum(REVENUE_LINES, i)
        var = col_sum(VARIABLE_LINES, i)
        fix = col_sum(FIXED_LINES, i)
        profit = rev + var + fix
        bonus = col_sum(BONUS_LINES, i)
        fin = col_sum(FINANCING_LINES, i)
        inv = rows_by_line[INVESTMENT_LINE][i]
        profit_series.append(profit)
        net_profit_series.append(bonus + fin + inv + profit)

    rows = []
    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            rows.append({'kind': 'line', 'label': line, 'vals': rows_by_line[line]})
        rows.append({'kind': 'subtotal', 'label': total_label,
                      'vals': [col_sum(lines, i) for i in range(n)]})
    rows.append({'kind': 'total', 'label': 'ПРИБЫЛЬ', 'vals': profit_series})
    rows.append({'kind': 'total', 'label': '💰 ЧИСТАЯ ПРИБЫЛЬ / КЭШ ФЛОУ', 'vals': net_profit_series})

    return {'rows': rows, 'periods': period_labels, 'sources': source_series,
            'profit': profit_series, 'net_profit': net_profit_series}


def _batched_fetch(lines, years, month, pf, dim=None):
    """Одним проходом (2 запроса: месяц + накопительно) тянет суммы по всем годам сразу,
    опционально разбитые по dim (имя колонки, либо список колонок, например ['line','project']).
    Возвращает (month_map, ytd_map), ключ — год, либо (год, *значения dim)."""
    dims = [] if dim is None else ([dim] if isinstance(dim, str) else list(dim))
    group_cols = ['extract(year FROM period)::int AS y'] + dims
    group_sql = ', '.join(group_cols)
    group_by = ', '.join(str(i + 1) for i in range(len(group_cols)))

    def run(month_cmp):
        sql = f'''SELECT {group_sql}, SUM(amount) / 1000.0 AS val FROM reporting.pl_monthly
                  WHERE pf = %s AND line = ANY(%s) AND extract(year FROM period) = ANY(%s)
                    AND extract(month FROM period) {month_cmp} %s
                  GROUP BY {group_by}'''
        return query(sql, (pf, lines, years, month))

    def to_map(rows):
        if dims:
            return {(r['y'], *(r[d] for d in dims)): float(r['val'] or 0) for r in rows}
        return {r['y']: float(r['val'] or 0) for r in rows}

    return to_map(run('=')), to_map(run('<='))


def _yoy_row(label, years, plan_year, month_vals, ytd_vals, plan_month_vals, plan_ytd_vals, bold=False):
    fact_month = month_vals.get(plan_year, 0.0)
    fact_ytd = ytd_vals.get(plan_year, 0.0)
    plan_month = plan_month_vals.get(plan_year, 0.0)
    plan_ytd = plan_ytd_vals.get(plan_year, 0.0)
    prev_years = [y for y in years if y != plan_year]
    prev_year = max(prev_years) if prev_years else None
    return {
        'kind': 'subtotal' if bold else 'line',
        'label': label,
        'month_vals': [month_vals.get(y, 0.0) for y in years],
        'ytd_vals': [ytd_vals.get(y, 0.0) for y in years],
        'plan_month': plan_month,
        'plan_ytd': plan_ytd,
        'delta_pf_month': fact_month - plan_month,
        'delta_pf_ytd': fact_ytd - plan_ytd,
        'delta_ff_month': (fact_month - month_vals.get(prev_year, 0.0)) if prev_year else None,
        'delta_ff_ytd': (fact_ytd - ytd_vals.get(prev_year, 0.0)) if prev_year else None,
    }


def dashboard2(month, years, plan_year=None):
    """Dashboard2: Свод1-строки за один месяц, годы в столбцах + накопительно, план/факт.
    Всего 4 SQL-запроса независимо от числа строк/лет."""
    plan_year = plan_year or max(years)
    all_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    fact_month, fact_ytd = _batched_fetch(all_lines, years, month, 'факт', dim='line')
    plan_month, plan_ytd = _batched_fetch(all_lines, [plan_year], month, 'план', dim='line')

    def line_maps(line):
        fm = {y: fact_month.get((y, line), 0.0) for y in years}
        fy = {y: fact_ytd.get((y, line), 0.0) for y in years}
        pm = {plan_year: plan_month.get((plan_year, line), 0.0)}
        py = {plan_year: plan_ytd.get((plan_year, line), 0.0)}
        return fm, fy, pm, py

    rows = []
    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            rows.append(_yoy_row(line, years, plan_year, *line_maps(line)))

        fm = {y: sum(fact_month.get((y, l), 0.0) for l in lines) for y in years}
        fy = {y: sum(fact_ytd.get((y, l), 0.0) for l in lines) for y in years}
        pm = {plan_year: sum(plan_month.get((plan_year, l), 0.0) for l in lines)}
        py = {plan_year: sum(plan_ytd.get((plan_year, l), 0.0) for l in lines)}
        rows.append(_yoy_row(total_label, years, plan_year, fm, fy, pm, py, bold=True))
    return {'rows': rows, 'years': years, 'plan_year': plan_year, 'month_name': MONTHS_RU[month - 1]}


def dashboard1(month, years, plan_year=None, top_n=12):
    """Dashboard1: Свод2-разбивка по портфелям за один месяц, годы + накопительно.
    Всего 4 SQL-запроса (по line+project сразу, одним проходом на все 3 секции)."""
    plan_year = plan_year or max(years)
    all_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    line_to_section = {}
    for _, lines, total_label in SECTIONS:
        for line in lines:
            line_to_section[line] = total_label

    fact_month, fact_ytd = _batched_fetch(all_lines, years, month, 'факт', dim=['line', 'project'])
    plan_month, plan_ytd = _batched_fetch(all_lines, [plan_year], month, 'план', dim=['line', 'project'])

    def agg(data, year, section_lines, project=None):
        total = 0.0
        for (y, line, p), v in data.items():
            if y == year and line in section_lines and (project is None or p == project):
                total += v
        return total

    rows = []
    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        fm_total = {y: agg(fact_month, y, lines) for y in years}
        fy_total = {y: agg(fact_ytd, y, lines) for y in years}
        pm_total = {plan_year: agg(plan_month, plan_year, lines)}
        py_total = {plan_year: agg(plan_ytd, plan_year, lines)}
        rows.append(_yoy_row(total_label, years, plan_year, fm_total, fy_total, pm_total, py_total, bold=True))

        projects = sorted(
            {p for (y, line, p) in fact_month if y == plan_year and line in lines},
            key=lambda p: -abs(agg(fact_month, plan_year, lines, project=p))
        )[:top_n]
        for p in projects:
            fm = {y: agg(fact_month, y, lines, project=p) for y in years}
            fy = {y: agg(fact_ytd, y, lines, project=p) for y in years}
            pm = {plan_year: agg(plan_month, plan_year, lines, project=p)}
            py = {plan_year: agg(plan_ytd, plan_year, lines, project=p)}
            rows.append(_yoy_row(p, years, plan_year, fm, fy, pm, py))
    return {'rows': rows, 'years': years, 'plan_year': plan_year, 'month_name': MONTHS_RU[month - 1]}
