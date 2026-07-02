"""Агрегация данных FinancialData (факт) / Budget2026 (план) в отчёты,
повторяющие структуру листов Свод1/2, DashBoard_1-3 и инвестиционного анализа.

Формулы сверены построчно с оригинальными Excel-файлами (см. план в
~/.claude/plans/inherited-twirling-dawn.md): при группировке FinancialData по
"СтатьяСвод" суммы совпадают с Свод1 до копейки.
"""
from db import query

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

# Строки Свода в порядке отображения: (СтатьяСвод, короткая метка)
SVOD_FACT_LINES = [
    ('01. Выручка профильная (+)', 'Выручка профильная'),
    ('02. Прочие доходы (+)', 'Прочие доходы'),
    ('03. Расходы портфельные (-)', 'Расходы портфельные'),
    ('04. Расходы Прочие (-)', 'Расходы прочие'),
]

SVOD_FACT_BELOW = [
    ('05. Финансы (+/-)', 'Финансы'),
    ('06. Инвестиции (+/-)', 'Инвестиции'),
]

SVOD_FACT_INFO = [
    ('07. ВНЕ БЮДЖЕТА (+/-)', 'Вне бюджета'),
    ('08. Учредители (+/-)', 'Учредители'),
    ('09. Перепродажа машин (+/-)', 'Перепродажа машин'),
    ('10. Нет в своде', 'Не входит в свод'),
]


def get_available_years():
    rows = query('SELECT DISTINCT extract(year FROM "Период")::int AS y FROM "FinancialData" ORDER BY 1')
    return [r['y'] for r in rows]


def get_svod(year, source='fact'):
    """Свод P&L по месяцам выбранного года. source: 'fact' или 'plan'."""
    if source == 'plan':
        return _get_svod_plan(year)
    return _get_svod_fact(year)


def _empty_month_map():
    return {m: 0.0 for m in range(1, 13)}


def _get_svod_fact(year):
    rows = query(
        '''SELECT extract(month FROM "Период")::int AS m, "СтатьяСвод" AS line, SUM("Сумма") / 1000.0 AS val
           FROM "FinancialData"
           WHERE extract(year FROM "Период") = %s
           GROUP BY 1, 2''',
        (year,)
    )
    by_line = {}
    for r in rows:
        by_line.setdefault(r['line'], _empty_month_map())[r['m']] = r['val']

    def line_values(key):
        return by_line.get(key, _empty_month_map())

    report = []
    op_profit = _empty_month_map()
    for key, label in SVOD_FACT_LINES:
        vals = line_values(key)
        report.append({'label': label, 'vals': [vals[m] for m in range(1, 13)]})
        for m in range(1, 13):
            op_profit[m] += vals[m]

    report.append({'label': 'Операционная прибыль', 'vals': [op_profit[m] for m in range(1, 13)], 'bold': True})

    company_profit = dict(op_profit)
    for key, label in SVOD_FACT_BELOW:
        vals = line_values(key)
        report.append({'label': label, 'vals': [vals[m] for m in range(1, 13)]})
        for m in range(1, 13):
            company_profit[m] += vals[m]

    report.append({'label': 'Прибыль Компании', 'vals': [company_profit[m] for m in range(1, 13)], 'bold': True})

    for key, label in SVOD_FACT_INFO:
        vals = line_values(key)
        report.append({'label': label, 'vals': [vals[m] for m in range(1, 13)], 'info': True})

    return {'rows': report, 'months': MONTHS_RU}


def _get_svod_plan(year):
    rows = query(
        '''SELECT extract(month FROM "Период")::int AS m,
                  SUM(CASE WHEN "СтатьяУровень1" = 'Поступления по ОД' THEN "Сумма" ELSE 0 END) / 1000.0 AS revenue,
                  SUM(CASE WHEN "СтатьяУровень1" = 'Отток по ОД' THEN "Сумма" ELSE 0 END) / 1000.0 AS expense,
                  SUM(CASE WHEN trim("СтатьяУровень1") = 'Финансы' THEN "Сумма" ELSE 0 END) / 1000.0 AS finance,
                  SUM(CASE WHEN trim("СтатьяУровень1") = 'Результат по  ИД' THEN "Сумма" ELSE 0 END) / 1000.0 AS invest
           FROM "Budget2026"
           WHERE extract(year FROM "Период") = %s
           GROUP BY 1''',
        (year,)
    )
    by_month = {r['m']: r for r in rows}

    def col(field):
        return [float(by_month.get(m, {}).get(field, 0) or 0) for m in range(1, 13)]

    revenue, expense = col('revenue'), col('expense')
    op_profit = [revenue[i] + expense[i] for i in range(12)]
    finance, invest = col('finance'), col('invest')
    company_profit = [op_profit[i] + finance[i] + invest[i] for i in range(12)]

    report = [
        {'label': 'Поступления по ОД (план)', 'vals': revenue},
        {'label': 'Отток по ОД (план)', 'vals': expense},
        {'label': 'Операционная прибыль', 'vals': op_profit, 'bold': True},
        {'label': 'Финансы (план)', 'vals': finance},
        {'label': 'Инвестиции (план)', 'vals': invest},
        {'label': 'Прибыль Компании', 'vals': company_profit, 'bold': True},
    ]
    return {'rows': report, 'months': MONTHS_RU}


def get_svod_for_project(project, year):
    """Тот же waterfall, что get_svod(fact), но по одному проекту/портфелю."""
    rows = query(
        '''SELECT extract(month FROM "Период")::int AS m, "СтатьяСвод" AS line, SUM("Сумма") / 1000.0 AS val
           FROM "FinancialData"
           WHERE extract(year FROM "Период") = %s AND "Проект" = %s
           GROUP BY 1, 2''',
        (year, project)
    )
    by_line = {}
    for r in rows:
        by_line.setdefault(r['line'], _empty_month_map())[r['m']] = r['val']

    def line_values(key):
        return by_line.get(key, _empty_month_map())

    report = []
    op_profit = _empty_month_map()
    all_lines = SVOD_FACT_LINES + SVOD_FACT_BELOW
    for key, label in all_lines:
        vals = line_values(key)
        report.append({'label': label, 'vals': [vals[m] for m in range(1, 13)]})
        for m in range(1, 13):
            op_profit[m] += vals[m]
    report.append({'label': 'Итого по портфелю', 'vals': [op_profit[m] for m in range(1, 13)], 'bold': True})
    return {'rows': report, 'months': MONTHS_RU}


def get_projects(prefix=None):
    sql = 'SELECT DISTINCT "Проект" FROM "FinancialData" WHERE "Проект" IS NOT NULL AND trim("Проект") <> \'\''
    params = ()
    if prefix:
        sql += ' AND "Проект" ILIKE %s'
        params = (f'{prefix}%',)
    sql += ' ORDER BY 1'
    return [r['Проект'] for r in query(sql, params)]


def get_dashboard(line, years):
    """Разбивка одной строки Свода (line, значение СтатьяСвод) по проектам за список years."""
    placeholders = ','.join(['%s'] * len(years))
    rows = query(
        f'''SELECT extract(year FROM "Период")::int AS y, "Проект" AS project, SUM("Сумма") / 1000.0 AS val
            FROM "FinancialData"
            WHERE "СтатьяСвод" = %s AND extract(year FROM "Период") IN ({placeholders})
            GROUP BY 1, 2''',
        (line, *years)
    )
    by_project = {}
    for r in rows:
        by_project.setdefault(r['project'], {})[r['y']] = r['val']

    plan_rows = []
    if 2026 in years:
        plan_rows = query(
            '''SELECT "Проект" AS project, SUM("Сумма") / 1000.0 AS val
               FROM "Budget2026" WHERE "СтатьяУровень1" = %s GROUP BY 1''',
            (_line_to_plan_uroven1(line),)
        )
    plan_by_project = {r['project']: r['val'] for r in plan_rows}

    table = []
    for project, vals in by_project.items():
        row = {'project': project, 'years': [vals.get(y, 0.0) for y in years]}
        row['plan_2026'] = plan_by_project.get(project)
        table.append(row)
    table.sort(key=lambda r: abs(r['years'][-1] if r['years'] else 0), reverse=True)
    return {'years': years, 'rows': table}


def _line_to_plan_uroven1(line):
    mapping = {
        '01. Выручка профильная (+)': 'Поступления по ОД',
        '02. Прочие доходы (+)': 'Поступления по ОД',
        '03. Расходы портфельные (-)': 'Отток по ОД',
        '04. Расходы Прочие (-)': 'Отток по ОД',
        '05. Финансы (+/-)': 'Финансы',
        '06. Инвестиции (+/-)': 'Результат по  ИД',
    }
    return mapping.get(line, line)


def get_investments(years):
    """Инвестиции (06. Инвестиции) по проектам/портфелям за список years."""
    return get_dashboard('06. Инвестиции (+/-)', years)
