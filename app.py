import logging
import os
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, session, flash

from config import Config
from auth import login_required, admin_required, authenticate_user
from db import query, execute, close_connection
import reports

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_connection)

try:
    Config.validate()
except ValueError:
    app.logger.exception('Некорректная конфигурация окружения')
    raise


@app.route('/')
def index():
    return redirect(url_for('svod') if 'user_id' in session else url_for('login'))


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
            return redirect(url_for('svod'))
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


@app.route('/svod')
@login_required
def svod():
    years = reports.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    source = request.args.get('source', 'fact')
    if source not in ('fact', 'plan'):
        source = 'fact'
    if source == 'plan' and year != 2026:
        year = 2026
    data = reports.get_svod(year, source)
    plan_years = [2026]
    return render_template('svod.html', data=data, years=years, year=year, source=source, plan_years=plan_years)


@app.route('/dashboard')
@login_required
def dashboard():
    all_lines = reports.SVOD_FACT_LINES + reports.SVOD_FACT_BELOW
    line = request.args.get('line') or all_lines[0][0]
    years = reports.get_available_years()
    selected_years = years[-4:] if len(years) > 4 else years
    data = reports.get_dashboard(line, selected_years)
    return render_template('dashboard.html', data=data, lines=all_lines, line=line, years=years)


@app.route('/portfolio')
@login_required
def portfolio():
    projects = reports.get_projects()
    project = request.args.get('project') or (projects[0] if projects else None)
    years = reports.get_available_years()
    year = request.args.get('year', type=int) or (years[-1] if years else date.today().year)
    data = reports.get_svod_for_project(project, year) if project else None
    return render_template('portfolio.html', data=data, projects=projects, project=project, years=years, year=year)


@app.route('/investments')
@login_required
def investments():
    years = reports.get_available_years()
    selected_years = years[-4:] if len(years) > 4 else years
    data = reports.get_investments(selected_years)
    return render_template('investments.html', data=data, years=years)


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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True)
