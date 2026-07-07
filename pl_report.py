"""П&Л-отчётность: Свод1, Свод2, Dashboard1, Dashboard2, UNIT+PL.

Структура строк построчно снята с формул эталонного Excel-отчёта
(02_Отчетность_202606_fin_new.xlsx, листы Свод1/Свод2) и сверена с БД
до копейки — см. контекст в ~/.claude/plans/inherited-twirling-dawn.md.
Источник данных — reporting.pl_monthly (period, line, project, pf, amount),
материализованное представление поверх public."FinancialData".
"""
from collections import defaultdict
from datetime import date

from db import query
import export

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
FINANCING_LINES = ['Займ приход', 'Возврат тела займа', 'Чужие деньги', 'Дивиденды учредителям']

ALL_LINES = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES + BONUS_LINES + [INVESTMENT_LINE] + FINANCING_LINES

SECTIONS = [
    ('  ВЫРУЧКА', REVENUE_LINES, 'Итого выручка'),
    ('  РАСХОДЫ ПЕРЕМЕННЫЕ', VARIABLE_LINES, 'Итого переменные'),
    ('  РАСХОДЫ ПОСТОЯННЫЕ', FIXED_LINES, 'Итого постоянные'),
]


def _empty_months():
    return {m: 0.0 for m in range(1, 13)}


def _alloc_where(allocation='all'):
    """С учётом распределения (по умолчанию, 'all') — берём обе строки
    "Распределение" (до распределения + распределение), т.е. без фильтра.
    Без учёта ('no_alloc') — только строки "до распределения", отбрасываем
    распределённую по проектам часть постоянных затрат целиком. Тот же принцип,
    что investment_report._cost_case()."""
    return " AND allocation = 'до распределения'" if allocation == 'no_alloc' else ''


def _fetch_year(year, pf, allocation='all'):
    """{line: {month: amount_thousands}} для всех ALL_LINES за год."""
    rows = query(
        f'''SELECT extract(month FROM period)::int AS m, line, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = %s AND pf = %s AND line = ANY(%s){_alloc_where(allocation)}
           GROUP BY 1, 2''',
        (year, pf, ALL_LINES)
    )
    by_line = defaultdict(_empty_months)
    for r in rows:
        by_line[r['line']][r['m']] = r['val']
    return by_line


def _fetch_all_years(years, pf, allocation='all'):
    """{year: {line: {month: amount_thousands}}} одним запросом на все года сразу."""
    rows = query(
        f'''SELECT extract(year FROM period)::int AS y, extract(month FROM period)::int AS m,
                  line, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = ANY(%s) AND pf = %s AND line = ANY(%s){_alloc_where(allocation)}
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


def _is_all_zero(vals):
    return all(abs(v) < 0.005 for v in vals)


def _fetch_statya3_detail(year, pf, lines, allocation='all'):
    """{line: {month: [{stat3, val}, ...]}} — для подсказки при наведении, из
    reporting.pl_monthly_stat3 (не из "живой" FinancialData — там широкий запрос
    на год выполняется секунды, таблица не помещается в кеш на этом тарифе)."""
    rows = query(
        f'''SELECT extract(month FROM period)::int AS m, line, stat3, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly_stat3
           WHERE extract(year FROM period) = %s AND pf = %s AND line = ANY(%s){_alloc_where(allocation)}
           GROUP BY 1, 2, 3''',
        (year, pf, lines)
    )
    detail = defaultdict(lambda: defaultdict(list))
    for r in rows:
        detail[r['line']][r['m']].append({'stat3': r['stat3'], 'val': r['val']})
    for line, months in detail.items():
        for m in months:
            months[m].sort(key=lambda d: -abs(d['val']))
    return detail


def svod1(year, pf='факт', allocation='all'):
    """Свод1: П&Л по месяцам одного года. Строки, пустые за весь период
    (сейчас неактуальные для этого п_ф в текущей классификации БД), не показываем —
    как только по ним появятся данные, они вернутся сами. Для каждой строки
    добавлена детализация до СтатьяУровень3 (row['detail'][m]) — используется
    подсказкой при наведении на клиенте, без дополнительных запросов.
    allocation: 'all' (с распределением затрат, по умолчанию) / 'no_alloc' (без)."""
    by_line = _fetch_year(year, pf, allocation)
    all_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    statya3_detail = _fetch_statya3_detail(year, pf, all_lines, allocation)
    rows = []
    section_totals = {}

    for header, lines, total_label in SECTIONS:
        focus = 'projects' if lines is REVENUE_LINES else 'statya'
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            vals = _series(by_line.get(line, _empty_months()))
            if _is_all_zero(vals):
                continue
            line_detail = statya3_detail.get(line, {})
            rows.append({
                'kind': 'line', 'label': line, 'vals': vals, 'focus': focus,
                'detail': [line_detail.get(m, []) for m in range(1, 13)],
            })
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
        vals = _series(by_line.get(line, _empty_months()))
        if _is_all_zero(vals):
            continue
        rows.append({'kind': 'line', 'label': line, 'vals': vals})
    profit_after_bonus = _sum_lines(by_line, BONUS_LINES)
    rows.append({'kind': 'subtotal', 'label': 'Прибыль после бонусов', 'vals': _series(profit_after_bonus)})

    rows.append({'kind': 'header', 'label': '  ИНВЕСТИЦИИ В ПОРТФЕЛИ'})
    investment = by_line.get(INVESTMENT_LINE, _empty_months())
    if not _is_all_zero(_series(investment)):
        rows.append({'kind': 'line', 'label': INVESTMENT_LINE, 'vals': _series(investment)})

    rows.append({'kind': 'header', 'label': '  ФИНАНСИРОВАНИЕ'})
    for line in FINANCING_LINES:
        vals = _series(by_line.get(line, _empty_months()))
        if _is_all_zero(vals):
            continue
        rows.append({'kind': 'line', 'label': line, 'vals': vals})
    financing_total = _sum_lines(by_line, FINANCING_LINES)
    rows.append({'kind': 'subtotal', 'label': 'Итого финансирование', 'vals': _series(financing_total)})

    net_profit = _empty_months()
    for m in range(1, 13):
        net_profit[m] = profit_after_bonus[m] + financing_total[m] + investment[m] + profit[m]
    rows.append({'kind': 'total', 'label': '💰 ЧИСТАЯ ПРИБЫЛЬ / КЭШ ФЛОУ', 'vals': _series(net_profit)})

    gm = _empty_months()
    for m in range(1, 13):
        gm[m] = section_totals['Итого выручка'][m] + section_totals['Итого переменные'][m]

    for row in rows:
        if 'vals' in row:
            row['vals'] = row['vals'] + [sum(row['vals'])]

    return {
        'rows': rows, 'months': MONTHS_RU + ['Итого'], 'profit': _series(profit), 'net_profit': _series(net_profit),
        'revenue_series': _series(section_totals['Итого выручка']),
        'variable_series': _series(section_totals['Итого переменные']),
        'fixed_series': _series(section_totals['Итого постоянные']),
        'gm_series': _series(gm),
    }


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


def get_projects_with_type():
    """Справочник проектов для мультиселекта на Dashboard1/2: [(tip_project_1, [name, ...])]."""
    rows = query('SELECT "name", tip_project_1 FROM public.projects ORDER BY tip_project_1, "name"')
    groups = defaultdict(list)
    for r in rows:
        groups[r['tip_project_1'] or 'Прочие'].append(r['name'])
    return sorted(groups.items())


def _fetch_year_by_project(year, pf, lines, allocation='all'):
    rows = query(
        f'''SELECT extract(month FROM period)::int AS m, project, SUM(amount) / 1000.0 AS val
           FROM reporting.pl_monthly
           WHERE extract(year FROM period) = %s AND pf = %s AND line = ANY(%s){_alloc_where(allocation)}
           GROUP BY 1, 2''',
        (year, pf, lines)
    )
    by_project = defaultdict(_empty_months)
    for r in rows:
        by_project[r['project']][r['m']] = r['val']
    return by_project


_PROJECT_TYPE_CACHE = None


def _project_type_map():
    """{project_name: (tip_project_1, tip_project_2)} — из public.projects; кэш на процесс
    (справочник маленький и меняется редко, но переживём рестарт процесса при деплое)."""
    global _PROJECT_TYPE_CACHE
    if _PROJECT_TYPE_CACHE is None:
        rows = query('SELECT "name", tip_project_1, tip_project_2 FROM public.projects')
        _PROJECT_TYPE_CACHE = {r['name']: (r['tip_project_1'] or 'Прочие', r['tip_project_2'] or 'Прочие') for r in rows}
    return _PROJECT_TYPE_CACHE


def _project_hierarchy_from_dict(by_project, section_id):
    """Общая сборка свёрнутой по умолчанию 3-уровневой иерархии tip_project_1 ->
    tip_project_2 -> проект из уже посчитанного {project: {month: val}} — используется
    и для секций-строк (выручка/переменные/постоянные), и для производных (GM)."""
    type_map = _project_type_map()

    tree = defaultdict(lambda: defaultdict(list))
    for p in by_project:
        tip1, tip2 = type_map.get(p, ('Прочие', 'Прочие'))
        tree[tip1][tip2].append(p)

    rows = []
    for i1, tip1 in enumerate(sorted(tree)):
        row_id1 = f'{section_id}-{i1}'
        tip1_total = _empty_months()
        for tip2, projects in tree[tip1].items():
            for p in projects:
                for m in range(1, 13):
                    tip1_total[m] += by_project[p][m]
        rows.append({
            'kind': 'subtotal', 'label': tip1, 'vals': _series(tip1_total),
            'level': 1, 'row_id': row_id1, 'parent_id': None,
        })
        for i2, tip2 in enumerate(sorted(tree[tip1])):
            row_id2 = f'{row_id1}-{i2}'
            projects = tree[tip1][tip2]
            tip2_total = _sum_lines(by_project, projects)
            rows.append({
                'kind': 'subtotal', 'label': tip2, 'vals': _series(tip2_total),
                'level': 2, 'row_id': row_id2, 'parent_id': row_id1,
            })
            for p in sorted(projects):
                rows.append({
                    'kind': 'line', 'label': p, 'vals': _series(by_project[p]),
                    'level': 3, 'row_id': f'{row_id2}-{p}', 'parent_id': row_id2,
                })
    return rows


def _project_hierarchy(year, pf, lines, section_id, allocation='all'):
    """Свёрнутая по умолчанию 3-уровневая иерархия: tip_project_1 -> tip_project_2 ->
    проект (справочник public.projects; проекты не из справочника — в "Прочие"). Полное
    разбиение — сумма всех строк уровня 1 точно равна итогу секции."""
    by_project = _fetch_year_by_project(year, pf, lines, allocation)
    return _project_hierarchy_from_dict(by_project, section_id)


def _project_hierarchy_gm(year, pf, section_id, allocation='all'):
    """GM по портфелям = выручка + переменные по каждому проекту (переменные уже со
    знаком минус — как и для итогового GM в svod2/overview, просто складываем)."""
    revenue_by_project = _fetch_year_by_project(year, pf, REVENUE_LINES, allocation)
    variable_by_project = _fetch_year_by_project(year, pf, VARIABLE_LINES, allocation)
    gm_by_project = defaultdict(_empty_months)
    for p in set(revenue_by_project) | set(variable_by_project):
        for m in range(1, 13):
            gm_by_project[p][m] = revenue_by_project[p][m] + variable_by_project[p][m]
    return _project_hierarchy_from_dict(gm_by_project, section_id)


def svod2(year, pf='факт', allocation='all'):
    """Свод2: Свод1, но ВЫРУЧКА/ПЕРЕМЕННЫЕ/ПОСТОЯННЫЕ разбиты по иерархии портфелей
    tip_project_1 -> tip_project_2 -> проект (public.projects), свёрнуто по умолчанию."""
    by_line = _fetch_year(year, pf, allocation)
    revenue_total = _sum_lines(by_line, REVENUE_LINES)
    variable_total = _sum_lines(by_line, VARIABLE_LINES)
    fixed_total = _sum_lines(by_line, FIXED_LINES)

    rows = []
    rows.append({'kind': 'header', 'label': '  ВЫРУЧКА'})
    rows.append({'kind': 'total', 'label': 'Итого выручка', 'vals': _series(revenue_total)})
    rows.extend(_project_hierarchy(year, pf, REVENUE_LINES, 'rev', allocation))

    rows.append({'kind': 'header', 'label': '  РАСХОДЫ ПЕРЕМЕННЫЕ'})
    rows.append({'kind': 'total', 'label': 'Итого переменные', 'vals': _series(variable_total)})
    rows.extend(_project_hierarchy(year, pf, VARIABLE_LINES, 'var', allocation))

    gm_total = _empty_months()
    for m in range(1, 13):
        gm_total[m] = revenue_total[m] + variable_total[m]
    rows.append({'kind': 'header', 'label': '  GM (Выручка + Переменные)'})
    rows.append({'kind': 'total', 'label': 'GM', 'vals': _series(gm_total)})
    rows.extend(_project_hierarchy_gm(year, pf, 'gm', allocation))

    rows.append({'kind': 'header', 'label': '  РАСХОДЫ ПОСТОЯННЫЕ'})
    rows.append({'kind': 'total', 'label': 'Итого постоянные', 'vals': _series(fixed_total)})
    rows.extend(_project_hierarchy(year, pf, FIXED_LINES, 'fix', allocation))

    profit = _empty_months()
    for m in range(1, 13):
        profit[m] = revenue_total[m] + variable_total[m] + fixed_total[m]
    rows.append({'kind': 'total', 'label': 'ПРИБЫЛЬ', 'vals': _series(profit)})

    for row in rows:
        if 'vals' in row:
            row['vals'] = row['vals'] + [sum(row['vals'])]

    return {'rows': rows, 'months': MONTHS_RU + ['Итого'], 'profit': _series(profit)}


def unit_pl(pf_history='факт', pf_forecast='план', start=None, end=None, allocation='all'):
    """UNIT+PL: непрерывный ряд по всей истории — факт там, где он есть, иначе план.
    start/end — индексы диапазона (включительно) в полном списке периодов; None = весь ряд."""
    years = get_available_years()
    rows_by_line = {line: [] for line in ALL_LINES}
    period_labels = []
    periods_meta = []

    fact_by_year = _fetch_all_years(years, pf_history, allocation)
    plan_by_year = _fetch_all_years(years, pf_forecast, allocation)

    profit_series = []
    net_profit_series = []

    for y in years:
        fact = fact_by_year[y]
        plan = plan_by_year[y]
        for m in range(1, 13):
            has_fact = any(fact.get(line, {}).get(m, 0.0) != 0.0 for line in ALL_LINES)
            src = fact if has_fact else plan
            pf = pf_history if has_fact else pf_forecast
            label = f'{MONTHS_RU[m - 1]} {y}'
            period_labels.append(label)
            periods_meta.append({'label': label, 'year': y, 'month': m, 'pf': pf})
            for line in ALL_LINES:
                rows_by_line[line].append(src.get(line, {}).get(m, 0.0))

    def col_sum(lines, idx):
        return sum(rows_by_line[line][idx] for line in lines)

    n_full = len(period_labels)
    for i in range(n_full):
        rev = col_sum(REVENUE_LINES, i)
        var = col_sum(VARIABLE_LINES, i)
        fix = col_sum(FIXED_LINES, i)
        profit = rev + var + fix
        bonus = col_sum(BONUS_LINES, i)
        fin = col_sum(FINANCING_LINES, i)
        inv = rows_by_line[INVESTMENT_LINE][i]
        profit_series.append(profit)
        net_profit_series.append(bonus + fin + inv + profit)

    start = start if start is not None and 0 <= start < n_full else 0
    end = end if end is not None and start <= end < n_full else n_full - 1
    sl = slice(start, end + 1)

    def endpoint_delta(vals):
        rng = vals[sl]
        return (rng[-1] - rng[0]) if len(rng) > 1 else 0.0

    rows = []
    all_profit_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    all_net_lines = all_profit_lines + BONUS_LINES + FINANCING_LINES + [INVESTMENT_LINE]

    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            vals = rows_by_line[line]
            rows.append({'kind': 'line', 'label': line, 'lines': [line],
                         'vals': vals[sl], 'endpoint_delta': endpoint_delta(vals)})
        subtotal_vals = [col_sum(lines, i) for i in range(n_full)]
        rows.append({'kind': 'subtotal', 'label': total_label, 'lines': lines,
                     'vals': subtotal_vals[sl], 'endpoint_delta': endpoint_delta(subtotal_vals)})
    rows.append({'kind': 'total', 'label': 'ПРИБЫЛЬ', 'lines': all_profit_lines,
                 'vals': profit_series[sl], 'endpoint_delta': endpoint_delta(profit_series)})
    rows.append({'kind': 'total', 'label': '💰 ЧИСТАЯ ПРИБЫЛЬ / КЭШ ФЛОУ', 'lines': all_net_lines,
                 'vals': net_profit_series[sl], 'endpoint_delta': endpoint_delta(net_profit_series)})

    revenue_series = [col_sum(REVENUE_LINES, i) for i in range(n_full)]
    cost_series = [col_sum(VARIABLE_LINES, i) + col_sum(FIXED_LINES, i) for i in range(n_full)]

    return {
        'rows': rows,
        'periods': period_labels[sl],
        'periods_meta': periods_meta[sl],
        'full_periods_meta': periods_meta,
        'start_idx': start, 'end_idx': end,
        'profit': profit_series[sl], 'net_profit': net_profit_series[sl],
        'revenue_series': revenue_series[sl], 'cost_series': cost_series[sl],
        'endpoint_a': periods_meta[end], 'endpoint_b': periods_meta[start],
    }


def _batched_fetch(lines, years, month, pf, dim=None, projects=None, allocation='all'):
    """Одним проходом (2 запроса: месяц + накопительно) тянет суммы по всем годам сразу,
    опционально разбитые по dim (имя колонки, либо список колонок, например ['line','project'])
    и отфильтрованные по списку проектов. Возвращает (month_map, ytd_map), ключ — год,
    либо (год, *значения dim)."""
    dims = [] if dim is None else ([dim] if isinstance(dim, str) else list(dim))
    group_cols = ['extract(year FROM period)::int AS y'] + dims
    group_sql = ', '.join(group_cols)
    group_by = ', '.join(str(i + 1) for i in range(len(group_cols)))
    project_filter = ' AND project = ANY(%s)' if projects else ''

    def run(month_cmp):
        sql = f'''SELECT {group_sql}, SUM(amount) / 1000.0 AS val FROM reporting.pl_monthly
                  WHERE pf = %s AND line = ANY(%s) AND extract(year FROM period) = ANY(%s)
                    AND extract(month FROM period) {month_cmp} %s{project_filter}{_alloc_where(allocation)}
                  GROUP BY {group_by}'''
        params = [pf, lines, years, month]
        if projects:
            params.append(projects)
        return query(sql, params)

    def to_map(rows):
        if dims:
            return {(r['y'], *(r[d] for d in dims)): float(r['val'] or 0) for r in rows}
        return {r['y']: float(r['val'] or 0) for r in rows}

    return to_map(run('=')), to_map(run('<='))


def default_series_deltas(years):
    """Дефолт: факт(N-1), прогноз(N), факт(N) + отклонения факт(N)-факт(N-1) и
    факт(N)-прогноз(N), где N — последний доступный год."""
    if not years:
        return [], []
    latest = max(years)
    sorted_years = sorted(years)
    prev = latest - 1 if (latest - 1) in years else (sorted_years[-2] if len(sorted_years) > 1 else latest)
    series = [('факт', prev), ('прогноз', latest), ('факт', latest)]
    deltas = [(2, 0), (2, 1)]
    return series, deltas


def _series_row(label, series, deltas, month_map, ytd_map, bold=False, lines=None, project=None, polarity=1):
    """polarity: +1 — рост показателя это хорошо (зелёный при Δ>0), по умолчанию;
    -1 — для показателей вроде остатка долга, где рост это плохо (зелёный при Δ<0)."""
    sm = [month_map.get(key, 0.0) for key in series]
    sy = [ytd_map.get(key, 0.0) for key in series]
    return {
        'kind': 'subtotal' if bold else 'line',
        'label': label,
        'series_month': sm,
        'series_ytd': sy,
        'delta_month': [sm[i] - sm[j] for i, j in deltas],
        'delta_ytd': [sy[i] - sy[j] for i, j in deltas],
        'lines': lines,
        'project': project,
        'polarity': polarity,
    }


def dashboard2(month, series, deltas, projects=None, allocation='all'):
    """Dashboard2: Свод1-строки за один месяц, настраиваемые колонки сравнения
    (series = [(pf, year), ...], deltas = [(i, j), ...] => series[i]-series[j]),
    опционально отфильтровано по проектам. Кол-во SQL = 2 × число разных pf в series."""
    all_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    by_pf = defaultdict(set)
    for pf, year in series:
        by_pf[pf].add(year)

    month_map, ytd_map = {}, {}
    for pf, years_set in by_pf.items():
        m, y = _batched_fetch(all_lines, sorted(years_set), month, pf, dim='line', projects=projects, allocation=allocation)
        for (yr, line), v in m.items():
            month_map[(pf, yr, line)] = v
        for (yr, line), v in y.items():
            ytd_map[(pf, yr, line)] = v

    rows = []
    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        for line in lines:
            mm = {(pf, yr): month_map.get((pf, yr, line), 0.0) for pf, yr in series}
            ym = {(pf, yr): ytd_map.get((pf, yr, line), 0.0) for pf, yr in series}
            row = _series_row(line, series, deltas, mm, ym, lines=[line], project=projects)
            if _is_all_zero(row['series_month']) and _is_all_zero(row['series_ytd']):
                continue
            rows.append(row)

        mm = {(pf, yr): sum(month_map.get((pf, yr, l), 0.0) for l in lines) for pf, yr in series}
        ym = {(pf, yr): sum(ytd_map.get((pf, yr, l), 0.0) for l in lines) for pf, yr in series}
        rows.append(_series_row(total_label, series, deltas, mm, ym, bold=True, lines=lines, project=projects))
    return {'rows': rows, 'series': series, 'deltas': deltas, 'month_name': MONTHS_RU[month - 1]}


def dashboard1(month, series, deltas, projects=None, top_n=12, allocation='all'):
    """Dashboard1: Свод2-разбивка по портфелям, настраиваемые колонки сравнения (см.
    dashboard2). Кол-во SQL = 2 × число разных pf в series."""
    all_lines = REVENUE_LINES + VARIABLE_LINES + FIXED_LINES
    by_pf = defaultdict(set)
    for pf, year in series:
        by_pf[pf].add(year)

    month_map, ytd_map = {}, {}
    for pf, years_set in by_pf.items():
        m, y = _batched_fetch(all_lines, sorted(years_set), month, pf, dim=['line', 'project'], projects=projects, allocation=allocation)
        for (yr, line, p), v in m.items():
            month_map[(pf, yr, line, p)] = v
        for (yr, line, p), v in y.items():
            ytd_map[(pf, yr, line, p)] = v

    def agg(data, pf, yr, lines, project=None):
        total = 0.0
        for (p_, y_, line_, proj_), v in data.items():
            if p_ == pf and y_ == yr and line_ in lines and (project is None or proj_ == project):
                total += v
        return total

    latest_pf, latest_year = series[-1]

    rows = []
    for header, lines, total_label in SECTIONS:
        rows.append({'kind': 'header', 'label': header})
        mm = {(pf, yr): agg(month_map, pf, yr, lines) for pf, yr in series}
        ym = {(pf, yr): agg(ytd_map, pf, yr, lines) for pf, yr in series}
        rows.append(_series_row(total_label, series, deltas, mm, ym, bold=True, lines=lines, project=projects))

        candidate_projects = projects or sorted(
            {p for (p_, y_, l_, p) in month_map if p_ == latest_pf and y_ == latest_year and l_ in lines},
            key=lambda p: -abs(agg(month_map, latest_pf, latest_year, lines, project=p))
        )[:top_n]
        for p in candidate_projects:
            mmp = {(pf, yr): agg(month_map, pf, yr, lines, project=p) for pf, yr in series}
            ymp = {(pf, yr): agg(ytd_map, pf, yr, lines, project=p) for pf, yr in series}
            row = _series_row(p, series, deltas, mmp, ymp, lines=lines, project=[p])
            if _is_all_zero(row['series_month']) and _is_all_zero(row['series_ytd']):
                continue
            rows.append(row)

        if lines is VARIABLE_LINES:
            gm_lines = REVENUE_LINES + VARIABLE_LINES
            mm_gm = {(pf, yr): agg(month_map, pf, yr, gm_lines) for pf, yr in series}
            ym_gm = {(pf, yr): agg(ytd_map, pf, yr, gm_lines) for pf, yr in series}
            rows.append(_series_row('GM (Валовая прибыль)', series, deltas, mm_gm, ym_gm, bold=True, lines=gm_lines, project=projects))
    return {'rows': rows, 'series': series, 'deltas': deltas, 'month_name': MONTHS_RU[month - 1]}


def portfolio_pl_summary(project, year=None, pf='факт', allocation='all'):
    """Выручка/переменные/постоянные расходы/GM по ОДНОМУ портфелю (проекту) —
    для чат-тула (вопросы про маржинальность конкретного портфеля). Переиспользует
    dashboard1() с фильтром projects=[project]: раз запрос уже ограничен одним
    проектом, его "Итого X" строки (обычно свод по компании) фактически и есть
    показатели этого портфеля. Возвращает None, если портфель не найден (в т.ч.
    по частичному регистронезависимому совпадению имени)."""
    all_projects = get_projects()
    match = next((p for p in all_projects if p == project), None)
    if match is None:
        match = next((p for p in all_projects if project.lower() in p.lower()), None)
    if match is None:
        return None
    if year is None:
        year = get_latest_period(pf).year
    latest = get_latest_period(pf)
    month = latest.month if latest.year == year else 12
    data = dashboard1(month, [(pf, year)], [], projects=[match], top_n=1, allocation=allocation)
    out = {'project': match, 'year': year, 'pf': pf, 'month_name': data['month_name']}
    wanted = {'Итого выручка': 'revenue', 'Итого переменные': 'variable_costs',
              'Итого постоянные': 'fixed_costs', 'GM (Валовая прибыль)': 'gm'}
    for row in data['rows']:
        key = wanted.get(row.get('label'))
        if key:
            out[key] = {'month': row['series_month'][0], 'ytd': row['series_ytd'][0]}
    if 'revenue' in out and 'gm' in out:
        rev_m, gm_m = out['revenue']['month'], out['gm']['month']
        rev_y, gm_y = out['revenue']['ytd'], out['gm']['ytd']
        out['gm_pct'] = {
            'month': (gm_m / rev_m * 100) if rev_m else None,
            'ytd': (gm_y / rev_y * 100) if rev_y else None,
        }
    return out


def cell_detail(lines, year, month, pf, projects=None, allocation='all', contragent=None):
    """Детализация ячейки Свод1/Dashboard2 (lines — список "Строка отчета", обычно
    одна строка, для итоговых строк — весь список секции): дерево
    СтатьяУровень3 -> Контрагент -> [{comment, amount, project}], плюс отдельно
    разбивка по проектам. Живой запрос к FinancialData — узкий фильтр
    (Строка отчета + Период + п_ф), под индекс idx_financialdata_line_period_pf,
    выполняется за единицы миллисекунд. contragent — доп. фильтр по "Контрагент"
    (используется ФОТ v3 для детализации начисления одному сотруднику)."""
    if isinstance(lines, str):
        lines = [lines]
    period = date(year, month, 1)
    sql = '''SELECT "СтатьяУровень3" AS stat3, "Контрагент" AS contragent, "Комментарии" AS comment,
                    "Проект" AS project, "Сумма" AS amount
             FROM public."FinancialData"
             WHERE "Строка отчета" = ANY(%s) AND "Период" = %s AND "п_ф" = %s'''
    params = [lines, period, pf]
    if projects:
        sql += ' AND "Проект" = ANY(%s)'
        params.append(projects)
    if contragent:
        sql += ' AND "Контрагент" = ANY(%s)'
        params.append(contragent)
    if allocation == 'no_alloc':
        sql += " AND \"Распределение\" = 'до распределения'"
    rows = query(sql, params)

    by_stat3 = {}
    by_project = defaultdict(float)
    total = 0.0
    for r in rows:
        amt = float(r['amount'] or 0)
        total += amt
        proj = (r['project'] or '').strip() or '(без проекта)'
        by_project[proj] += amt

        stat3 = (r['stat3'] or '').strip() or '(без статьи)'
        contragent = (r['contragent'] or '').strip() or '(без контрагента)'
        comment = (r['comment'] or '').strip()

        s = by_stat3.setdefault(stat3, {'total': 0.0, 'contragents': {}})
        s['total'] += amt
        c = s['contragents'].setdefault(contragent, {'total': 0.0, 'comments': []})
        c['total'] += amt
        if comment:
            c['comments'].append({'comment': comment, 'amount': amt, 'project': proj})

    stat3_list = []
    for stat3, s in by_stat3.items():
        contragents = []
        for contragent, c in s['contragents'].items():
            c['comments'].sort(key=lambda x: -abs(x['amount']))
            contragents.append({
                'contragent': contragent, 'total': c['total'],
                'comments': c['comments'][:50],
            })
        contragents.sort(key=lambda x: -abs(x['total']))
        stat3_list.append({'stat3': stat3, 'total': s['total'], 'contragents': contragents})
    stat3_list.sort(key=lambda x: -abs(x['total']))

    project_list = sorted(
        ({'project': p, 'total': t} for p, t in by_project.items()),
        key=lambda x: -abs(x['total'])
    )

    return {'total': total, 'by_statya3': stat3_list, 'by_project': project_list, 'row_count': len(rows)}


def _raw_group(lines, year, month, pf, projects=None, allocation='all'):
    """{(project, stat3, contragent): amount} — живой запрос, узкий фильтр (под
    idx_financialdata_line_period_pf), для акт-анализа отклонений."""
    period = date(year, month, 1)
    sql = '''SELECT "Проект" AS project, "СтатьяУровень3" AS stat3, "Контрагент" AS contragent,
                    SUM("Сумма") AS amount
             FROM public."FinancialData"
             WHERE "Строка отчета" = ANY(%s) AND "Период" = %s AND "п_ф" = %s'''
    params = [lines, period, pf]
    if projects:
        sql += ' AND "Проект" = ANY(%s)'
        params.append(projects)
    if allocation == 'no_alloc':
        sql += " AND \"Распределение\" = 'до распределения'"
    sql += ' GROUP BY 1, 2, 3'
    result = {}
    for r in query(sql, params):
        key = (
            (r['project'] or '').strip() or '(без проекта)',
            (r['stat3'] or '').strip() or '(без статьи)',
            (r['contragent'] or '').strip() or '(без контрагента)',
        )
        result[key] = result.get(key, 0.0) + float(r['amount'] or 0)
    return result


def deviation_detail(lines, series_a, series_b, projects=None, top_n=20, allocation='all'):
    """Акт-анализ отклонения между двумя срезами (series_a, series_b — каждый
    (pf, year, month)): топ-N (проект, СтатьяУровень3, Контрагент) по |разница|.
    Сортировка — сначала строки того же знака, что и общее отклонение (по
    убыванию модуля), затем строки противоположного знака (тоже по модулю)."""
    a = _raw_group(lines, series_a[1], series_a[2], series_a[0], projects, allocation)
    b = _raw_group(lines, series_b[1], series_b[2], series_b[0], projects, allocation)
    drivers = []
    for key in set(a) | set(b):
        va, vb = a.get(key, 0.0), b.get(key, 0.0)
        delta = va - vb
        if abs(delta) < 0.5:
            continue
        drivers.append({'project': key[0], 'stat3': key[1], 'contragent': key[2],
                         'a': va, 'b': vb, 'delta': delta})
    total_delta = sum(d['delta'] for d in drivers)
    drivers.sort(key=lambda d: (0 if (d['delta'] >= 0) == (total_delta >= 0) else 1, -abs(d['delta'])))
    return {'total_delta': total_delta, 'drivers': drivers[:top_n]}


def get_counterparties():
    rows = query('SELECT name FROM reporting.counterparty_list ORDER BY 1')
    return [r['name'] for r in rows]


def search_counterparties(q, limit=50):
    """Список контрагентов (~10 тыс. записей) слишком большой, чтобы отдавать
    целиком в select — ищем по подстроке для Tom-Select remote search."""
    rows = query(
        'SELECT name FROM reporting.counterparty_list WHERE name ILIKE %s ORDER BY 1 LIMIT %s',
        (f'%{q}%', limit),
    )
    return [r['name'] for r in rows]


def get_latest_period(pf='факт'):
    rows = query('SELECT MAX(period) AS mx FROM reporting.pl_monthly WHERE pf = %s', (pf,))
    return rows[0]['mx'] if rows and rows[0]['mx'] else date.today().replace(day=1)


def default_counterparty_range(pf='факт'):
    """Диапазон по умолчанию — последние 12 месяцев доступных данных для этого pf."""
    latest = get_latest_period(pf)
    y, m = latest.year, latest.month - 11
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1), latest


def counterparty_series(contragents, pf='факт', projects=None, date_from=None, date_to=None, allocation='all'):
    """Динамика по одному или нескольким контрагентам и/или проектам (индекс по
    "Контрагент" уже есть — idx_financial_data_contragent, запрос быстрый),
    опционально отфильтрованная по диапазону дат. Несколько контрагентов/проектов
    суммируются в один ряд (не сравниваются по отдельности). Можно указать только
    contragents, только projects, или оба вместе — хотя бы один обязателен (иначе
    это будет агрегат по всей компании, не для этого отчёта).

    Разбивка по секциям — та же, что в svod1() (Выручка/Переменные/Постоянные/
    Прибыль/Инвестиции в портфели/Финансирование/Чистая прибыль), формула
    ЧИСТОЙ ПРИБЫЛИ идентична svod1: профит + бонусы + инвестиции + финансирование.
    allocation: 'all' (с распределением затрат, по умолчанию) / 'no_alloc' (без)."""
    if isinstance(contragents, str):
        contragents = [contragents]
    if not contragents and not projects:
        raise ValueError('Нужно указать хотя бы контрагента или проект')
    sql = '''SELECT "Период" AS period, "Строка отчета" AS line, SUM("Сумма") AS amount
             FROM public."FinancialData"
             WHERE "п_ф" = %s AND "Строка отчета" = ANY(%s)'''
    params = [pf, ALL_LINES]
    if contragents:
        sql += ' AND "Контрагент" = ANY(%s)'
        params.append(contragents)
    if projects:
        sql += ' AND "Проект" = ANY(%s)'
        params.append(projects)
    if date_from:
        sql += ' AND "Период" >= %s'
        params.append(date_from)
    if date_to:
        sql += ' AND "Период" <= %s'
        params.append(date_to)
    if allocation == 'no_alloc':
        sql += " AND \"Распределение\" = 'до распределения'"
    sql += ' GROUP BY 1, 2 ORDER BY 1'
    rows = query(sql, params)

    revenue_set, variable_set, fixed_set = set(REVENUE_LINES), set(VARIABLE_LINES), set(FIXED_LINES)
    bonus_set, financing_set = set(BONUS_LINES), set(FINANCING_LINES)
    by_period = defaultdict(lambda: {'revenue': 0.0, 'variable': 0.0, 'fixed': 0.0,
                                      'bonus': 0.0, 'investment': 0.0, 'financing': 0.0})
    for r in rows:
        amount = float(r['amount'] or 0)
        line = r['line']
        if line in revenue_set:
            bucket = 'revenue'
        elif line in variable_set:
            bucket = 'variable'
        elif line in fixed_set:
            bucket = 'fixed'
        elif line in bonus_set:
            bucket = 'bonus'
        elif line == INVESTMENT_LINE:
            bucket = 'investment'
        else:
            bucket = 'financing'
        by_period[r['period']][bucket] += amount

    periods = sorted(by_period)
    table = []
    for p in periods:
        d = by_period[p]
        profit = d['revenue'] + d['variable'] + d['fixed']
        net_profit = profit + d['bonus'] + d['investment'] + d['financing']
        table.append({
            'period': p.strftime('%m.%Y'),
            'revenue': d['revenue'], 'variable': d['variable'], 'fixed': d['fixed'],
            'profit': profit, 'investment': d['investment'], 'financing': d['financing'],
            'net_profit': net_profit,
        })

    def _total(key):
        return sum(row[key] for row in table)

    return {
        'periods': [p.strftime('%Y-%m') for p in periods],
        'table': table,
        'revenue': [row['revenue'] for row in table],
        'profit': [row['profit'] for row in table],
        'net_profit': [row['net_profit'] for row in table],
        'total_revenue': _total('revenue'),
        'total_variable': _total('variable'),
        'total_fixed': _total('fixed'),
        'total_profit': _total('profit'),
        'total_investment': _total('investment'),
        'total_financing': _total('financing'),
        'total_net_profit': _total('net_profit'),
    }


def overview_data(year, pf='факт', allocation='all'):
    """Обзорный дашборд: выручка/прибыль/GM%/структура расходов/топ-5 портфелей,
    этот год против прошлого, тыс. руб."""
    prev_year = year - 1
    cur = _fetch_year(year, pf, allocation)
    prev = _fetch_year(prev_year, pf, allocation)

    def sums(by_line, lines):
        return [sum(by_line.get(l, _empty_months())[m] for l in lines) for m in range(1, 13)]

    revenue_cur, revenue_prev = sums(cur, REVENUE_LINES), sums(prev, REVENUE_LINES)
    variable_cur, variable_prev = sums(cur, VARIABLE_LINES), sums(prev, VARIABLE_LINES)
    fixed_cur, fixed_prev = sums(cur, FIXED_LINES), sums(prev, FIXED_LINES)
    gm_cur = [revenue_cur[i] + variable_cur[i] for i in range(12)]
    gm_prev = [revenue_prev[i] + variable_prev[i] for i in range(12)]
    profit_cur = [gm_cur[i] + fixed_cur[i] for i in range(12)]
    profit_prev = [gm_prev[i] + fixed_prev[i] for i in range(12)]

    bonus_cur, bonus_prev = sums(cur, BONUS_LINES), sums(prev, BONUS_LINES)
    fin_cur, fin_prev = sums(cur, FINANCING_LINES), sums(prev, FINANCING_LINES)
    inv_cur = _series(cur.get(INVESTMENT_LINE, _empty_months()))
    inv_prev = _series(prev.get(INVESTMENT_LINE, _empty_months()))
    net_profit_cur = [profit_cur[i] + bonus_cur[i] + fin_cur[i] + inv_cur[i] for i in range(12)]
    net_profit_prev = [profit_prev[i] + bonus_prev[i] + fin_prev[i] + inv_prev[i] for i in range(12)]

    gm_pct_cur = [(gm_cur[i] / revenue_cur[i] * 100) if revenue_cur[i] else 0.0 for i in range(12)]
    gm_pct_prev = [(gm_prev[i] / revenue_prev[i] * 100) if revenue_prev[i] else 0.0 for i in range(12)]

    by_project_cur = _fetch_year_by_project(year, pf, REVENUE_LINES, allocation)
    top_projects = sorted(
        ((p, sum(vals.values())) for p, vals in by_project_cur.items()),
        key=lambda kv: -kv[1]
    )[:5]

    return {
        'year': year, 'prev_year': prev_year, 'months': MONTHS_RU, 'pf': pf,
        'revenue_cur': revenue_cur, 'revenue_prev': revenue_prev,
        'variable_cur': variable_cur, 'variable_prev': variable_prev,
        'gm_cur': gm_cur, 'gm_prev': gm_prev,
        'fixed_cur': fixed_cur, 'fixed_prev': fixed_prev,
        'profit_cur': profit_cur, 'profit_prev': profit_prev,
        'investment_cur': inv_cur, 'investment_prev': inv_prev,
        'financing_cur': fin_cur, 'financing_prev': fin_prev,
        'net_profit_cur': net_profit_cur, 'net_profit_prev': net_profit_prev,
        'gm_pct_cur': gm_pct_cur, 'gm_pct_prev': gm_pct_prev,
        'total_variable': abs(sum(variable_cur)), 'total_fixed': abs(sum(fixed_cur)),
        'top_projects': [{'project': p, 'revenue': v} for p, v in top_projects],
        # Списки строк отчёта для клика-провала (window.showCellDetail) по каждому
        # из графиков левой колонки — те же построчные группы, что в Свод1.
        'revenue_lines': REVENUE_LINES, 'variable_lines': VARIABLE_LINES, 'fixed_lines': FIXED_LINES,
        'gm_lines': REVENUE_LINES + VARIABLE_LINES,
        'profit_lines': REVENUE_LINES + VARIABLE_LINES + FIXED_LINES,
        'investment_lines': [INVESTMENT_LINE], 'financing_lines': FINANCING_LINES,
    }


def export_svod1(data):
    headers = ['Статья'] + data['months']
    return [('Свод1', headers, export.flatten_rows(data['rows'], ('vals',)))]


def export_svod2(data):
    headers = ['Портфель'] + data['months']
    return [('Свод2', headers, export.flatten_rows(data['rows'], ('vals',)))]


def export_unitpl(data):
    headers = ['Статья'] + data['periods'] + [f"Δ ({data['endpoint_a']['label']}-{data['endpoint_b']['label']})"]
    return [('UNIT+PL', headers, export.flatten_rows(data['rows'], ('vals', 'endpoint_delta')))]


def _dashboard_headers(data):
    series_headers = [f'{pf} {y}' for pf, y in data['series']]
    delta_headers = [f'Δ ({data["series"][i][0]}{data["series"][i][1]}-{data["series"][j][0]}{data["series"][j][1]})'
                      for i, j in data['deltas']]
    return ['Статья'] + series_headers + delta_headers


def export_dashboard(data, sheet_prefix):
    headers = _dashboard_headers(data)
    month_rows = export.flatten_rows(data['rows'], ('series_month', 'delta_month'))
    ytd_rows = export.flatten_rows(data['rows'], ('series_ytd', 'delta_ytd'))
    return [(f'{sheet_prefix} Месяц', headers, month_rows), (f'{sheet_prefix} Накопительно', headers, ytd_rows)]


def export_overview(data):
    headers = ['Месяц', f'Выручка {data["year"]}', f'Выручка {data["prev_year"]}',
               f'Прибыль {data["year"]}', f'Прибыль {data["prev_year"]}',
               f'Чистая прибыль {data["year"]}', f'GM% {data["year"]}', f'GM% {data["prev_year"]}']
    rows = [
        [m, data['revenue_cur'][i], data['revenue_prev'][i], data['profit_cur'][i], data['profit_prev'][i],
         data['net_profit_cur'][i], data['gm_pct_cur'][i], data['gm_pct_prev'][i]]
        for i, m in enumerate(data['months'])
    ]
    return [('Обзор', headers, rows)]


def export_counterparty(data):
    headers = ['Месяц', 'Выручка', 'Переменные', 'Постоянные', 'Прибыль', 'Инвестиции в портфели',
               'Финансирование', 'Чистая прибыль / Кэш флоу']
    rows = [
        [r['period'], r['revenue'], r['variable'], r['fixed'], r['profit'], r['investment'],
         r['financing'], r['net_profit']]
        for r in data['table']
    ]
    return [('По контрагенту', headers, rows)]
