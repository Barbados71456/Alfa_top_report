"""HTTP regression checks. No database, scheduler, or external service is used."""
import importlib
from datetime import date
from unittest.mock import Mock, patch
from flask import url_for
from werkzeug.routing import IntegerConverter

import pytest


@pytest.fixture
def web(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from config import Config
    for key in ('DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'SECRET_KEY'):
        monkeypatch.setattr(Config, key, 'isolated-test')
    with patch('threading.Thread.start'), patch('apscheduler.schedulers.background.BackgroundScheduler.start'):
        module = importlib.import_module('app')
    import auth
    import db
    monkeypatch.setattr(db, '_connect', Mock(side_effect=AssertionError('Tests must not connect to a database')))
    monkeypatch.setattr(module.audit, 'log_action', Mock())
    user = {'id': 18, 'username': 'test-admin', 'role': 'admin', 'is_active': True}
    monkeypatch.setattr(auth, 'query_one', Mock(return_value=user))
    monkeypatch.setattr(module.pr, 'get_available_years', lambda: [2025, 2026])
    monkeypatch.setattr(module.fr, 'get_available_years', lambda: [2025, 2026])
    monkeypatch.setattr(module.pr, 'get_projects_with_type', lambda: [])
    module.app.config.update(TESTING=True)
    client = module.app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=18, username='test-admin', role='admin')
    return module, client, user


@pytest.mark.parametrize('path', [
    '/dashboard1?month=13', '/dashboard2?month=-1', '/fot2?month=0',
    '/loans?month=no', '/export/dashboard2?month=13',
    '/api/cell_detail?line=test&year=2026&month=13',
    '/api/deviation_detail?line=test&a=факт:no:1&b=факт:2026:1',
    '/flash?period=bad', '/api/flash_transactions?period=bad',
    '/export/flash_combined?period=bad', '/svod1?pf=wrong',
    '/dashboard2?series=факт:2026&deltas=4-0',
    '/dashboard2?deltas=4-0',
    '/export/dashboard2?deltas=4-0',
    '/counterparty?date_from=2026-09-01&date_to=2026-08-01',
])
def test_invalid_report_parameters_are_400_not_500(web, path):
    _, client, _ = web
    response = client.get(path)
    assert response.status_code == 400


def test_single_comparison_column_does_not_use_three_column_default(web, monkeypatch):
    module, client, _ = web
    dashboard = Mock(return_value={})
    monkeypatch.setattr(module.pr, 'dashboard2', dashboard)
    monkeypatch.setattr(module, 'render_template', lambda *a, **kw: 'ok')
    assert client.get('/dashboard2?series=факт:2026&deltas=').status_code == 200
    assert dashboard.call_args.args[1:3] == ([('факт', 2026)], [])


@pytest.fixture
def month_review_web(web, monkeypatch):
    module, client, _ = web
    monkeypatch.setattr(module.pr, '_fetch_year', lambda *a: {})
    monkeypatch.setattr(module.pr, '_fetch_statya3_detail', lambda *a: {})
    return web


def test_svod1_month_review_renders_with_independent_fact_scenario(month_review_web, monkeypatch):
    module, client, _ = month_review_web
    def comparison_query(sql, params):
        assert "allocation = 'до распределения'" in sql
        return [dict(period=date(2025, 10, 1), pf='факт', line='ФОТ постоянный', value=-12)]
    monkeypatch.setattr(module.pr, 'query', comparison_query)
    result = client.get('/svod1', query_string=dict(year=2025, month=10, pf='план', allocation='no_alloc'))
    assert result.status_code == 200
    html = result.get_data(as_text=True)
    assert 'Итоги месяца для акционеров' in html and 'Октябрь 2025' in html
    assert 'Нет сопоставимых данных прогноза' in html and 'chartRevenue' in html


def test_shareholder_refresh_reads_new_bookings_and_rewrites_conclusions(month_review_web, monkeypatch):
    module, client, user = month_review_web
    user['role'] = 'shareholder'
    actual_revenues = iter([80, 120])

    def bookings(sql, params):
        assert 'public."FinancialData"' in sql and "allocation = 'до распределения'" in sql
        assert params[:4] == (date(2025, 1, 1), date(2025, 10, 1), date(2024, 1, 1), date(2024, 10, 1))
        return [dict(period=date(2025, month, 1), pf=pf, line=line, value=value)
                for pf, revenue in [('факт', next(actual_revenues)), ('прогноз', 100)]
                for month in range(1, 11)
                for line, value in [(module.pr.REVENUE_LINES[0], revenue), ('Аренда', -10)]]
    monkeypatch.setattr(module.pr, 'query', bookings)
    params = dict(year=2025, month=10, allocation='no_alloc', pf='план', refresh_review='1')
    for direction in ['ниже', 'выше']:
        result = client.get('/svod1', query_string=params)
        assert result.status_code == 200 and result.cache_control.no_store
        page = result.get_data(as_text=True)
        assert 'Обновить выводы' in page and 'Пересчитано по данным базы' in page
        assert f'Операционная прибыль {direction} на' in page
        assert 'Январь — октябрь 2025' in page
        assert page.count(f'Чистая прибыль / кэш флоу <strong>{direction} на') == 2


def test_manual_review_db_error_shows_scheduled_data_without_success_stamp(month_review_web, monkeypatch):
    module, client, _ = month_review_web

    def bookings(sql, params):
        if 'public."FinancialData"' in sql:
            raise module.DatabaseError('test')
        assert 'FROM reporting.pl_monthly' in sql
        return []
    monkeypatch.setattr(module.pr, 'query', bookings)
    result = client.get('/svod1?year=2025&month=10&refresh_review=1')
    page = result.get_data(as_text=True)
    assert result.status_code == 200 and 'Попробуйте ещё раз' in page
    assert 'Пересчитано по данным базы' not in page


def test_disabled_user_cannot_keep_using_existing_session(web):
    _, client, user = web
    user['is_active'] = False
    response = client.get('/admin/users')
    assert response.status_code == 302
    assert response.location.endswith('/login')
    with client.session_transaction() as session:
        assert 'user_id' not in session


def test_changed_role_is_used_immediately(web):
    _, client, user = web
    user['role'] = 'shareholder'
    response = client.post('/flash/split/1', json={'splits': []})
    assert response.status_code == 403
    assert response.is_json


def test_expired_api_session_returns_json(web):
    _, client, _ = web
    with client.session_transaction() as session:
        session.clear()
    response = client.get('/api/cell_detail')
    assert response.status_code == 401
    assert response.is_json


@pytest.mark.parametrize('endpoint,params', [
    ('cell_detail', {'year': 2026, 'month': 10}),
    ('deviation_detail', {'a': 'факт:2026:10', 'b': 'прогноз:2026:10'}),
])
def test_dashboard_profit_detail_expands_compact_group(web, monkeypatch, endpoint, params):
    module, client, _ = web
    detail = Mock(return_value={})
    monkeypatch.setattr(module.pr, endpoint, detail)
    path = '/api/' + endpoint
    response = client.get(path, query_string=dict(params, line_group='net_profit', mode='ytd'))
    assert response.status_code == 200
    assert detail.call_args.args[0] == module.pr.ALL_LINES
    assert detail.call_args.kwargs['mode'] == 'ytd'
    assert client.get(path, query_string=dict(params, line_group='unknown')).status_code == 400


def test_healthcheck_does_not_disclose_connection_details(web, monkeypatch):
    module, client, _ = web
    monkeypatch.setattr(module, 'query', Mock(side_effect=RuntimeError('private-host password=secret')))
    response = client.get('/healthz')
    assert response.status_code == 500
    assert b'private-host' not in response.data
    assert b'secret' not in response.data


@pytest.mark.parametrize('path', ['/api/chat', '/flash/split/1'])
@pytest.mark.parametrize('payload', [[1], 'wrong', 2])
def test_json_endpoints_reject_non_object_payload(web, path, payload):
    _, client, _ = web
    assert client.post(path, json=payload).status_code == 400


def test_counterparty_export_supports_project_only_filter(web, monkeypatch):
    module, client, _ = web
    monkeypatch.setattr(module.pr, 'default_counterparty_range', lambda pf: (date(2026, 1, 1), date(2026, 9, 30)))
    report = Mock(return_value={})
    monkeypatch.setattr(module.pr, 'counterparty_series', report)
    monkeypatch.setattr(module.pr, 'export_counterparty', lambda data: [('test', ['a'], [[1]])])
    response = client.get('/export/counterparty?project=test')
    assert response.status_code == 200
    assert report.call_args.args[0] == []
    assert report.call_args.args[2] == ['test']


def test_refresh_failure_is_not_reported_as_success(web, monkeypatch):
    module, client, _ = web
    monkeypatch.setattr(module, 'refresh_all', lambda: {'updated': [], 'failed': ['reporting.pl_monthly']})
    response = client.post('/admin/refresh_views')
    assert response.status_code == 302
    with client.session_transaction() as session:
        messages = session.get('_flashes', [])
    assert any(category == 'danger' for category, _ in messages)
    assert not any(category == 'success' for category, _ in messages)


@pytest.mark.parametrize('path,data', [
    ('/admin/users/create', {'username': 'test', 'password': 'test', 'role': 'invalid'}),
    ('/admin/users/18/update', {'role': 'shareholder'}),
])
def test_invalid_role_or_self_lockout_never_writes(web, monkeypatch, path, data):
    module, client, _ = web
    execute = Mock()
    monkeypatch.setattr(module, 'execute', execute)
    response = client.post(path, data=data)
    assert response.status_code in (302, 400)
    execute.assert_not_called()


def test_every_private_route_requires_login(web):
    module, client, _ = web
    with client.session_transaction() as session:
        session.clear()
    checked = 0
    for rule in module.app.url_map.iter_rules():
        if rule.endpoint in {'index', 'login', 'logout', 'healthz', 'static'}:
            continue
        values = {name: 1 if isinstance(converter, IntegerConverter) else 'test'
                  for name, converter in rule._converters.items()}
        with module.app.test_request_context():
            path = url_for(rule.endpoint, **values)
        for method in rule.methods & {'GET', 'POST'}:
            response = client.open(path, method=method)
            assert response.status_code in (302, 401), (method, path, response.status_code)
            if response.status_code == 302:
                assert response.location.endswith('/login'), path
            checked += 1
    assert checked >= 60


def test_shareholder_cannot_use_any_write_route(web):
    module, client, user = web
    user['role'] = 'shareholder'
    for rule in module.app.url_map.iter_rules():
        if 'POST' not in rule.methods or rule.endpoint in {
            'login', 'my_profile_update', 'my_password_update', 'api_chat', 'refresh_svod1_review',
        }:
            continue
        values = {name: 1 if isinstance(converter, IntegerConverter) else 'test'
                  for name, converter in rule._converters.items()}
        with module.app.test_request_context():
            path = url_for(rule.endpoint, **values)
        response = client.post(path)
        assert response.status_code == 302, path
        assert response.location.endswith('/svod1'), path


def test_api_forwards_ytd_and_allocation_filters(web, monkeypatch):
    module, client, _ = web
    detail = Mock(return_value={'total': 0})
    monkeypatch.setattr(module.pr, 'cell_detail', detail)
    response = client.get('/api/cell_detail?line=test&year=2026&month=9&mode=ytd&allocation=no_alloc')
    assert response.status_code == 200
    assert detail.call_args.args[5] == 'no_alloc'
    assert detail.call_args.kwargs['mode'] == 'ytd'


def test_duplicate_user_creation_is_a_validation_message(web, monkeypatch):
    from psycopg2.errors import UniqueViolation
    module, client, _ = web
    monkeypatch.setattr(module, 'execute', Mock(side_effect=UniqueViolation()))
    response = client.post('/admin/users/create', data={'username': 'exists', 'password': 'test'})
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert any(category == 'danger' for category, _ in session['_flashes'])


def test_all_templates_compile(web):
    module, _, _ = web
    for template in module.app.jinja_env.list_templates():
        module.app.jinja_env.get_template(template)


def test_review_button_posts_once_as_shareholder_and_get_never_calls_polza(month_review_web, monkeypatch, tmp_path):
    module, client, user = month_review_web
    user['role'] = 'shareholder'
    monkeypatch.setattr(module.sr, 'CACHE', tmp_path / 'cache.sqlite')
    query = Mock(return_value=[dict(period=date(2025, 1, 1), pf=pf, line='Аренда', value=value)
                               for pf, value in [('факт', -15), ('прогноз', -30)]])
    monkeypatch.setattr(module.pr, 'query', query)
    start = Mock(return_value='pending')
    monkeypatch.setattr(module.sr, 'start', start)
    args = dict(year=2025, month=1, pf='прогноз', allocation='no_alloc')
    assert client.get('/svod1', query_string=args).status_code == 200
    start.assert_not_called()
    assert client.post('/svod1/refresh-review', data=args).status_code == 400
    with client.session_transaction() as session:
        token = session['review_token']
    result = client.post('/svod1/refresh-review', data=dict(args, token=token))
    assert result.status_code == 303 and 'allocation=no_alloc' in result.location
    start.assert_called_once()
    assert 'public."FinancialData"' in query.call_args.args[0]
    assert client.get(result.location).status_code == 200
    start.assert_called_once()
