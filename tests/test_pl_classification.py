from datetime import date

import flash_report
import pl_report


TRANSFER_LINE = 'Внутренние перемещения (нетто)'
ONE_OFF_PURCHASE_LINE = 'Покупка портфелей (разовая)'


def _months(january=0.0):
    return {month: january if month == 1 else 0.0 for month in range(1, 13)}


def test_internal_transfers_have_one_financing_bucket():
    assert TRANSFER_LINE not in pl_report.FIXED_LINES
    assert TRANSFER_LINE in pl_report.FINANCING_LINES
    assert pl_report.ALL_LINES.count(TRANSFER_LINE) == 1
    assert pl_report.line_bucket(TRANSFER_LINE) == 'financing'


def test_one_off_portfolio_purchase_has_one_variable_bucket():
    assert ONE_OFF_PURCHASE_LINE in pl_report.VARIABLE_LINES
    assert ONE_OFF_PURCHASE_LINE != pl_report.INVESTMENT_LINE
    assert ONE_OFF_PURCHASE_LINE not in pl_report.FIXED_LINES
    assert ONE_OFF_PURCHASE_LINE not in pl_report.FINANCING_LINES
    assert pl_report.ALL_LINES.count(ONE_OFF_PURCHASE_LINE) == 1
    assert pl_report.line_bucket(ONE_OFF_PURCHASE_LINE) == 'variable'


def test_svod1_shows_one_off_purchase_in_variable_expenses(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        '_fetch_year',
        lambda year, pf, allocation: {ONE_OFF_PURCHASE_LINE: _months(-250.0)},
    )
    monkeypatch.setattr(
        pl_report,
        '_fetch_statya3_detail',
        lambda year, pf, lines, allocation: {},
    )

    data = pl_report.svod1(2026)
    labels = [row['label'].strip() for row in data['rows']]
    purchase_index = labels.index(ONE_OFF_PURCHASE_LINE)

    assert labels.index('РАСХОДЫ ПЕРЕМЕННЫЕ') < purchase_index
    assert purchase_index < labels.index('Итого переменные')
    assert next(row for row in data['rows'] if row['label'] == 'Итого переменные')['vals'][0] == -250.0
    assert data['variable_series'][0] == -250.0
    assert data['gm_series'][0] == -250.0
    assert data['profit'][0] == -250.0
    assert data['net_profit'][0] == -250.0


def test_svod2_includes_one_off_purchase_in_variable_total(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        '_fetch_year',
        lambda year, pf, allocation: {ONE_OFF_PURCHASE_LINE: _months(-250.0)},
    )
    monkeypatch.setattr(pl_report, '_project_hierarchy', lambda *args, **kwargs: [])
    monkeypatch.setattr(pl_report, '_project_hierarchy_gm', lambda *args, **kwargs: [])

    data = pl_report.svod2(2026)

    assert next(row for row in data['rows'] if row['label'] == 'Итого переменные')['vals'][0] == -250.0
    assert next(row for row in data['rows'] if row['label'] == 'Итого постоянные')['vals'][0] == 0.0
    assert data['profit'][0] == -250.0


def test_dashboards_include_one_off_purchase_in_variable_expenses(monkeypatch):
    calls = []

    def batched_fetch(lines, years, month, pf, dim=None, projects=None, allocation='all'):
        calls.append(tuple(lines))
        if dim == 'line':
            values = {(2026, ONE_OFF_PURCHASE_LINE): -250.0}
        else:
            values = {(2026, ONE_OFF_PURCHASE_LINE, 'Портфель'): -250.0}
        return values, values

    monkeypatch.setattr(pl_report, '_batched_fetch', batched_fetch)

    dashboard2 = pl_report.dashboard2(1, [('факт', 2026)], [])
    dashboard1 = pl_report.dashboard1(1, [('факт', 2026)], [])

    d2_line = next(row for row in dashboard2['rows'] if row['label'] == ONE_OFF_PURCHASE_LINE)
    d2_total = next(row for row in dashboard2['rows'] if row['label'] == 'Итого переменные')
    d1_total = next(row for row in dashboard1['rows'] if row['label'] == 'Итого переменные')
    assert d2_line['series_month'] == [-250.0]
    assert d2_total['series_month'] == [-250.0]
    assert d1_total['series_month'] == [-250.0]
    assert calls and all(ONE_OFF_PURCHASE_LINE in lines for lines in calls)


def test_dashboard2_reconciles_month_ytd_and_deltas_to_svod1(monkeypatch):
    pl = pl_report
    series = [('факт', 2025), ('прогноз', 2026), ('факт', 2026)]
    postings = {
        pl.REVENUE_LINES[0]: (200, 70), pl.OPENING_BALANCE_LINE: (9, 0),
        pl.ONE_OFF_PORTFOLIO_PURCHASE_LINE: (-5, -8), pl.FIXED_LINES[0]: (-20, -70),
        pl.BONUS_LINES[0]: (-4, 0), pl.BONUS_LINES[1]: (-3, -2),
        pl.INVESTMENT_LINE: (-16, -40), pl.INTERNAL_TRANSFER_LINE: (4, -1),
        'Возврат тела займа': (-2, -8), 'Займ приход': (8, 12),
    }

    def by_year(year, pf, allocation):
        scale = 1 + series.index((pf, year))
        amounts = {}
        for line, (january, october) in postings.items():
            amounts[line] = _months(january * scale)
            amounts[line][10] = october * scale
        return amounts

    def batched(lines, years, month, pf, dim, projects, allocation):
        assert (month, dim, projects, allocation) == (10, 'line', ['Портфель'], 'no_alloc')
        monthly, cumulative = {}, {}
        for year in years:
            for line, values in by_year(year, pf, allocation).items():
                if line in lines:
                    monthly[year, line] = values[month]
                    cumulative[year, line] = sum(values[m] for m in range(1, month + 1))
        return monthly, cumulative

    monkeypatch.setattr(pl, '_fetch_year', by_year)
    monkeypatch.setattr(pl, '_fetch_statya3_detail', lambda *args: {})
    monkeypatch.setattr(pl, '_batched_fetch', batched)
    data = pl.dashboard2(10, series, [(2, 0), (2, 1)], ['Портфель'], 'no_alloc')
    summaries = [pl.svod1(year, pf, 'no_alloc')['rows'] for pf, year in series]
    assert [row['label'] for row in data['rows']] == [row['label'] for row in summaries[0]]
    for index, row in enumerate(data['rows']):
        if row['kind'] == 'header':
            continue
        for field, expected in [('month', [s[index]['vals'][9] for s in summaries]),
                                ('ytd', [sum(s[index]['vals'][:10]) for s in summaries])]:
            assert row[f'series_{field}'] == expected
            assert row[f'delta_{field}'] == [expected[2] - expected[0], expected[2] - expected[1]]
    final = data['rows'][-1]
    assert final['detail_group'] == 'net_profit'
    assert final['series_month'] == [-47, -94, -141]
    for name, _, rows in pl.export_dashboard(data, 'Dashboard2'):
        field = 'month' if 'Месяц' in name else 'ytd'
        assert rows[-1] == [final['label'], *final[f'series_{field}'], *final[f'delta_{field}']]


def test_overview_uses_one_off_purchase_as_variable_expense(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        '_fetch_year',
        lambda year, pf, allocation: (
            {ONE_OFF_PURCHASE_LINE: _months(-250.0)} if year == 2026 else {}
        ),
    )
    monkeypatch.setattr(
        pl_report,
        '_fetch_year_by_project',
        lambda year, pf, lines, allocation: {},
    )

    data = pl_report.overview_data(2026)

    assert data['variable_cur'][0] == -250.0
    assert data['gm_cur'][0] == -250.0
    assert data['fixed_cur'][0] == 0.0
    assert data['profit_cur'][0] == -250.0
    assert data['investment_cur'][0] == 0.0
    assert data['net_profit_cur'][0] == -250.0
    assert ONE_OFF_PURCHASE_LINE in data['variable_lines']


def test_counterparty_uses_one_off_purchase_as_variable_expense(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        'query',
        lambda sql, params=None: [{
            'period': date(2026, 1, 1),
            'line': ONE_OFF_PURCHASE_LINE,
            'amount': -250000.0,
        }],
    )

    row = pl_report.counterparty_series(['Контрагент'])['table'][0]

    assert row['variable'] == -250000.0
    assert row['fixed'] == 0.0
    assert row['profit'] == -250000.0
    assert row['investment'] == 0.0
    assert row['financing'] == 0.0
    assert row['net_profit'] == -250000.0


def test_unit_pl_uses_one_off_purchase_as_cost_and_profit(monkeypatch):
    monkeypatch.setattr(pl_report, 'get_available_years', lambda: [2026])

    def fetch_all_years(years, pf, allocation):
        rows = {2026: {}}
        if pf == 'факт':
            rows[2026][ONE_OFF_PURCHASE_LINE] = _months(-250.0)
        return rows

    monkeypatch.setattr(pl_report, '_fetch_all_years', fetch_all_years)

    data = pl_report.unit_pl()

    assert data['cost_series'][0] == -250.0
    assert data['profit'][0] == -250.0
    assert data['net_profit'][0] == -250.0


def test_flash_uses_one_off_purchase_as_variable_expense(monkeypatch):
    monkeypatch.setattr(
        flash_report,
        'query',
        lambda sql, params=None: [{
            'Статья': 'Разовая покупка',
            'Строка отчета': ONE_OFF_PURCHASE_LINE,
            'amount': -250000.0,
            'cnt': 1,
        }],
    )

    data = flash_report.month_breakdown(date(2026, 1, 1))

    assert data['totals']['variable'] == -250000.0
    assert data['totals']['fixed'] == 0.0
    assert data['totals']['investment'] == 0.0
    assert data['gm'] == -250000.0
    assert data['profit'] == -250000.0
    assert data['net_profit'] == -250000.0


def test_svod1_shows_transfers_in_financing_without_changing_cash_flow(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        '_fetch_year',
        lambda year, pf, allocation: {TRANSFER_LINE: _months(-125.0)},
    )
    monkeypatch.setattr(
        pl_report,
        '_fetch_statya3_detail',
        lambda year, pf, lines, allocation: {},
    )

    data = pl_report.svod1(2026)
    labels = [row['label'].strip() for row in data['rows']]
    transfer_index = labels.index(TRANSFER_LINE)

    assert labels.index('ФИНАНСИРОВАНИЕ') < transfer_index
    assert transfer_index < labels.index('Итого финансирование')
    assert next(row for row in data['rows'] if row['label'] == 'Итого постоянные')['vals'][0] == 0.0
    assert next(row for row in data['rows'] if row['label'] == 'Итого финансирование')['vals'][0] == -125.0
    assert data['profit'][0] == 0.0
    assert data['net_profit'][0] == -125.0


def test_counterparty_report_uses_financing_bucket(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        'query',
        lambda sql, params=None: [{
            'period': date(2026, 1, 1),
            'line': TRANSFER_LINE,
            'amount': -125000.0,
        }],
    )

    data = pl_report.counterparty_series(['Контрагент'])
    row = data['table'][0]

    assert row['fixed'] == 0.0
    assert row['profit'] == 0.0
    assert row['financing'] == -125000.0
    assert row['net_profit'] == -125000.0


def test_overview_moves_transfers_from_fixed_to_financing(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        '_fetch_year',
        lambda year, pf, allocation: (
            {TRANSFER_LINE: _months(-125.0)} if year == 2026 else {}
        ),
    )
    monkeypatch.setattr(
        pl_report,
        '_fetch_year_by_project',
        lambda year, pf, lines, allocation: {},
    )

    data = pl_report.overview_data(2026)

    assert data['fixed_cur'][0] == 0.0
    assert data['profit_cur'][0] == 0.0
    assert data['financing_cur'][0] == -125.0
    assert data['net_profit_cur'][0] == -125.0
    assert TRANSFER_LINE in data['financing_lines']
    assert TRANSFER_LINE not in data['fixed_lines']


def test_unit_pl_excludes_transfers_from_costs_but_keeps_cash_flow(monkeypatch):
    monkeypatch.setattr(pl_report, 'get_available_years', lambda: [2026])

    def fetch_all_years(years, pf, allocation):
        rows = {2026: {}}
        if pf == 'факт':
            rows[2026][TRANSFER_LINE] = _months(-125.0)
        return rows

    monkeypatch.setattr(pl_report, '_fetch_all_years', fetch_all_years)

    data = pl_report.unit_pl()

    assert data['cost_series'][0] == 0.0
    assert data['profit'][0] == 0.0
    assert data['net_profit'][0] == -125.0


def test_flash_report_uses_same_financing_bucket(monkeypatch):
    monkeypatch.setattr(
        flash_report,
        'query',
        lambda sql, params=None: [{
            'Статья': 'Перевод',
            'Строка отчета': TRANSFER_LINE,
            'amount': -125000.0,
            'cnt': 1,
        }],
    )

    data = flash_report.month_breakdown(date(2026, 1, 1))

    assert data['totals']['fixed'] == 0.0
    assert data['profit'] == 0.0
    assert data['totals']['financing'] == -125000.0
    assert data['net_profit'] == -125000.0
