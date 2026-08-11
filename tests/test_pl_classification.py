from datetime import date

import flash_report
import pl_report


TRANSFER_LINE = 'Внутренние перемещения (нетто)'


def _months(january=0.0):
    return {month: january if month == 1 else 0.0 for month in range(1, 13)}


def test_internal_transfers_have_one_financing_bucket():
    assert TRANSFER_LINE not in pl_report.FIXED_LINES
    assert TRANSFER_LINE in pl_report.FINANCING_LINES
    assert pl_report.ALL_LINES.count(TRANSFER_LINE) == 1
    assert pl_report.line_bucket(TRANSFER_LINE) == 'financing'


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
