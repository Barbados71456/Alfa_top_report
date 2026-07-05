import logging
import os
import threading
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file

from config import Config
from auth import admin_required, report_required, classifier_required, login_required, authenticate_user, set_password
from auth import hash_password as auth_hash_password
from db import query, query_one, execute, close_connection
from reporting_refresh import refresh_all
import pl_report as pr
import fot_report as fr
import loans_report as lr
import investment_report as ir
import cbr_report as cr
import wallet_report as wr
import audit
import chat_assistant
import export

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_connection)

try:
    Config.validate()
except ValueError:
    app.logger.exception('Некорректная конфигурация окружения')
    raise

# Автообновление reporting.* — без участия пользователя: сразу при старте процесса
# (в фоновом потоке, чтобы не блокировать старт сервера) и затем каждые 10 минут.
threading.Thread(target=refresh_all, daemon=True).start()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(refresh_all, 'interval', minutes=10)
scheduler.start()


def _pick_year(years, requested):
    if requested and requested in years:
        return requested
    return years[-1] if years else date.today().year


def _parse_series(raw):
    """'факт:2025,прогноз:2026,факт:2026' -> [('факт',2025),('прогноз',2026),('факт',2026)]"""
    if not raw:
        return None
    series = []
    for part in raw.split(','):
        pf, _, year = part.partition(':')
        if pf and year.isdigit():
            series.append((pf, int(year)))
    return series or None


def _parse_deltas(raw):
    """'2-0,2-1' -> [(2,0),(2,1)]"""
    if not raw:
        return None
    deltas = []
    for part in raw.split(','):
        i, _, j = part.partition('-')
        if i.isdigit() and j.isdigit():
            deltas.append((int(i), int(j)))
    return deltas or None


def _format_series(series):
    return ','.join(f'{pf}:{year}' for pf, year in series)


def _format_deltas(deltas):
    return ','.join(f'{i}-{j}' for i, j in deltas)


def _series_deltas_from_request(years):
    series = _parse_series(request.args.get('series')) or None
    deltas = _parse_deltas(request.args.get('deltas')) or None
    if series is None or deltas is None:
        default_series, default_deltas = pr.default_series_deltas(years)
        series = series or default_series
        deltas = deltas or default_deltas
    return series, deltas


@app.route('/')
def index():
    return redirect(url_for('svod1') if 'user_id' in session else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        try:
            ok, user = authenticate_user(username, password)
        except Exception:
            app.logger.exception('Ошибка при обращении к БД во время входа')
            flash('Ошибка подключения к базе данных. Сообщите администратору.', 'danger')
            return render_template('login.html')
        if ok:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session.permanent = True
            return redirect(url_for('svod1'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/healthz')
def healthz():
    try:
        query('SELECT 1')
        return {'status': 'ok'}
    except Exception as e:
        app.logger.exception('healthz: БД недоступна')
        return {'status': 'error', 'detail': str(e)}, 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/overview')
@report_required
def overview():
    years = pr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    allocation = request.args.get('allocation', 'all')
    data = pr.overview_data(year, pf, allocation)
    fot_data = fr.fot1(year, pf)
    fot_total = next((r for r in fot_data['rows'] if r['label'] == 'ФОТ (всего)'), None)
    headcount = next((r for r in fot_data['rows'] if r['label'] == 'Численность (всего)'), None)
    loans_series = lr.loans_balance_series(pf)
    return render_template(
        'overview.html', data=data, years=years, year=year, pf=pf, allocation=allocation,
        fot_total=fot_total, headcount=headcount, loans_series=loans_series,
    )


@app.route('/svod1')
@report_required
def svod1():
    years = pr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    allocation = request.args.get('allocation', 'all')
    data = pr.svod1(year, pf, allocation)
    return render_template('svod1.html', data=data, years=years, year=year, pf=pf, allocation=allocation)


@app.route('/api/cell_detail')
@report_required
def api_cell_detail():
    lines = request.args.getlist('line')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    pf = request.args.get('pf', 'факт')
    projects = request.args.getlist('project') or None
    allocation = request.args.get('allocation', 'all')
    if not (lines and year and month):
        return {'error': 'line, year, month обязательны'}, 400
    try:
        data = pr.cell_detail(lines, year, month, pf, projects, allocation)
    except Exception:
        app.logger.exception('cell_detail error')
        return {'error': 'Ошибка при получении детализации'}, 500
    return data


@app.route('/svod2')
@report_required
def svod2():
    years = pr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    allocation = request.args.get('allocation', 'all')
    data = pr.svod2(year, pf, allocation)
    return render_template('svod2.html', data=data, years=years, year=year, pf=pf, allocation=allocation)


@app.route('/unitpl')
@report_required
def unitpl():
    start = request.args.get('start', type=int)
    end = request.args.get('end', type=int)
    allocation = request.args.get('allocation', 'all')
    data = pr.unit_pl(start=start, end=end, allocation=allocation)
    return render_template('unitpl.html', data=data, allocation=allocation)


@app.route('/api/deviation_detail')
@report_required
def api_deviation_detail():
    lines = request.args.getlist('line')
    projects = request.args.getlist('project') or None
    allocation = request.args.get('allocation', 'all')
    a = request.args.get('a', '')
    b = request.args.get('b', '')
    try:
        a_pf, a_year, a_month = a.split(':')
        b_pf, b_year, b_month = b.split(':')
    except ValueError:
        return {'error': 'Некорректные параметры a/b (ожидается pf:год:месяц)'}, 400
    if not lines:
        return {'error': 'line обязателен'}, 400
    try:
        data = pr.deviation_detail(
            lines, (a_pf, int(a_year), int(a_month)), (b_pf, int(b_year), int(b_month)), projects, allocation=allocation
        )
    except Exception:
        app.logger.exception('deviation_detail error')
        return {'error': 'Ошибка при получении акт-анализа'}, 500
    return data


@app.route('/dashboard1')
@report_required
def dashboard1():
    years = pr.get_available_years()
    month = request.args.get('month', type=int) or date.today().month
    series, deltas = _series_deltas_from_request(years)
    projects = request.args.getlist('project') or None
    allocation = request.args.get('allocation', 'all')
    data = pr.dashboard1(month, series, deltas, projects, allocation=allocation)
    return render_template(
        'dashboard1.html', data=data, years=years, month=month, projects=projects, allocation=allocation,
        all_projects=pr.get_projects_with_type(),
        series_str=_format_series(series), deltas_str=_format_deltas(deltas),
    )


@app.route('/dashboard2')
@report_required
def dashboard2():
    years = pr.get_available_years()
    month = request.args.get('month', type=int) or date.today().month
    series, deltas = _series_deltas_from_request(years)
    projects = request.args.getlist('project') or None
    allocation = request.args.get('allocation', 'all')
    data = pr.dashboard2(month, series, deltas, projects, allocation=allocation)
    return render_template(
        'dashboard2.html', data=data, years=years, month=month, projects=projects, allocation=allocation,
        all_projects=pr.get_projects_with_type(),
        series_str=_format_series(series), deltas_str=_format_deltas(deltas),
    )


@app.route('/fot1')
@report_required
def fot1():
    years = fr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    data = fr.fot1(year, pf)
    return render_template('fot1.html', data=data, years=years, year=year, pf=pf)


@app.route('/fot2')
@report_required
def fot2():
    years = fr.get_available_years()
    month = request.args.get('month', type=int) or date.today().month
    series = _parse_series(request.args.get('series'))
    deltas = _parse_deltas(request.args.get('deltas'))
    if series is None or deltas is None:
        default_series, default_deltas = fr.default_series_deltas(years)
        series = series or default_series
        deltas = deltas or default_deltas
    data = fr.fot2(month, series, deltas)
    return render_template(
        'fot2.html', data=data, years=years, month=month,
        series_str=_format_series(series), deltas_str=_format_deltas(deltas),
    )


@app.route('/loans')
@report_required
def loans():
    periods = lr.get_available_periods()
    years = sorted({p.year for p in periods}) if periods else [date.today().year]
    year = request.args.get('year', type=int) or years[-1]
    month = request.args.get('month', type=int) or date.today().month
    pf = request.args.get('pf', 'факт')
    data = lr.loans(year, month, pf)
    series = lr.loans_balance_series(pf)
    return render_template('loans.html', data=data, series=series, years=years, year=year, month=month, pf=pf)


@app.route('/counterparty')
@report_required
def counterparty():
    contragents = request.args.getlist('name')
    pf = request.args.get('pf', 'факт')
    projects = request.args.getlist('project') or None
    default_from, default_to = pr.default_counterparty_range(pf)
    date_from = request.args.get('date_from') or default_from.isoformat()
    date_to = request.args.get('date_to') or default_to.isoformat()
    data = pr.counterparty_series(contragents, pf, projects, date_from, date_to) if contragents else None
    return render_template(
        'counterparty.html', data=data, contragents=contragents, pf=pf, projects=projects,
        date_from=date_from, date_to=date_to,
        counterparties=pr.get_counterparties(),
        all_projects=pr.get_projects_with_type(),
    )


@app.route('/cbr')
@report_required
def cbr():
    dept = request.args.getlist('dept') or None
    emp_region = request.args.getlist('emp_region') or None
    employee = request.args.getlist('employee') or None
    network_param = request.args.get('network', 'network')
    is_network = {'network': True, 'non_network': False}.get(network_param)  # None => 'all'

    table_data = cr.overall_by_month()
    creditor_pivot_all = cr.creditor_pivot()
    chart_filtered = cr.filtered_monthly(dept, emp_region, employee, is_network)
    creditor_pivot_partners = cr.creditor_pivot(is_network=is_network)
    region_dept_pivot = cr.region_department_pivot(is_network=is_network)
    filter_options = cr.get_filter_options()

    legacy_dim = request.args.get('dim', 'department')
    if legacy_dim not in ('department', 'employee', 'region', 'creditor', 'debt_type'):
        legacy_dim = 'department'
    legacy_by_dim = cr.by_dim(legacy_dim)
    months_raw = table_data['months_raw']
    latest_month = months_raw[-1] if months_raw else None
    legacy_perf = cr.top_bottom_performers(latest_month, legacy_dim) if latest_month else {'top': [], 'bottom': []}
    legacy_recommendations = cr.analysis_and_recommendations(legacy_dim)

    return render_template(
        'cbr.html',
        table_data=table_data, creditor_pivot_all=creditor_pivot_all,
        chart_filtered=chart_filtered, creditor_pivot_partners=creditor_pivot_partners,
        region_dept_pivot=region_dept_pivot, filter_options=filter_options,
        dept=dept or [], emp_region=emp_region or [], employee=employee or [], network_param=network_param,
        legacy_dim=legacy_dim, legacy_by_dim=legacy_by_dim, legacy_perf=legacy_perf,
        legacy_recommendations=legacy_recommendations, dim_labels=cr.DIM_LABELS,
    )


@app.route('/cbr/admin')
@classifier_required
def cbr_admin():
    rows = cr.get_employee_mapping()
    return render_template('cbr_admin.html', rows=rows)


@app.route('/cbr/admin/<path:employee>', methods=['POST'])
@classifier_required
def cbr_admin_update(employee):
    cr.update_employee_mapping(
        employee,
        request.form.get('department', '').strip(),
        request.form.get('region', '').strip(),
        request.form.get('is_fired') == 'on',
        request.form.get('employment_type', '').strip(),
    )
    audit.log_action(session.get('username'), 'edit_cbr_employee', employee)
    flash(f'Данные «{employee}» обновлены', 'success')
    return redirect(url_for('cbr_admin'))


@app.route('/investment')
@report_required
def investment():
    rows = ir.all_dp_summary()
    return render_template('investment_summary.html', rows=rows)


@app.route('/investment/<path:name>')
@report_required
def investment_detail(name):
    include_allocation = request.args.get('allocation', '1') != '0'
    data = ir.portfolio_detail(name, include_allocation)
    if data is None:
        flash(f'Портфель «{name}» не найден', 'danger')
        return redirect(url_for('investment'))
    return render_template('investment_detail.html', data=data, name=name, include_allocation=include_allocation)


@app.route('/investment/admin')
@classifier_required
def investment_admin():
    portfolios = ir.get_dp_portfolios()
    for p in portfolios:
        p['aliases'] = ir.get_portfolio_aliases(p['id'])
    unmatched = ir.get_unmatched_dp_projects()
    return render_template('investment_admin.html', portfolios=portfolios, unmatched=unmatched)


@app.route('/investment/admin/<int:portfolio_id>', methods=['POST'])
@classifier_required
def investment_admin_update(portfolio_id):
    ir.update_portfolio(
        portfolio_id,
        request.form.get('purchase_date') or None,
        request.form.get('units') or None,
        request.form.get('face_value_rub') or None,
        request.form.get('price_rub') or None,
        request.form.get('notes', '').strip(),
    )
    audit.log_action(session.get('username'), 'edit_investment_portfolio', f'portfolio_id={portfolio_id}')
    flash('Карточка портфеля обновлена', 'success')
    return redirect(url_for('investment_admin'))


@app.route('/investment/admin/new', methods=['POST'])
@classifier_required
def investment_admin_new():
    name = request.form.get('canonical_name', '').strip()
    if name:
        ir.create_portfolio(
            name,
            request.form.get('purchase_date') or None,
            request.form.get('units') or None,
            request.form.get('face_value_rub') or None,
            request.form.get('price_rub') or None,
            request.form.get('notes', '').strip(),
        )
        alias_for = request.form.get('alias_for_project', '').strip()
        if alias_for:
            portfolio = query('SELECT id FROM reporting.dp_portfolios WHERE canonical_name = %s', (name,))
            if portfolio:
                ir.add_alias(portfolio[0]['id'], alias_for)
        audit.log_action(session.get('username'), 'create_investment_portfolio', name)
        flash(f'Портфель «{name}» создан', 'success')
    return redirect(url_for('investment_admin'))


@app.route('/investment/admin/alias', methods=['POST'])
@classifier_required
def investment_admin_add_alias():
    portfolio_id = request.form.get('portfolio_id', type=int)
    project_name = request.form.get('project_name', '').strip()
    if portfolio_id and project_name:
        ir.add_alias(portfolio_id, project_name)
        audit.log_action(session.get('username'), 'add_investment_alias', f'{project_name} -> portfolio_id={portfolio_id}')
        flash(f'«{project_name}» привязан к портфелю', 'success')
    return redirect(url_for('investment_admin'))


@app.route('/investment/admin/alias/remove', methods=['POST'])
@classifier_required
def investment_admin_remove_alias():
    project_name = request.form.get('project_name', '').strip()
    if project_name:
        ir.remove_alias(project_name)
        audit.log_action(session.get('username'), 'remove_investment_alias', project_name)
        flash(f'«{project_name}» отвязан', 'success')
    return redirect(url_for('investment_admin'))


@app.route('/wallets')
@report_required
def wallets():
    rows = wr.all_wallets_summary()
    return render_template('wallets_summary.html', rows=rows)


@app.route('/wallets/<path:name>')
@report_required
def wallets_detail(name):
    year = request.args.get('year', type=int)
    data = wr.wallet_detail(name, year)
    if data is None:
        flash(f'Кошелёк «{name}» не найден', 'danger')
        return redirect(url_for('wallets'))
    return render_template('wallets_detail.html', data=data, name=name)


@app.route('/wallets/<path:name>/balance', methods=['POST'])
@classifier_required
def wallets_add_balance(name):
    wallet = query('SELECT id FROM reporting.wallets WHERE canonical_name = %s', (name,))
    if not wallet:
        flash(f'Кошелёк «{name}» не найден', 'danger')
        return redirect(url_for('wallets'))
    period_month = request.form.get('period_month')
    period = f'{period_month}-01' if period_month else None
    balance = request.form.get('balance')
    year = request.form.get('year', type=int)
    if period and balance:
        wr.add_balance_entry(wallet[0]['id'], period, balance, request.form.get('notes', '').strip(), session.get('username'))
        audit.log_action(session.get('username'), 'add_wallet_balance', f'{name} @ {period} = {balance}')
        flash('Точка сверки сохранена', 'success')
    return redirect(url_for('wallets_detail', name=name, year=year))


@app.route('/wallets/<path:name>/ledger')
@report_required
def wallets_ledger(name):
    detail = wr.wallet_detail(name, year='all')
    if detail is None:
        flash(f'Кошелёк «{name}» не найден', 'danger')
        return redirect(url_for('wallets'))
    year = request.args.get('year', type=int) or (detail['all_years'][-1] if detail['all_years'] else None)
    date_from = date(year, 1, 1) if year else None
    date_to = date(year, 12, 31) if year else None
    data = wr.wallet_ledger(name, date_from, date_to)
    return render_template('wallets_ledger.html', data=data, name=name, year=year, year_options=detail['all_years'])


@app.route('/wallets/admin')
@classifier_required
def wallets_admin():
    wallets_list = wr.get_wallets()
    for w in wallets_list:
        w['aliases'] = wr.get_wallet_aliases(w['id'])
    unmatched = wr.get_unmatched_wallets()
    return render_template('wallets_admin.html', wallets=wallets_list, unmatched=unmatched, group_order=wr.GROUP_ORDER)


@app.route('/wallets/admin/<int:wallet_id>', methods=['POST'])
@classifier_required
def wallets_admin_update(wallet_id):
    wr.update_wallet(wallet_id, request.form.get('group_name', '').strip(), request.form.get('notes', '').strip())
    audit.log_action(session.get('username'), 'edit_wallet', f'wallet_id={wallet_id}')
    flash('Карточка кошелька обновлена', 'success')
    return redirect(url_for('wallets_admin'))


@app.route('/wallets/admin/new', methods=['POST'])
@classifier_required
def wallets_admin_new():
    name = request.form.get('canonical_name', '').strip()
    if name:
        wr.create_wallet(name, request.form.get('group_name', '').strip(), request.form.get('notes', '').strip())
        alias_for = request.form.get('alias_for_raw', '').strip()
        if alias_for:
            wallet = query('SELECT id FROM reporting.wallets WHERE canonical_name = %s', (name,))
            if wallet:
                wr.add_alias(wallet[0]['id'], alias_for)
        audit.log_action(session.get('username'), 'create_wallet', name)
        flash(f'Кошелёк «{name}» создан', 'success')
    return redirect(url_for('wallets_admin'))


@app.route('/wallets/admin/alias', methods=['POST'])
@classifier_required
def wallets_admin_add_alias():
    wallet_id = request.form.get('wallet_id', type=int)
    raw_name = request.form.get('raw_name', '').strip()
    if wallet_id and raw_name:
        wr.add_alias(wallet_id, raw_name)
        audit.log_action(session.get('username'), 'add_wallet_alias', f'{raw_name} -> wallet_id={wallet_id}')
        flash(f'«{raw_name}» привязан к кошельку', 'success')
    return redirect(url_for('wallets_admin'))


@app.route('/wallets/admin/alias/remove', methods=['POST'])
@classifier_required
def wallets_admin_remove_alias():
    raw_name = request.form.get('raw_name', '').strip()
    if raw_name:
        wr.remove_alias(raw_name)
        audit.log_action(session.get('username'), 'remove_wallet_alias', raw_name)
        flash(f'«{raw_name}» отвязан', 'success')
    return redirect(url_for('wallets_admin'))


@app.route('/employees')
@classifier_required
def employees():
    search = request.args.get('q', '').strip()
    sql = 'SELECT contragent, department, position, status FROM reporting.employees'
    params = ()
    if search:
        sql += ' WHERE contragent ILIKE %s'
        params = (f'%{search}%',)
    sql += ' ORDER BY department NULLS LAST, contragent'
    rows = query(sql, params)
    return render_template('employees.html', rows=rows, search=search, dept_order=fr.DEPT_ORDER)


@app.route('/employees/<contragent>', methods=['POST'])
@classifier_required
def employees_update(contragent):
    department = request.form.get('department', '').strip()
    if department == '__custom__':
        department = request.form.get('department_custom', '').strip()
    execute(
        '''UPDATE reporting.employees SET department = %s, position = %s, status = %s, updated_at = now()
           WHERE contragent = %s''',
        (department or None, request.form.get('position', '').strip() or None,
         request.form.get('status', 'Работает'), contragent)
    )
    audit.log_action(session.get('username'), 'edit_employee', contragent)
    flash(f'Данные сотрудника «{contragent}» обновлены', 'success')
    return redirect(url_for('employees', q=request.form.get('q', '')))


@app.route('/classifier')
@classifier_required
def classifier():
    search = request.args.get('q', '').strip()
    sql = 'SELECT * FROM dim_level_report'
    params = ()
    if search:
        sql += ' WHERE "Статья" ILIKE %s OR "Категория" ILIKE %s'
        params = (f'%{search}%', f'%{search}%')
    sql += ' ORDER BY id'
    rows = query(sql, params)
    return render_template('classifier.html', rows=rows, search=search)


@app.route('/classifier/<int:row_id>', methods=['POST'])
@classifier_required
def classifier_update(row_id):
    execute(
        '''UPDATE dim_level_report
           SET "СтатьяУровень0" = %s, "СтатьяУровень1" = %s, "СтатьяУровень2" = %s, "СтатьяУровень3" = %s
           WHERE id = %s''',
        (
            request.form.get('u0', '').strip(),
            request.form.get('u1', '').strip(),
            request.form.get('u2', '').strip(),
            request.form.get('u3', '').strip(),
            row_id,
        )
    )
    audit.log_action(session.get('username'), 'edit_classifier', f'row_id={row_id}')
    flash('Строка обновлена', 'success')
    return redirect(url_for('classifier', q=request.form.get('q', '')))


@app.route('/admin/log')
@admin_required
def admin_log():
    search = request.args.get('q', '').strip()
    rows = audit.get_log(search)
    return render_template('admin_log.html', rows=rows, search=search)


@app.route('/admin/users')
@admin_required
def admin_users():
    rows = query('SELECT id, username, email, role, is_active, created_at FROM users ORDER BY username')
    return render_template('admin_users.html', rows=rows)


@app.route('/admin/users/create', methods=['POST'])
@admin_required
def admin_users_create():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'shareholder')
    email = request.form.get('email', '').strip() or None
    if username and password:
        execute(
            'INSERT INTO users (username, password_hash, email, role, is_active) VALUES (%s, %s, %s, %s, true)',
            (username, auth_hash_password(password), email, role)
        )
        audit.log_action(session.get('username'), 'create_user', f'{username} ({role})')
        flash(f'Пользователь «{username}» создан', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/update', methods=['POST'])
@admin_required
def admin_users_update(user_id):
    role = request.form.get('role')
    is_active = request.form.get('is_active') == 'on'
    execute('UPDATE users SET role = %s, is_active = %s WHERE id = %s', (role, is_active, user_id))
    audit.log_action(session.get('username'), 'update_user', f'user_id={user_id} role={role} is_active={is_active}')
    flash('Пользователь обновлён', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/password', methods=['POST'])
@admin_required
def admin_users_password(user_id):
    new_password = request.form.get('password', '')
    user = query('SELECT username FROM users WHERE id = %s', (user_id,))
    if user and new_password:
        set_password(user[0]['username'], new_password)
        audit.log_action(session.get('username'), 'reset_password', f'user_id={user_id}')
        flash(f'Пароль для «{user[0]["username"]}» обновлён', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_users_delete(user_id):
    if user_id == session.get('user_id'):
        flash('Нельзя удалить свою же учётную запись', 'danger')
        return redirect(url_for('admin_users'))
    user = query('SELECT username FROM users WHERE id = %s', (user_id,))
    if user:
        execute('DELETE FROM users WHERE id = %s', (user_id,))
        audit.log_action(session.get('username'), 'delete_user', f'user_id={user_id} username={user[0]["username"]}')
        flash(f'Пользователь «{user[0]["username"]}» удалён', 'success')
    return redirect(url_for('admin_users'))


@app.route('/my/profile')
@login_required
def my_profile():
    user = query_one('SELECT id, username, email, full_name, role, created_at FROM users WHERE id = %s', (session['user_id'],))
    return render_template('my_profile.html', user=user)


@app.route('/my/profile', methods=['POST'])
@login_required
def my_profile_update():
    email = request.form.get('email', '').strip() or None
    full_name = request.form.get('full_name', '').strip() or None
    execute('UPDATE users SET email = %s, full_name = %s WHERE id = %s', (email, full_name, session['user_id']))
    audit.log_action(session.get('username'), 'update_own_profile', f'email={email} full_name={full_name}')
    flash('Профиль обновлён', 'success')
    return redirect(url_for('my_profile'))


@app.route('/my/password', methods=['POST'])
@login_required
def my_password_update():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    ok, _ = authenticate_user(session['username'], current_password)
    if not ok:
        flash('Текущий пароль неверен', 'danger')
    elif not new_password or new_password != confirm_password:
        flash('Новый пароль и подтверждение не совпадают', 'danger')
    else:
        set_password(session['username'], new_password)
        audit.log_action(session.get('username'), 'change_own_password', '')
        flash('Пароль изменён', 'success')
    return redirect(url_for('my_profile'))


@app.route('/export/<kind>')
@report_required
def export_report(kind):
    try:
        if kind == 'svod1':
            years = pr.get_available_years()
            year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
            pf = request.args.get('pf', 'факт')
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_svod1(pr.svod1(year, pf, allocation))
        elif kind == 'svod2':
            years = pr.get_available_years()
            year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
            pf = request.args.get('pf', 'факт')
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_svod2(pr.svod2(year, pf, allocation))
        elif kind == 'dashboard1':
            years = pr.get_available_years()
            month = request.args.get('month', type=int) or date.today().month
            series, deltas = _series_deltas_from_request(years)
            projects = request.args.getlist('project') or None
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_dashboard(pr.dashboard1(month, series, deltas, projects, allocation=allocation), 'Dashboard1')
        elif kind == 'dashboard2':
            years = pr.get_available_years()
            month = request.args.get('month', type=int) or date.today().month
            series, deltas = _series_deltas_from_request(years)
            projects = request.args.getlist('project') or None
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_dashboard(pr.dashboard2(month, series, deltas, projects, allocation=allocation), 'Dashboard2')
        elif kind == 'unitpl':
            start = request.args.get('start', type=int)
            end = request.args.get('end', type=int)
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_unitpl(pr.unit_pl(start=start, end=end, allocation=allocation))
        elif kind == 'fot1':
            years = fr.get_available_years()
            year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
            pf = request.args.get('pf', 'факт')
            sheets = fr.export_fot1(fr.fot1(year, pf))
        elif kind == 'fot2':
            years = fr.get_available_years()
            month = request.args.get('month', type=int) or date.today().month
            series = _parse_series(request.args.get('series'))
            deltas = _parse_deltas(request.args.get('deltas'))
            if series is None or deltas is None:
                default_series, default_deltas = fr.default_series_deltas(years)
                series = series or default_series
                deltas = deltas or default_deltas
            sheets = fr.export_fot2(fr.fot2(month, series, deltas))
        elif kind == 'loans':
            periods = lr.get_available_periods()
            years = sorted({p.year for p in periods}) if periods else [date.today().year]
            year = request.args.get('year', type=int) or years[-1]
            month = request.args.get('month', type=int) or date.today().month
            pf = request.args.get('pf', 'факт')
            sheets = lr.export_loans(lr.loans(year, month, pf))
        elif kind == 'counterparty':
            contragents = request.args.getlist('name')
            if not contragents:
                return {'error': 'name обязателен'}, 400
            pf = request.args.get('pf', 'факт')
            projects = request.args.getlist('project') or None
            default_from, default_to = pr.default_counterparty_range(pf)
            date_from = request.args.get('date_from') or default_from.isoformat()
            date_to = request.args.get('date_to') or default_to.isoformat()
            sheets = pr.export_counterparty(pr.counterparty_series(contragents, pf, projects, date_from, date_to))
        elif kind == 'overview':
            years = pr.get_available_years()
            year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
            pf = request.args.get('pf', 'факт')
            allocation = request.args.get('allocation', 'all')
            sheets = pr.export_overview(pr.overview_data(year, pf, allocation))
        elif kind == 'investment':
            sheets = ir.export_summary(ir.all_dp_summary())
        elif kind == 'investment_detail':
            name = request.args.get('name', '')
            include_allocation = request.args.get('allocation', '1') != '0'
            data = ir.portfolio_detail(name, include_allocation)
            if data is None:
                return {'error': 'Портфель не найден'}, 404
            sheets = ir.export_detail(data)
        elif kind == 'cbr':
            sheets = cr.export_rows(cr.overall_by_month())
        elif kind == 'wallets':
            sheets = wr.export_summary(wr.all_wallets_summary())
        elif kind == 'wallets_detail':
            name = request.args.get('name', '')
            data = wr.wallet_detail(name, year='all')
            if data is None:
                return {'error': 'Кошелёк не найден'}, 404
            sheets = wr.export_detail(data)
        elif kind == 'wallets_ledger':
            name = request.args.get('name', '')
            year = request.args.get('year', type=int)
            date_from = date(year, 1, 1) if year else None
            date_to = date(year, 12, 31) if year else None
            data = wr.wallet_ledger(name, date_from, date_to)
            if data is None:
                return {'error': 'Кошелёк не найден'}, 404
            sheets = wr.export_ledger(data)
        else:
            return {'error': f'Неизвестный отчёт: {kind}'}, 404
    except Exception:
        app.logger.exception('Ошибка экспорта kind=%s', kind)
        return {'error': 'Ошибка при формировании отчёта'}, 500

    audit.log_action(session.get('username'), 'export', kind)
    buf = export.build_workbook(sheets)
    return send_file(
        buf, as_attachment=True, download_name=f'{kind}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/chat')
@report_required
def chat():
    return render_template('chat.html', configured=bool(Config.POLZA_AI_API_KEY))


@app.route('/api/chat', methods=['POST'])
@report_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get('question') or '').strip()
    history = payload.get('history') or []
    if not question:
        return jsonify({'error': 'Пустой вопрос'}), 400
    result = chat_assistant.ask(question, history)
    audit.log_action(session.get('username'), 'chat', question[:500])
    if 'error' in result:
        return jsonify(result), 200
    return jsonify(result)


if __name__ == '__main__':
    Config.validate()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True, use_reloader=False)
