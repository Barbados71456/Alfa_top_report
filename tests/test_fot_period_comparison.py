from datetime import date

import fot_report


def test_fot_period_comparison_is_fact_only_and_keeps_fot2_hierarchy(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return [
            {
                'dept': 'Field', 'employee': 'Сотрудник А',
                'value_a': -100.0, 'value_b': -150.0,
                'active_months_a': 1, 'active_months_b': 1,
            },
            {
                'dept': 'Legal', 'employee': 'Сотрудник Б',
                'value_a': 0.0, 'value_b': -50.0,
                'active_months_a': 0, 'active_months_b': 1,
            },
        ]

    monkeypatch.setattr(fot_report, 'query', fake_query)
    data = fot_report.period_comparison(
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
    )

    assert "fm.pf = 'факт'" in captured['sql']
    assert data['fact_only'] is True
    total, salary, headcount = data['kpis']
    assert (total['value_a'], total['value_b'], total['delta']) == (-100.0, -200.0, -100.0)
    assert (salary['value_a'], salary['value_b']) == (-100.0, -100.0)
    assert (headcount['value_a'], headcount['value_b'], headcount['delta']) == (1, 2, 1)
    assert [row['label'] for row in data['department_rows']] == ['Legal', 'Field']
    employee_rows = [row for row in data['rows'] if row.get('parent_id')]
    assert {row['label'] for row in employee_rows} == {'Сотрудник А', 'Сотрудник Б'}
    assert all(row['can_detail'] for row in employee_rows)


def test_fot_period_comparison_uses_employee_months_for_range_metrics(monkeypatch):
    monkeypatch.setattr(
        fot_report,
        'query',
        lambda sql, params=None: [{
            'dept': 'Field', 'employee': 'Сотрудник А',
            'value_a': -300.0, 'value_b': -600.0,
            'active_months_a': 3, 'active_months_b': 2,
        }],
    )

    data = fot_report.period_comparison(
        date(2026, 1, 1), date(2026, 3, 1),
        date(2026, 1, 1), date(2026, 2, 1),
    )

    assert data['kpis'][1]['value_a'] == -100.0
    assert data['kpis'][1]['value_b'] == -300.0
    assert data['kpis'][2]['label'] == 'Средняя численность (всего)'
    assert data['kpis'][2]['value_a'] == 1.0
    assert data['kpis'][2]['value_b'] == 1.0


def test_fot_period_comparison_ytd_starts_each_period_in_january(monkeypatch):
    monkeypatch.setattr(fot_report, 'query', lambda sql, params=None: [])

    data = fot_report.period_comparison(
        date(2024, 8, 1), date(2025, 3, 1),
        date(2025, 11, 1), date(2026, 6, 1),
        mode='ytd',
    )

    assert data['period_a']['start'] == date(2025, 1, 1)
    assert data['period_a']['months_count'] == 3
    assert data['period_b']['start'] == date(2026, 1, 1)
    assert data['period_b']['months_count'] == 6
    assert data['period_b']['label'].endswith('· накопительно')


def test_fot_period_detail_filters_effective_department_and_employee(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return [{
            'stat3': fot_report.REPOSSESSION_BONUS_LINE,
            'contragent': 'Сотрудник А',
            'comment': 'Премия',
            'project': 'Проект 1',
            'amount': -1200.0,
            'operation_count': 2,
        }]

    monkeypatch.setattr(fot_report, 'query', fake_query)
    data = fot_report.period_detail(
        date(2026, 1, 1), date(2026, 2, 1),
        department='Field', employee='Сотрудник А',
    )

    assert 'reporting.employees' in captured['sql']
    assert captured['params'][-2:] == ['Field', 'Сотрудник А']
    assert data['total'] == -1200.0
    assert data['row_count'] == 2
    assert data['by_statya3'][0]['stat3'] == fot_report.REPOSSESSION_BONUS_LINE
    assert data['by_statya3'][0]['contragents'][0]['comments'][0]['comment'] == 'Премия · 2 оп.'


def test_fot_period_deviation_is_b_minus_a(monkeypatch):
    calls = []

    def fake_group(start, end, department=None, employee=None):
        calls.append((start, end, department, employee))
        if len(calls) == 1:
            return {('Проект', 'ФОТ постоянный', 'Сотрудник'): -100.0}
        return {('Проект', 'ФОТ постоянный', 'Сотрудник'): -170.0}

    monkeypatch.setattr(fot_report, '_raw_group_period', fake_group)
    data = fot_report.period_deviation_detail(
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
        department='Field',
    )

    assert data['total_delta'] == -70.0
    assert data['drivers'][0]['delta'] == -70.0
    assert calls[0][-2:] == ('Field', None)


def test_fot_period_comparison_export_contains_values_and_parameters(monkeypatch):
    monkeypatch.setattr(fot_report, 'query', lambda sql, params=None: [])
    data = fot_report.period_comparison(
        date(2026, 1, 1), date(2026, 1, 1),
        date(2026, 2, 1), date(2026, 2, 1),
    )

    sheets = fot_report.export_period_comparison(data)

    assert [sheet[0] for sheet in sheets] == ['ФОТ анализ изменений', 'Параметры']
    assert sheets[0][1][4] == 'Δ B−A'
    assert ['Источник', 'Только факт'] in sheets[1][2]
    assert any(row[0] == 'Состав ФОТ' for row in sheets[1][2])
