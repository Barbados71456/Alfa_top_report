from datetime import date

import flash_report


def _transaction(amount, purpose, inn=None):
    return {
        'operation_date': date(2026, 8, 7),
        'document_number': '1',
        'amount': amount,
        'counterparty_name': 'Плательщик',
        'counterparty_inn': inn,
        'purpose_text': purpose,
        'account_number': '40702810000000000001',
    }


def test_extract_crm_contract_candidates_uses_explicit_markers():
    assert flash_report._extract_crm_contract_candidates(
        'Погашение задолженности по кредитному договору № 2013914-Ф_0438972121, Иванов И.И.'
    ) == ['2013914-Ф_0438972121']
    assert flash_report._extract_crm_contract_candidates(
        'Взыск. задолж. согл. КД № 18-0006-1с-013234 и/л N 77/645'
    ) == ['18-0006-1с-013234']
    assert flash_report._extract_crm_contract_candidates(
        'Оплата по договору № 1 от 07.12.2023'
    ) == []
    assert flash_report._extract_crm_contract_candidates(
        'ИНН 1234567890, исполнительное производство 74074/22/17004-ИП'
    ) == []


def test_crm_projects_are_looked_up_only_for_positive_operations(monkeypatch):
    calls = []

    def fake_query(sql, params=None):
        calls.append((sql, params))
        return [
            {'candidate': '16794110', 'project': '(DP) Moneyman'},
            {'candidate': '2013914-Ф_0438972121', 'project': '(DP) TB'},
        ]

    monkeypatch.setattr(flash_report, 'query', fake_query)
    rows = [
        _transaction(100, 'Задолженность по договору №16794110: Иванов'),
        _transaction(-100, 'Задолженность по договору №16794110: Иванов'),
        _transaction(50, 'По кредитному договору 2013914-Ф_0438972121, Петров'),
    ]

    assert flash_report._crm_projects_for_transactions(rows) == {
        0: '(DP) Moneyman',
        2: '(DP) TB',
    }
    assert len(calls) == 1
    assert calls[0][1][0] == ['16794110', '2013914-Ф_0438972121']
    assert 'count(DISTINCT cases.id) = 1' in calls[0][0]
    assert 'crm_alfa.source_cases AS cases' in calls[0][0]


def test_import_statement_prefers_crm_project_but_keeps_classification_source(monkeypatch):
    rows = [
        _transaction(100, 'Задолженность по договору №16794110: Иванов', inn='123'),
        _transaction(50, 'По кредитному договору 2013914-Ф_0438972121, Петров'),
        _transaction(-75, 'Задолженность по договору №16794110: Иванов', inn='123'),
    ]
    rule = {
        'id': 7,
        'Признак': 'Операционка',
        'Категория': 'Выручка',
        'Статья': 'Поступления от должников',
        'Проект': 'Старый проект правила',
        'Контрагент_report': 'Должники',
        'Строка отчета': 'Выручка общая',
    }
    inserted = []

    monkeypatch.setattr(flash_report, 'detect_and_parse', lambda *_: ('alfabank', rows))
    monkeypatch.setattr(flash_report, '_load_classification_rules', lambda: ({'123': rule}, []))
    monkeypatch.setattr(flash_report, '_load_wallet_aliases', lambda: {})

    def fake_query(sql, params=None):
        assert params[0] == ['16794110', '2013914-Ф_0438972121']
        return [
            {'candidate': '16794110', 'project': '(DP) Moneyman'},
            {'candidate': '2013914-Ф_0438972121', 'project': '(DP) TB'},
        ]

    monkeypatch.setattr(flash_report, 'query', fake_query)
    monkeypatch.setattr(flash_report, 'execute_values', lambda sql, values: inserted.extend(values))
    monkeypatch.setattr(flash_report, 'execute', lambda *args, **kwargs: None)

    result = flash_report.import_statement(object(), 'statement.xlsx', 'analyst')

    assert result == {'bank_format': 'alfabank', 'total': 3, 'matched': 2, 'crm_projects': 2}
    assert inserted[0][13] == '(DP) Moneyman'
    assert inserted[0][16] == 'rule'
    assert inserted[1][13] == '(DP) TB'
    assert inserted[1][16] == 'unmatched'
    assert inserted[2][13] == 'Старый проект правила'
    assert inserted[2][16] == 'rule'


def test_enrich_projects_from_crm_preserves_manual_and_split_rows_in_sql(monkeypatch):
    transaction = {'id': 41, **_transaction(100, 'Задолженность по договору №16794110')}
    updates = []

    def fake_query(sql, params=None):
        if sql.lstrip().startswith('SELECT id, amount'):
            assert "classification_source NOT IN ('manual', 'split')" in sql
            assert 'amount > 0' in sql
            return [transaction]
        return [{'candidate': '16794110', 'project': '(DP) Moneyman'}]

    monkeypatch.setattr(flash_report, 'query', fake_query)
    monkeypatch.setattr(flash_report, 'execute_values', lambda sql, values: updates.extend(values))

    assert flash_report.enrich_projects_from_crm(date(2026, 8, 1)) == 1
    assert updates == [('(DP) Moneyman', 41)]
