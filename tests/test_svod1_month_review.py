from datetime import date

import pl_report as pl


def test_review_separates_cost_direction_and_uses_two_distinct_baselines(monkeypatch):
    period = date(2025, 10, 1)
    sales, fees = pl.REVENUE_LINES[:2]
    rent, payroll = 'Аренда', 'ФОТ постоянный'
    sources = [(period, 'факт', {sales: 80, fees: 40, rent: -12, payroll: -30}),
               (period, 'прогноз', {sales: 95, fees: 5, rent: -9, payroll: -31}),
               (date(2024, 10, 1), 'факт', {sales: 150, rent: -50})]

    def query(sql, args):
        assert "allocation = 'до распределения'" in sql
        assert args[-1] == pl.ALL_LINES
        return [dict(period=p, pf=pf, line=k, value=v)
                for p, pf, lines in sources for k, v in lines.items()]

    monkeypatch.setattr(pl, 'query', query)
    review = pl.svod1_month_review(2025, 10, 'no_alloc')['windows'][0]
    revenue, costs, profit, net = review['metrics']
    assert costs['values'] == [42, 40, 50]
    assert profit['values'] == [78, 60, 100]
    assert [d['value'] for d in revenue['deltas']] == [20, -30]
    assert costs['deltas'][0] == {'value': 2, 'pct': 5}
    drivers = review['comparisons'][0]['groups']
    assert drivers[0]['leaders'] == [dict(name=fees, delta=35), dict(name=sales, delta=-15)]
    assert drivers[1]['leaders'] == [dict(name=rent, delta=3), dict(name=payroll, delta=-1)]


def test_absent_forecast_is_not_zero_and_zero_year_ago_has_no_percentage(monkeypatch):
    rows = [dict(period=date(year, 8, 1), pf='факт', line=pl.REVENUE_LINES[0], value=amount)
            for year, amount in [(2025, 12), (2024, 0)]]
    monkeypatch.setattr(pl, 'query', lambda *args: rows)
    revenue, costs, profit, net = pl.svod1_month_review(2025, 8)['windows'][0]['metrics']
    assert revenue['values'] == [12, None, 0]
    assert revenue['deltas'] == [None, {'value': 12, 'pct': None}]
    assert costs['values'] == profit['values'] == [None, None, None]
    assert net['values'] == [12, None, 0]


def test_month_and_ytd_cash_flow_include_all_svod1_lines_and_reconcile_every_driver(monkeypatch):
    # All three scenarios have both months. Each article affects the net exactly
    # once, including signed financing, opening balance, bonuses and investment.
    sales = pl.REVENUE_LINES[0]
    rows = []
    def book(year, month, pf, amounts):
        rows.extend(dict(period=date(year, month, 1), pf=pf, line=line, value=value)
                    for line, value in amounts.items())

    book(2025, 1, 'факт', {sales: 140, pl.OPENING_BALANCE_LINE: 8, pl.BONUS_LINES[0]: -3})
    book(2025, 2, 'факт', {sales: 100, 'Аренда': -40, pl.INVESTMENT_LINE: -60,
                            'Займ приход': 30, 'Дивиденды учредителям': -10})
    book(2025, 1, 'прогноз', {sales: 100, 'Аренда': -10})
    book(2025, 2, 'прогноз', {sales: 120, 'Аренда': -45, 'Возврат тела займа': -2})
    book(2024, 1, 'факт', {sales: 60})
    book(2024, 2, 'факт', {sales: 40, 'Аренда': -30, pl.INVESTMENT_LINE: -30})
    monkeypatch.setattr(pl, 'query', lambda *args: rows)
    month, ytd = pl.svod1_month_review(2025, 2)['windows']
    assert month['metrics'][-1]['values'] == [20, 73, -20]
    assert ytd['metrics'][-1]['values'] == [165, 163, 40]
    assert ytd['metrics'][2]['values'][0] == 200  # opening balance belongs only to the net
    for window in (month, ytd):
        for comparison in window['comparisons']:
            drivers = comparison['drivers']
            all_items = drivers['leaders'] + drivers['others']
            assert len({item['name'] for item in all_items}) == len(all_items)
            assert sum(item['delta'] for item in drivers['leaders']) + drivers['other_total'] == comparison['net_delta']['value']
    assert month['comparisons'][0]['drivers']['leaders'][0] == {'name': pl.INVESTMENT_LINE, 'delta': -60}
    assert ytd['comparisons'][1]['net_delta']['value'] == 125


def test_missing_middle_month_suppresses_only_the_incomplete_ytd_comparison(monkeypatch):
    rows = [dict(period=date(year, m, 1), pf=pf, line=pl.REVENUE_LINES[0], value=value)
            for year, pf, months, value in [(2025, 'факт', [1, 2, 3], 10),
                                            (2025, 'прогноз', [1, 3], 12),
                                            (2024, 'факт', [1, 2, 3], 0)]
            for m in months]
    monkeypatch.setattr(pl, 'query', lambda *args: rows)
    month, ytd = pl.svod1_month_review(2025, 3)['windows']
    assert month['comparisons'][0]['net_delta']['value'] == -2
    assert ytd['metrics'][-1]['values'] == [30, 24, 0]
    assert ytd['gaps'] == [('Прогноз', 'фев')]
    assert ytd['comparisons'][0]['drivers'] is None
    assert ytd['comparisons'][1]['net_delta'] == {'value': 30, 'pct': None}


def test_no_completed_month_has_explicit_empty_state(monkeypatch):
    monkeypatch.setattr(pl, 'query', lambda *args: [{'period': None}])
    assert pl.svod1_month_review(2025)['month'] is None
