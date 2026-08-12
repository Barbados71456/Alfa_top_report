from pathlib import Path

import fot_report


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fot_source_includes_repossession_bonus():
    schema = (REPO_ROOT / 'schema.sql').read_text(encoding='utf-8')

    assert fot_report.REPOSSESSION_BONUS_LINE in fot_report.FOT_LINES
    assert "'Премия за изъятие авто'" in schema


def test_fot3_breaks_out_repossession_bonus_and_includes_it_in_total(monkeypatch):
    def fake_query(sql, params=None):
        if 'FROM reporting.fot_monthly fm' in sql:
            return [
                {'m': 1, 'line': fot_report.FOT_VARIABLE_LINE, 'dept': 'Field', 'val': -100.0},
                {'m': 1, 'line': fot_report.FOT_FIXED_LINE, 'dept': 'Field', 'val': -200.0},
                {'m': 1, 'line': fot_report.REPOSSESSION_BONUS_LINE, 'dept': 'Field', 'val': -50.0},
            ]
        return [{'department': 'Field'}]

    monkeypatch.setattr(fot_report, 'query', fake_query)
    data = fot_report.fot3('Сотрудник', 2026)

    assert data['variable'][0] == -100.0
    assert data['fixed'][0] == -200.0
    assert data['repossession_bonus'][0] == -50.0
    assert data['total'][0] == -350.0
    assert data['year_total'] == -350.0


def test_manual_employee_is_available_in_fot3_selector(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured['sql'] = sql
        return [{'contragent': 'Добавлен вручную'}]

    monkeypatch.setattr(fot_report, 'query', fake_query)

    assert fot_report.get_employees() == ['Добавлен вручную']
    assert 'reporting.employees' in captured['sql']


def test_fot3_export_has_bonus_row():
    data = {
        'employee': 'Сотрудник',
        'dept': 'Field',
        'months': fot_report.MONTHS_RU,
        'variable': [0.0] * 12,
        'fixed': [0.0] * 12,
        'repossession_bonus': [-10.0] + [0.0] * 11,
        'total': [-10.0] + [0.0] * 11,
        'year_total': -10.0,
    }

    sheets = fot_report.export_fot3(data, year=2026, pf='факт')
    report_rows = sheets[0][2]

    assert report_rows[2][0] == fot_report.REPOSSESSION_BONUS_LINE
    assert report_rows[2][1] == -10.0
    assert report_rows[3][0] == 'Итого'
