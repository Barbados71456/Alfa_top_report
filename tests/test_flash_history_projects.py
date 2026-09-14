from datetime import date

import flash_report


def _transaction(amount, purpose):
    return {
        'operation_date': date(2026, 8, 20),
        'document_number': '15',
        'amount': amount,
        'counterparty_name': 'Поставщик',
        'counterparty_inn': '1234567890',
        'purpose_text': purpose,
        'account_number': '40702810000000000001',
    }


def test_history_period_normalization_changes_only_calendar_fragments():
    july = 'Оплата услуг по договору № 2026-77 за июль 2025 года, без НДС'
    august = 'Оплата услуг по договору № 2026-77 за август 2026 года, без НДС'
    other_contract = 'Оплата услуг по договору № 2027-77 за август 2026 года, без НДС'

    assert flash_report._normalize_history_periods(july) == flash_report._normalize_history_periods(august)
    assert flash_report._normalize_history_periods(august) != flash_report._normalize_history_periods(other_contract)
    assert '2026-77' in flash_report._normalize_history_periods(august)


def test_load_history_uses_latest_unambiguous_prior_period(monkeypatch):
    recurring = 'Оплата сопровождения за июль 2026 года по договору 55/А'
    ambiguous = 'Оплата юридических услуг за июль 2026 года по реестру 17'
    rows = [
        {'Период': date(2026, 5, 1), 'Комментарии': recurring, 'Проект': 'Старый проект'},
        {'Период': date(2026, 7, 1), 'Комментарии': recurring, 'Проект': 'Новый проект'},
        {'Период': date(2026, 7, 1), 'Комментарии': ambiguous, 'Проект': 'Проект А'},
        {'Период': date(2026, 7, 1), 'Комментарии': ambiguous, 'Проект': 'Проект Б'},
    ]

    def fake_query(sql, params=None):
        assert params == (date(2026, 8, 1),)
        assert '"Период" < %s' in sql
        assert '"Сумма" < 0' in sql
        assert '"п_ф" = \'факт\'' in sql
        assert '"Распределение" = \'до распределения\'' in sql
        return rows

    monkeypatch.setattr(flash_report, 'query', fake_query)
    index = flash_report.load_historical_project_index(date(2026, 8, 19))

    recurring_key = flash_report._normalize_history_purpose(recurring)
    ambiguous_key = flash_report._normalize_history_purpose(ambiguous)
    assert index['before_period'] == date(2026, 8, 1)
    assert index['expected_previous_period'] == date(2026, 7, 1)
    assert index['latest_period'] == date(2026, 7, 1)
    assert index['is_fresh'] is True
    assert index['exact'][recurring_key] == 'Новый проект'
    assert ambiguous_key not in index['exact']


def test_load_history_disables_stale_projects(monkeypatch):
    rows = [{
        'Период': date(2026, 6, 1),
        'Комментарии': 'Оплата сопровождения по договору 55/А за июнь 2026 года',
        'Проект': 'Устаревший проект',
    }]
    monkeypatch.setattr(flash_report, 'query', lambda sql, params=None: rows)

    index = flash_report.load_historical_project_index(date(2026, 8, 1))

    assert index['is_fresh'] is False
    assert index['latest_period'] == date(2026, 6, 1)
    assert index['expected_previous_period'] == date(2026, 7, 1)
    assert index['exact'] == {}
    assert index['period'] == {}


def test_history_projects_apply_only_to_negative_operations_and_prefer_exact():
    exact_purpose = 'Аренда офиса по договору 14/22, постоянный ежемесячный платеж'
    august_purpose = 'Оплата связи за август 2026 года по договору 91/Т'
    period_key = flash_report._normalize_history_periods(august_purpose)
    index = {
        'exact': {
            flash_report._normalize_history_purpose(exact_purpose): 'Точный проект',
            flash_report._normalize_history_purpose(august_purpose): 'Точный август',
        },
        'period': {
            period_key: 'Проект прошлого месяца',
        },
    }
    rows = [
        _transaction(-100, exact_purpose),
        _transaction(100, exact_purpose),
        _transaction(-200, august_purpose),
    ]

    assert flash_report._historical_projects_for_transactions(rows, index) == {
        0: 'Точный проект',
        2: 'Точный август',
    }


def test_import_statement_sets_history_project_without_changing_source(monkeypatch):
    purpose = 'Оплата услуг связи за август 2026 года по договору 91/Т'
    rows = [_transaction(-200, purpose)]
    history_index = {
        'exact': {},
        'period': {
            flash_report._normalize_history_periods(purpose): 'Проект из июля',
        },
    }
    inserted = []

    monkeypatch.setattr(flash_report, 'detect_and_parse', lambda *_: ('alfabank', rows))
    monkeypatch.setattr(flash_report, '_load_classification_rules', lambda: ({}, []))
    monkeypatch.setattr(flash_report, '_load_wallet_aliases', lambda: {})
    monkeypatch.setattr(flash_report, 'execute_values', lambda sql, values: inserted.extend(values))

    result = flash_report.import_statement(
        object(), 'statement.xlsx', 'analyst',
        historical_project_index=history_index,
    )

    assert result['history_projects'] == 1
    assert result['crm_projects'] == 0
    assert inserted[0][13] == 'Проект из июля'
    assert inserted[0][16] == 'unmatched'


def test_enrich_history_preserves_manual_split_and_current_fact(monkeypatch):
    purpose = 'Оплата услуг связи за август 2026 года по договору 91/Т'
    transaction = {'id': 41, **_transaction(-200, purpose)}
    index = {
        'exact': {flash_report._normalize_history_purpose(purpose): 'Проект из июля'},
        'period': {},
    }
    updates = []

    def fake_query(sql, params=None):
        assert 'amount < 0' in sql
        assert "classification_source NOT IN ('manual', 'split', 'learned')" in sql
        return [transaction]

    monkeypatch.setattr(flash_report, 'query', fake_query)
    monkeypatch.setattr(flash_report, 'execute_values', lambda sql, values: updates.extend(values))

    assert flash_report.enrich_projects_from_history(
        date(2026, 8, 1), historical_project_index=index
    ) == 1
    assert updates == [('Проект из июля', 41)]
