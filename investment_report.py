"""Инвестиционный анализ портфелей DP: окупаемость, собираемость, свод по всем портфелям.

Источник — reporting.dp_monthly (period, project, statya_svod, allocation, pf, amount),
материализованное представление поверх public."FinancialData", отфильтрованное по
СтатьяСвод IN ('01. Выручка профильная (+)', '03. Расходы портфельные (-)',
'04. Расходы Прочие (-)'). Колонка allocation ('до распределения' / 'распределение') —
это и есть переключатель "с учётом / без учёта распределения затрат".

Справочник купленных портфелей (дата уступки, к-во, ОСЗ = номинал долга, фактическая
цена) — внешние данные из эталонного Excel (лист "Список"), которых нет в FinancialData;
хранится в reporting.dp_portfolios и редактируется на /investment/admin. Сопоставление
"сырое имя Проект -> канонический портфель" — в reporting.dp_portfolio_aliases, так как
в FinancialData один портфель встречается с вариациями (пробелы/регистр/NBSP).
"""
from collections import defaultdict
from datetime import date

from db import execute, query, query_one

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

REVENUE_STATYA = '01. Выручка профильная (+)'
COST_STATYA = ('03. Расходы портфельные (-)', '04. Расходы Прочие (-)')
INVESTMENT_STATYA = '06. Инвестиции (+/-)'

# Разово вытащено и сверено из листа "Список" эталонного Excel (03_Инвестиционный_анализ.xlsx).
# Дублирующиеся строки (несколько траншей покупки одного портфеля) уже просуммированы
# (проверено на "(DP) Mercedes" и "(DP) ALFA MKK(SMS)" — сходится до рубля с листом
# "Удельные показатели"). (name, purchase_date, units, face_value_rub, price_rub)
SEED_PORTFOLIOS = [
    ('(DP) ALFA RFB', '2019-10-25', 173, 81477756.16, 2284415.07),
    ('(DP) ALFA RB', '2020-04-20', 430, 287183200.37, 11228863.13),
    ('(DP) KASM', '2019-05-16', 466, 175420948.38, 8712614.46),
    ('(DP) ALFA BIB', '2021-12-24', 583, 281187549.05, 5889193.03),
    ('(DP) Rusnar', '2022-09-02', 11, 5697466.90, 1042739.00),
    ('(DP) ALFA BIB 2', '2022-10-21', 646, 350811159.09, 7836697.59),
    ('(DP) Mercedes', '2023-06-02', 31, 45664894.06, 668978.75),
    ('(DP) Aurora BIB', '2023-09-22', 280, 148421459.22, 3043199.36),
    ('(DP) ABR AB', '2023-10-11', 230, 120081805.90, 1809737.26),
    ('(DP) Moneyman', '2022-11-28', 1611, 57308307.52, 8023163.43),
    ('(DP) Drive', '2023-11-22', 173, 265794346.15, 11283283.81),
    ('(DP) BMW', '2024-02-14', 21, 50838660.94, 31011583.17),
    ('(DP) Aurora Mercedes', '2023-12-26', 17, 21876843.57, 328152.65),
    ('(DP) ALFA MKK(SMS)', '2024-01-26', 8160, 235320865.20, 25414653.45),
    ('(DP) ALFA MKK(SMS) 2', '2025-03-14', 776, 44557638.00, 4678551.99),
    ('(DP) Aurora', '2022-06-30', 2151, 74573130.43, -2201500.00),
    ('(DP) Unicredit', '2024-10-10', 890, 508446990.42, 23388561.56),
    ('(DP) Zenith', '2026-02-17', 1, 2106208.99, 800000.00),
    ('(DP) Bokova', '2023-02-02', 1, 1312444.86, 1000000.00),
    ('(DP) Isakov', '2024-02-19', 1, 416784.23, 250070.53),
    ('(DP) Investagro', '2024-02-20', 1, 1229808.84, 600000.00),
    ('(DP) Denisova', '2024-07-29', 1, 710999.55, 10000.00),
    ('(DP) Bogatskii', '2024-09-03', 1205, 101263689.22, 3000000.00),
    ('(DP) ABC', '2025-11-26', 9267, 3239749421.04, 323974.51),
    ('(DP) Aksyonov', '2023-11-03', 1, 2230191.38, 780566.98),
    ('(DP) FORT', '2026-03-03', 1, 1661907.65, 800000.00),
]


def seed_portfolios():
    """Разовое заполнение справочника портфелей из SEED_PORTFOLIOS. Не перезаписывает
    уже существующие (в т.ч. поправленные вручную) строки."""
    for name, pdate, units, face, price in SEED_PORTFOLIOS:
        execute(
            '''INSERT INTO reporting.dp_portfolios (canonical_name, purchase_date, units, face_value_rub, price_rub)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (canonical_name) DO NOTHING''',
            (name, pdate, units, face, price)
        )
    sync_aliases()


def sync_aliases():
    """Автопривязка новых "Проект" из reporting.dp_monthly к каноническим портфелям по
    точному совпадению имени без учёта пробелов/регистра/NBSP. Расхождения (другое
    написание, отсутствие карточки) остаются непривязанными — донастраиваются на
    /investment/admin."""
    execute('''
        INSERT INTO reporting.dp_portfolio_aliases (dp_portfolio_id, project_name)
        SELECT DISTINCT dp.id, m.project
        FROM reporting.dp_monthly m
        JOIN reporting.dp_portfolios dp
          ON lower(trim(replace(m.project, chr(160), ' '))) = lower(trim(dp.canonical_name))
        ON CONFLICT (project_name) DO NOTHING
    ''')


def get_dp_portfolios():
    return query('SELECT * FROM reporting.dp_portfolios ORDER BY purchase_date NULLS LAST, canonical_name')


def get_portfolio_aliases(portfolio_id):
    rows = query('SELECT project_name FROM reporting.dp_portfolio_aliases WHERE dp_portfolio_id = %s ORDER BY project_name', (portfolio_id,))
    return [r['project_name'] for r in rows]


def get_unmatched_dp_projects():
    """"Проект" значения из dp_monthly без привязки к карточке портфеля."""
    rows = query('''
        SELECT DISTINCT m.project
        FROM reporting.dp_monthly m
        WHERE NOT EXISTS (SELECT 1 FROM reporting.dp_portfolio_aliases a WHERE a.project_name = m.project)
        ORDER BY 1
    ''')
    return [r['project'] for r in rows]


def _cost_case(include_allocation):
    statya_list = "('" + "','".join(COST_STATYA) + "')"
    if include_allocation:
        return f"CASE WHEN statya_svod IN {statya_list} THEN amount ELSE 0 END"
    return f"CASE WHEN statya_svod IN {statya_list} AND allocation = 'до распределения' THEN amount ELSE 0 END"


def _portfolio_by_name(canonical_name):
    portfolio = query_one('SELECT * FROM reporting.dp_portfolios WHERE canonical_name = %s', (canonical_name,))
    if not portfolio:
        return None, []
    return portfolio, get_portfolio_aliases(portfolio['id'])


def _monthly_for_projects(project_names, include_allocation):
    """{period: {pf: {'revenue':, 'cost':, 'investment':}}} для списка сырых имён "Проект"."""
    if not project_names:
        return {}
    cost_case = _cost_case(include_allocation)
    rows = query(f'''
        SELECT period, pf,
               SUM(CASE WHEN statya_svod = %s THEN amount ELSE 0 END) AS revenue,
               SUM({cost_case}) AS cost,
               SUM(CASE WHEN statya_svod = %s THEN amount ELSE 0 END) AS investment
        FROM reporting.dp_monthly
        WHERE project = ANY(%s)
        GROUP BY 1, 2
    ''', (REVENUE_STATYA, INVESTMENT_STATYA, project_names))
    by_period = defaultdict(dict)
    for r in rows:
        by_period[r['period']][r['pf']] = {'revenue': float(r['revenue'] or 0), 'cost': float(r['cost'] or 0),
                                            'investment': float(r['investment'] or 0)}
    return by_period


def _all_portfolios_monthly(include_allocation):
    """{dp_portfolio_id: {period: {pf: {'revenue':, 'cost':, 'investment':}}}} — один проход
    по dp_monthly для всех портфелей сразу (без N+1 запросов на свод)."""
    cost_case = _cost_case(include_allocation)
    rows = query(f'''
        SELECT a.dp_portfolio_id AS pid, m.period, m.pf,
               SUM(CASE WHEN m.statya_svod = %s THEN m.amount ELSE 0 END) AS revenue,
               SUM({cost_case}) AS cost,
               SUM(CASE WHEN m.statya_svod = %s THEN m.amount ELSE 0 END) AS investment
        FROM reporting.dp_monthly m
        JOIN reporting.dp_portfolio_aliases a ON a.project_name = m.project
        GROUP BY 1, 2, 3
    ''', (REVENUE_STATYA, INVESTMENT_STATYA))
    by_portfolio = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        by_portfolio[r['pid']][r['period']][r['pf']] = {'revenue': float(r['revenue'] or 0), 'cost': float(r['cost'] or 0),
                                                          'investment': float(r['investment'] or 0)}
    return by_portfolio


def _unmatched_monthly(include_allocation):
    cost_case = _cost_case(include_allocation)
    rows = query(f'''
        SELECT period, pf,
               SUM(CASE WHEN statya_svod = %s THEN amount ELSE 0 END) AS revenue,
               SUM({cost_case}) AS cost,
               SUM(CASE WHEN statya_svod = %s THEN amount ELSE 0 END) AS investment
        FROM reporting.dp_monthly
        WHERE NOT EXISTS (SELECT 1 FROM reporting.dp_portfolio_aliases a WHERE a.project_name = dp_monthly.project)
        GROUP BY 1, 2
    ''', (REVENUE_STATYA, INVESTMENT_STATYA))
    by_period = defaultdict(dict)
    for r in rows:
        by_period[r['period']][r['pf']] = {'revenue': float(r['revenue'] or 0), 'cost': float(r['cost'] or 0),
                                            'investment': float(r['investment'] or 0)}
    return by_period


def _build_rows(monthly, purchase_date, price, face_value=None):
    """monthly: {period: {pf: {'revenue':,'cost':,'investment':}}}. Возвращает
    (rows, cum_revenue_fact, cf_to_date_fact). Инвестиция берётся из фактических данных
    ("06. Инвестиции (+/-)" — так же, как в эталонном Excel), если для портфеля таких
    записей нет вовсе (например, у старых портфелей часть истории уже не хранит эту
    строку) — подставляется единой суммой -price в месяц покупки, справочно из
    reporting.dp_portfolios. Факт приоритетнее плана в том же периоде; окупаемость
    считается по непрерывному ряду факт-потом-план (чтобы прогноз показывал, когда
    портфель окупится по плану)."""
    periods = set(monthly.keys())
    anchor = None
    if purchase_date:
        anchor = date(purchase_date.year, purchase_date.month, 1)
        periods.add(anchor)
    if not periods:
        return [], 0.0, 0.0
    periods = sorted(periods)
    anchor = anchor or periods[0]

    total_db_investment = sum(
        vals.get('investment', 0.0) for by_pf in monthly.values() for vals in by_pf.values()
    )
    use_price_fallback = abs(total_db_investment) < 0.01 and bool(price)

    rows = []
    cum_pv = 0.0
    cum_revenue_fact = 0.0
    cum_revenue_running = 0.0
    cf_to_date_fact = 0.0
    investment_applied = False
    for p in periods:
        by_pf = monthly.get(p, {})
        pf_used = 'факт' if 'факт' in by_pf else ('план' if 'план' in by_pf else None)
        empty = {'revenue': 0.0, 'cost': 0.0, 'investment': 0.0}
        vals = by_pf.get(pf_used, empty) if pf_used else empty
        rev, cost, invest = vals['revenue'], vals['cost'], vals['investment']
        age = (p.year - anchor.year) * 12 + (p.month - anchor.month) + 1
        if use_price_fallback and not investment_applied and p == anchor:
            invest = -price
            investment_applied = True
        cf = rev + cost + invest
        cum_pv += cf
        cum_revenue_running += rev
        if pf_used == 'факт':
            cum_revenue_fact += rev
            cf_to_date_fact += rev + cost
        if pf_used == 'факт' or (use_price_fallback and p == anchor):
            cf_to_date_fact += invest  # инвестиция — известный факт, не прогноз
        rows.append({
            'period': p, 'label': f'{MONTHS_RU[p.month - 1]} {p.year}', 'age': age,
            'pf': pf_used or 'план', 'revenue': rev, 'cost': cost, 'investment': invest,
            'cf': cf, 'pv': cum_pv,
            'remaining_balance': (face_value - cum_revenue_running) if face_value else None,
            'collection_pct': (cum_revenue_running / face_value * 100) if face_value else None,
        })
    return rows, cum_revenue_fact, cf_to_date_fact


def payback_months(rows):
    """Линейная интерполяция первого пересечения накопленного денежного потока (pv) через 0."""
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r['age'])
    if rows[0]['pv'] >= 0:
        return rows[0]['age']
    prev = rows[0]
    for r in rows[1:]:
        if prev['pv'] < 0 <= r['pv']:
            cf = r['pv'] - prev['pv']
            fraction = (-prev['pv'] / cf) if cf else 0.0
            return prev['age'] + fraction
        prev = r
    return None


def portfolio_detail(canonical_name, include_allocation=True):
    portfolio, aliases = _portfolio_by_name(canonical_name)
    if portfolio is None:
        return None
    monthly = _monthly_for_projects(aliases, include_allocation)
    price = float(portfolio['price_rub'] or 0)
    face_value = float(portfolio['face_value_rub'] or 0)
    rows, cum_revenue_fact, cf_to_date_fact = _build_rows(monthly, portfolio['purchase_date'], price, face_value)
    payback = payback_months(rows)
    remaining_balance = (face_value - cum_revenue_fact) if face_value else None
    collection_pct = (cum_revenue_fact / face_value * 100) if face_value else None

    return {
        'portfolio': portfolio, 'aliases': aliases, 'rows': rows,
        'payback_months': payback, 'cf_to_date': cf_to_date_fact,
        'collected_revenue': cum_revenue_fact, 'remaining_balance': remaining_balance,
        'collection_pct': collection_pct, 'include_allocation': include_allocation,
    }


def all_dp_summary():
    """Свод по всем DP-портфелям + строка "Без карточки" для непривязанных "Проект" имён.
    Собираемость/остаток не зависят от распределения затрат — считаются один раз; денежный
    поток и окупаемость — дважды (без и с учётом распределения) для прямого сравнения."""
    portfolios = get_dp_portfolios()
    monthly_no_alloc = _all_portfolios_monthly(include_allocation=False)
    monthly_with_alloc = _all_portfolios_monthly(include_allocation=True)

    rows = []
    for p in portfolios:
        price = float(p['price_rub'] or 0)
        face_value = float(p['face_value_rub'] or 0)
        m_no = monthly_no_alloc.get(p['id'], {})
        m_with = monthly_with_alloc.get(p['id'], {})
        rows_no, cum_rev, cf_no = _build_rows(m_no, p['purchase_date'], price)
        rows_with, _, cf_with = _build_rows(m_with, p['purchase_date'], price)
        rows.append({
            'name': p['canonical_name'], 'has_card': True,
            'purchase_date': p['purchase_date'], 'units': p['units'],
            'face_value_rub': face_value, 'price_rub': price,
            'collected_revenue': cum_rev,
            'remaining_balance': (face_value - cum_rev) if face_value else None,
            'collection_pct': (cum_rev / face_value * 100) if face_value else None,
            'cf_to_date_no_alloc': cf_no, 'cf_to_date_with_alloc': cf_with,
            'payback_no_alloc': payback_months(rows_no), 'payback_with_alloc': payback_months(rows_with),
        })

    unmatched_no = _unmatched_monthly(include_allocation=False)
    unmatched_with = _unmatched_monthly(include_allocation=True)
    if unmatched_no or unmatched_with:
        rows_no, cum_rev, cf_no = _build_rows(unmatched_no, None, 0.0)
        rows_with, _, cf_with = _build_rows(unmatched_with, None, 0.0)
        rows.append({
            'name': 'Без карточки', 'has_card': False,
            'purchase_date': None, 'units': None, 'face_value_rub': None, 'price_rub': None,
            'collected_revenue': cum_rev, 'remaining_balance': None, 'collection_pct': None,
            'cf_to_date_no_alloc': cf_no, 'cf_to_date_with_alloc': cf_with,
            'payback_no_alloc': None, 'payback_with_alloc': None,
        })

    return rows


def update_portfolio(portfolio_id, purchase_date, units, face_value_rub, price_rub, notes):
    execute(
        '''UPDATE reporting.dp_portfolios
           SET purchase_date = %s, units = %s, face_value_rub = %s, price_rub = %s, notes = %s, updated_at = now()
           WHERE id = %s''',
        (purchase_date or None, units or None, face_value_rub or None, price_rub or None, notes or None, portfolio_id)
    )


def create_portfolio(canonical_name, purchase_date, units, face_value_rub, price_rub, notes):
    execute(
        '''INSERT INTO reporting.dp_portfolios (canonical_name, purchase_date, units, face_value_rub, price_rub, notes)
           VALUES (%s, %s, %s, %s, %s, %s)''',
        (canonical_name, purchase_date or None, units or None, face_value_rub or None, price_rub or None, notes or None)
    )


def add_alias(portfolio_id, project_name):
    execute(
        'INSERT INTO reporting.dp_portfolio_aliases (dp_portfolio_id, project_name) VALUES (%s, %s) ON CONFLICT (project_name) DO NOTHING',
        (portfolio_id, project_name)
    )


def remove_alias(project_name):
    execute('DELETE FROM reporting.dp_portfolio_aliases WHERE project_name = %s', (project_name,))


def export_summary(rows):
    headers = ['Портфель', 'Дата покупки', 'Ед.', 'ОСЗ, руб', 'Цена, руб', 'Собрано, руб',
               'Остаток, руб', 'Собираемость %', 'ДП без аллок., руб', 'ДП с аллок., руб',
               'Окупаемость без аллок., мес', 'Окупаемость с аллок., мес']
    out = [
        [r['name'], r['purchase_date'], r['units'], r['face_value_rub'], r['price_rub'],
         r['collected_revenue'], r['remaining_balance'], r['collection_pct'],
         r['cf_to_date_no_alloc'], r['cf_to_date_with_alloc'], r['payback_no_alloc'], r['payback_with_alloc']]
        for r in rows
    ]
    return [('Инвестанализ - свод', headers, out)]


def export_detail(data):
    headers = ['Период', 'Возраст', 'pf', 'Выручка', 'Расходы', 'Инвестиция', 'ДП', 'Накопленный ДП', 'Остаток портфеля']
    rows = [
        [r['label'], r['age'], r['pf'], r['revenue'], r['cost'], r['investment'], r['cf'], r['pv'], r['remaining_balance']]
        for r in data['rows']
    ]
    return [(data['portfolio']['canonical_name'][:31], headers, rows)]
