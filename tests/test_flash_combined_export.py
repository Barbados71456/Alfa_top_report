from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

import export
import flash_report
import monthly_etl as etl


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_combined_export_includes_all_effective_rows_and_blank_projects(monkeypatch):
    operations_sql = []

    def fake_query(sql, params=None):
        if 'SELECT operation_date' in sql:
            operations_sql.append(sql)
            return [
                {
                    'operation_date': date(2026, 8, 3),
                    'Признак': 'Операционка',
                    'Категория': 'Выручка',
                    'Статья': 'Поступления от должников',
                    'Проект': 'Проект А',
                    'counterparty_name': 'Плательщик',
                    'wallet': 'Основной счёт',
                    'amount': 1500,
                    'purpose_text': 'Поступление по договору',
                },
                {
                    'operation_date': date(2026, 8, 4),
                    'Признак': None,
                    'Категория': None,
                    'Статья': None,
                    'Проект': '',
                    'counterparty_name': 'Поставщик',
                    'wallet': 'Основной счёт',
                    'amount': -700,
                    'purpose_text': 'Оплата услуг',
                },
            ]
        if 'wallet_type' in sql:
            return [{'account_number': '40701', 'wallet_type': 'Расчётный счёт'}]
        if 'SELECT account_number, wallet' in sql:
            return [{'account_number': '40701', 'wallet': 'Основной счёт'}]
        raise AssertionError(sql)

    monkeypatch.setattr(flash_report, 'query', fake_query)
    rows = flash_report.export_combined(date(2026, 8, 1))

    assert len(rows) == 2
    assert rows[0]['Проект'] == 'Проект А'
    assert rows[1]['Проект'] is None
    assert rows[1]['Признак'] is None
    assert rows[1]['Сумма'] == -700.0
    assert 'UNION ALL' in operations_sql[0]
    assert "AND classification_source != 'unmatched'" not in operations_sql[0]
    assert 'ORDER BY operation_date, id, split_id NULLS FIRST' in operations_sql[0]

    payload = export.build_workbook([
        ('сводная', etl.FACT_COLUMNS, [[row[column] for column in etl.FACT_COLUMNS] for row in rows])
    ]).getvalue()
    workbook = load_workbook(BytesIO(payload), data_only=True)
    sheet = workbook['сводная']
    assert [cell.value for cell in sheet[1]] == etl.FACT_COLUMNS
    assert sheet['A2'].value.date() == date(2026, 8, 3)
    assert sheet['G3'].value is None
    assert sheet['K3'].value == -700
    assert sheet.auto_filter.ref == 'A1:L3'
    workbook.close()


def test_flash_page_has_combined_export_button():
    template = (REPO_ROOT / 'templates' / 'flash.html').read_text(encoding='utf-8')
    assert "kind='flash_combined'" in template
    assert 'Сведённая выгрузка' in template
