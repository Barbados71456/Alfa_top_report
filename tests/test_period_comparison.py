from datetime import date

import pl_report


def test_period_comparison_is_fact_only_and_calculates_dashboard_rows(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return [
            {'line': pl_report.REVENUE_LINES[0], 'value_a': 100.0, 'value_b': 150.0},
            {'line': pl_report.VARIABLE_LINES[0], 'value_a': -40.0, 'value_b': -50.0},
            {'line': pl_report.COMPARISON_FIXED_LINES[0], 'value_a': -20.0, 'value_b': -15.0},
        ]

    monkeypatch.setattr(pl_report, 'query', fake_query)
    data = pl_report.period_comparison(
        date(2026, 1, 1), date(2026, 2, 1),
        date(2026, 3, 1), date(2026, 5, 1),
    )

    assert captured['params'][4] == 'факт'
    assert pl_report.OPENING_BALANCE_LINE not in captured['params'][5]
    assert data['fact_only'] is True
    assert data['opening_balance_excluded'] is True
    assert data['period_a']['months_count'] == 2
    assert data['period_b']['months_count'] == 3

    revenue, gross_margin, operating_profit, fixed_costs = data['kpis']
    assert (revenue['value_a'], revenue['value_b'], revenue['delta']) == (100.0, 150.0, 50.0)
    assert revenue['delta_percent'] == 50.0
    assert (gross_margin['value_a'], gross_margin['value_b']) == (60.0, 100.0)
    assert (operating_profit['value_a'], operating_profit['value_b']) == (40.0, 85.0)
    assert fixed_costs['delta'] == 5.0
    assert fixed_costs['delta_percent'] == 25.0
    assert revenue['monthly_average_a'] == 50.0
    assert revenue['monthly_average_b'] == 50.0


def test_period_comparison_ytd_uses_january_of_each_end_year(monkeypatch):
    monkeypatch.setattr(pl_report, 'query', lambda sql, params=None: [])

    data = pl_report.period_comparison(
        date(2024, 10, 1), date(2025, 3, 1),
        date(2025, 11, 1), date(2026, 6, 1),
        mode='ytd',
    )

    assert data['period_a']['start'] == date(2025, 1, 1)
    assert data['period_a']['end'] == date(2025, 3, 1)
    assert data['period_a']['months_count'] == 3
    assert data['period_b']['start'] == date(2026, 1, 1)
    assert data['period_b']['months_count'] == 6
    assert data['period_b']['label'].endswith('· накопительно')


def test_period_comparison_handles_zero_base(monkeypatch):
    monkeypatch.setattr(
        pl_report,
        'query',
        lambda sql, params=None: [{
            'line': pl_report.REVENUE_LINES[0], 'value_a': 0.0, 'value_b': 10.0,
        }],
    )

    data = pl_report.period_comparison(
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
    )

    assert data['kpis'][0]['delta'] == 10.0
    assert data['kpis'][0]['delta_percent'] is None


def test_period_detail_rolls_grouped_operations_into_existing_modal_shape(monkeypatch):
    def fake_query(sql, params=None):
        assert '"п_ф" = \'факт\'' in sql
        return [
            {
                'stat3': 'Зарплата', 'contragent': 'Иванов', 'comment': 'Аванс',
                'project': 'Проект 1', 'amount': -1000.0, 'operation_count': 2,
            },
            {
                'stat3': 'Зарплата', 'contragent': 'Иванов', 'comment': 'Оклад',
                'project': 'Проект 2', 'amount': -2000.0, 'operation_count': 1,
            },
        ]

    monkeypatch.setattr(pl_report, 'query', fake_query)
    data = pl_report.period_detail(
        ['ФОТ постоянный'], date(2026, 1, 1), date(2026, 2, 1)
    )

    assert data['total'] == -3000.0
    assert data['row_count'] == 3
    assert data['by_project'] == [
        {'project': 'Проект 2', 'total': -2000.0},
        {'project': 'Проект 1', 'total': -1000.0},
    ]
    comments = data['by_statya3'][0]['contragents'][0]['comments']
    assert comments[1]['comment'] == 'Аванс · 2 оп.'


def test_period_deviation_is_b_minus_a(monkeypatch):
    calls = []

    def fake_group(lines, start, end, projects=None, allocation='all'):
        calls.append((start, end))
        if len(calls) == 1:
            return {('P', 'Статья', 'Контрагент'): 100.0}
        return {('P', 'Статья', 'Контрагент'): 70.0}

    monkeypatch.setattr(pl_report, '_raw_group_period', fake_group)
    data = pl_report.period_deviation_detail(
        ['Выручка DP (цессия)'],
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
    )

    assert data['total_delta'] == -30.0
    assert data['drivers'][0]['delta'] == -30.0


def test_period_comparison_export_contains_values_and_parameters(monkeypatch):
    monkeypatch.setattr(pl_report, 'query', lambda sql, params=None: [])
    data = pl_report.period_comparison(
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
    )

    sheets = pl_report.export_period_comparison(data)

    assert [sheet[0] for sheet in sheets] == ['Анализ изменений', 'Параметры']
    assert sheets[0][1][3] == 'Δ B−A, тыс. руб.'
    assert ['Источник', 'Только факт'] in sheets[1][2]
