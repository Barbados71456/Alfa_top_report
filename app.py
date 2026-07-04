import logging
import os
import threading
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, redirect, url_for, session, flash

from config import Config
from auth import login_required, admin_required, authenticate_user
from db import query, execute, close_connection
from reporting_refresh import refresh_all
import pl_report as pr
import fot_report as fr
import loans_report as lr

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


@app.route('/svod1')
@login_required
def svod1():
    years = pr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    data = pr.svod1(year, pf)
    return render_template('svod1.html', data=data, years=years, year=year, pf=pf)


@app.route('/api/cell_detail')
@login_required
def api_cell_detail():
    lines = request.args.getlist('line')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    pf = request.args.get('pf', 'факт')
    projects = request.args.getlist('project') or None
    if not (lines and year and month):
        return {'error': 'line, year, month обязательны'}, 400
    try:
        data = pr.cell_detail(lines, year, month, pf, projects)
    except Exception:
        app.logger.exception('cell_detail error')
        return {'error': 'Ошибка при получении детализации'}, 500
    return data


@app.route('/svod2')
@login_required
def svod2():
    years = pr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    data = pr.svod2(year, pf)
    return render_template('svod2.html', data=data, years=years, year=year, pf=pf)


@app.route('/unitpl')
@login_required
def unitpl():
    data = pr.unit_pl()
    return render_template('unitpl.html', data=data)


@app.route('/api/deviation_detail')
@login_required
def api_deviation_detail():
    lines = request.args.getlist('line')
    projects = request.args.getlist('project') or None
    a = request.args.get('a', '')
    b = request.args.get('b', '')
    month = request.args.get('month', type=int)
    try:
        a_pf, a_year = a.split(':')
        b_pf, b_year = b.split(':')
    except ValueError:
        return {'error': 'Некорректные параметры a/b (ожидается pf:year)'}, 400
    if not (lines and month):
        return {'error': 'line, month обязательны'}, 400
    try:
        data = pr.deviation_detail(lines, (a_pf, int(a_year), month), (b_pf, int(b_year), month), projects)
    except Exception:
        app.logger.exception('deviation_detail error')
        return {'error': 'Ошибка при получении акт-анализа'}, 500
    return data


@app.route('/dashboard1')
@login_required
def dashboard1():
    years = pr.get_available_years()
    month = request.args.get('month', type=int) or date.today().month
    series, deltas = _series_deltas_from_request(years)
    projects = request.args.getlist('project') or None
    data = pr.dashboard1(month, series, deltas, projects)
    return render_template(
        'dashboard1.html', data=data, years=years, month=month, projects=projects,
        all_projects=pr.get_projects_with_type(),
        series_str=_format_series(series), deltas_str=_format_deltas(deltas),
    )


@app.route('/dashboard2')
@login_required
def dashboard2():
    years = pr.get_available_years()
    month = request.args.get('month', type=int) or date.today().month
    series, deltas = _series_deltas_from_request(years)
    projects = request.args.getlist('project') or None
    data = pr.dashboard2(month, series, deltas, projects)
    return render_template(
        'dashboard2.html', data=data, years=years, month=month, projects=projects,
        all_projects=pr.get_projects_with_type(),
        series_str=_format_series(series), deltas_str=_format_deltas(deltas),
    )


@app.route('/fot1')
@login_required
def fot1():
    years = fr.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    pf = request.args.get('pf', 'факт')
    data = fr.fot1(year, pf)
    return render_template('fot1.html', data=data, years=years, year=year, pf=pf)


@app.route('/fot2')
@login_required
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
@login_required
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
@login_required
def counterparty():
    contragent = request.args.get('name', '').strip()
    pf = request.args.get('pf', 'факт')
    data = pr.counterparty_series(contragent, pf) if contragent else None
    return render_template(
        'counterparty.html', data=data, contragent=contragent, pf=pf,
        counterparties=pr.get_counterparties(),
    )


@app.route('/employees')
@admin_required
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
@admin_required
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
    flash(f'Данные сотрудника «{contragent}» обновлены', 'success')
    return redirect(url_for('employees', q=request.form.get('q', '')))


@app.route('/classifier')
@admin_required
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
@admin_required
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
    flash('Строка обновлена', 'success')
    return redirect(url_for('classifier', q=request.form.get('q', '')))


if __name__ == '__main__':
    Config.validate()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True, use_reloader=False)
