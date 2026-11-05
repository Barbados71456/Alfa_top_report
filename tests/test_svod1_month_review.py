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
        assert pl.OPENING_BALANCE_LINE not in args[-1]
        return [dict(period=p, pf=pf, line=k, value=v)
                for p, pf, lines in sources for k, v in lines.items()]

    monkeypatch.setattr(pl, 'query', query)
    review = pl.svod1_month_review(2025, 10, 'no_alloc')
    revenue, costs, profit = review['metrics']
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
    revenue, costs, profit = pl.svod1_month_review(2025, 8)['metrics']
    assert revenue['values'] == [12, None, 0]
    assert revenue['deltas'] == [None, {'value': 12, 'pct': None}]
    assert costs['values'] == profit['values'] == [None, None, None]


def test_no_completed_month_has_explicit_empty_state(monkeypatch):
    monkeypatch.setattr(pl, 'query', lambda *args: [{'period': None}])
    assert pl.svod1_month_review(2025)['month'] is None
