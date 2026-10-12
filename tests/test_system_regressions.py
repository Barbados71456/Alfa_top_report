from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

import db
import flash_report as flash
import pl_report as pl
import reporting_refresh as refresh
import fot_report as fot


def test_profit_after_bonus_includes_profit_without_double_counting_cashflow(monkeypatch):
    def months(value):
        return {m: value if m == 6 else 0 for m in range(1, 13)}
    values = {
        pl.REVENUE_LINES[0]: months(1000), pl.VARIABLE_LINES[0]: months(-200),
        pl.FIXED_LINES[0]: months(-100), pl.BONUS_LINES[0]: months(-35),
        pl.INVESTMENT_LINE: months(-300), pl.FINANCING_LINES[0]: months(50),
    }
    monkeypatch.setattr(pl, '_fetch_year', lambda *args: values)
    monkeypatch.setattr(pl, '_fetch_statya3_detail', lambda *args: {})
    result = pl.svod1(2026)
    after = next(r for r in result['rows'] if r['label'] == 'Прибыль после бонусов')
    assert result['profit'][5] == 700
    assert after['vals'][5] == 665
    assert after['vals'][-1] == 665
    assert result['net_profit'][5] == 415


@pytest.mark.parametrize('mode,start', [('month', date(2026, 9, 1)), ('ytd', date(2026, 1, 1))])
def test_detail_preserves_period_and_allocation(monkeypatch, mode, start):
    query = Mock(return_value=[])
    monkeypatch.setattr(pl, 'query', query)
    pl.cell_detail(['test'], 2026, 9, 'факт', ['project'], 'no_alloc', mode=mode)
    sql, params = query.call_args.args
    assert 'BETWEEN %s AND %s' in sql
    assert params == [['test'], start, date(2026, 9, 1), 'факт', ['project']]
    assert "до распределения" in sql


def test_deviation_preserves_ytd_and_total_including_small_changes(monkeypatch):
    group = Mock(side_effect=[{('p', 's', 'c'): 0.4}, {}])
    monkeypatch.setattr(pl, '_raw_group', group)
    result = pl.deviation_detail(['test'], ('факт', 2026, 9), ('факт', 2025, 9),
                                 ['project'], allocation='no_alloc', mode='ytd')
    assert result['total_delta'] == 0.4
    assert all(call.args[-2:] == ('no_alloc', 'ytd') for call in group.call_args_list)


@pytest.fixture
def split_connection(monkeypatch):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (Decimal('100.10'),)
    monkeypatch.setattr(db, '_connect', lambda: conn)
    monkeypatch.setattr(flash, 'cursor_execute_values', Mock())
    return conn, cur


def test_split_commits_all_parts_and_status_once(split_connection):
    conn, cur = split_connection
    flash.set_transaction_splits(1, [{'amount': '60.05'}, {'amount': '40.05'}], 'tester')
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    sql = [call.args[0] for call in cur.execute.call_args_list]
    assert 'FOR UPDATE' in sql[0]
    assert sql[1].startswith('DELETE')
    assert "classification_source='split'" in sql[2]
    assert flash.cursor_execute_values.call_args.args[2][0][1] == Decimal('60.05')


def test_failed_split_insert_rolls_back_existing_parts(split_connection):
    conn, _ = split_connection
    flash.cursor_execute_values.side_effect = RuntimeError('insert failed')
    with pytest.raises(RuntimeError):
        flash.set_transaction_splits(1, [{'amount': '100.10'}], 'tester')
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_split_sum_mismatch_does_not_delete_existing_parts(split_connection):
    conn, cur = split_connection
    with pytest.raises(ValueError, match='не совпадает'):
        flash.set_transaction_splits(1, [{'amount': '100'}], 'tester')
    assert len(cur.execute.call_args_list) == 1
    conn.commit.assert_not_called()


@pytest.mark.parametrize('splits', [[], {}, [None], [{'amount': 'NaN'}],
                                   [{'amount': 'Infinity'}], [{'amount': None}], [{'amount': 'abc'}]])
def test_invalid_split_rejected_before_opening_transaction(monkeypatch, splits):
    connect = Mock(side_effect=AssertionError('Must validate before connecting'))
    monkeypatch.setattr(db, '_connect', connect)
    with pytest.raises(ValueError):
        flash.set_transaction_splits(1, splits, 'tester')
    connect.assert_not_called()


def test_clear_split_is_atomic_and_does_not_reset_manual_classification(split_connection):
    conn, cur = split_connection
    flash.clear_transaction_splits(1)
    conn.commit.assert_called_once()
    assert 'FOR UPDATE' in cur.execute.call_args_list[0].args[0]
    assert "AND classification_source='split'" in cur.execute.call_args_list[-1].args[0]


def test_refresh_reports_failure_but_continues_other_views(monkeypatch):
    def execute(sql):
        if sql.endswith('reporting.pl_monthly'):
            raise RuntimeError('unavailable')
    monkeypatch.setattr(refresh, 'execute_autocommit', execute)
    monkeypatch.setattr(refresh, '_sync_employees', lambda: None)
    monkeypatch.setattr(refresh.ir, 'sync_aliases', lambda: None)
    monkeypatch.setattr(refresh.wr, 'sync_aliases', lambda: None)
    monkeypatch.setattr(refresh.wr, 'seed_foreign_money_balance', lambda: None)
    result = refresh.refresh_all()
    assert result['failed'] == ['reporting.pl_monthly']
    assert len(result['updated']) == 7


def test_fot2_keeps_prior_only_employees_and_ytd_with_empty_current_month(monkeypatch):
    def fetch(years, month, pf):
        return {}, {(2025, 'Field', 'Former'): -100, (2026, 'Field', 'Current'): -200}
    monkeypatch.setattr(fot, '_batched_fetch', fetch)
    data = fot.fot2(10, [('факт', 2025), ('факт', 2026)], [(1, 0)])
    employees = [row for row in data['rows'] if row.get('parent_id')]
    assert {row['label'] for row in employees} == {'Former', 'Current'}
    assert [sum(row['series_ytd'][i] for row in employees) for i in range(2)] == [-100, -200]


def test_empty_fot2_does_not_crash(monkeypatch):
    monkeypatch.setattr(fot, 'query', lambda *args: [])
    assert fot.fot2(10, [], [])['rows'][0]['series_month'] == []


def test_payroll_and_employee_sync_include_bonus_without_restored_mv(monkeypatch):
    query = Mock(return_value=[])
    monkeypatch.setattr(fot, 'query', query)
    fot.fot1(2026)
    sql = query.call_args.args[0]
    assert 'FROM public."FinancialData"' in sql
    assert 'reporting.fot_monthly' not in sql
    assert all(line in sql for line in fot.FOT_LINES)
    assert 'GROUP BY 1, 2, 3, 4, 5' in sql
    execute = Mock()
    monkeypatch.setattr(refresh, 'execute', execute)
    refresh._sync_employees()
    sql = execute.call_args.args[0]
    assert 'Премия за изъятие авто' in sql
    assert 'ON CONFLICT (contragent) DO NOTHING' in sql
    assert 'DELETE' not in sql and 'UPDATE' not in sql
