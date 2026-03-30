# financial_routes.py
import os
import pandas as pd
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, send_file
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from db_utils import get_db  # Импортируем из существующего модуля

# Создаем Blueprint
financial_bp = Blueprint('financial', __name__, url_prefix='/financial')

# Декоратор проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ГЛАВНАЯ СТРАНИЦА ====================

@financial_bp.route('/')
@login_required
def dashboard():
    """Главная страница финансового модуля"""
    return render_template('financial/dashboard.html')

# ==================== ОСТАТКИ НА СЧЕТАХ ====================

@financial_bp.route('/balances')
@login_required
def get_balances():
    """Получить список остатков на счетах"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM account_balances 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC, id DESC
    """, (session['user_id'], session.get('role')))
    
    balances = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(balances)

@financial_bp.route('/balances/add', methods=['POST'])
@login_required
def add_balance():
    """Добавить остаток на счете"""
    data = request.json
    
    if not data.get('date') or not data.get('bank_name') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO account_balances (date, bank_name, portfolio, amount, user_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['bank_name'],
            data.get('portfolio'),
            data['amount'],
            session['user_id']
        ))
        
        balance_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': balance_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@financial_bp.route('/balances/update/<int:balance_id>', methods=['PUT'])
@login_required
def update_balance(balance_id):
    """Обновить остаток на счете"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE account_balances 
            SET date = %s, bank_name = %s, portfolio = %s, amount = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['date'],
            data['bank_name'],
            data.get('portfolio'),
            data['amount'],
            balance_id,
            session['user_id'],
            session.get('role')
        ))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@financial_bp.route('/balances/delete/<int:balance_id>', methods=['DELETE'])
@login_required
def delete_balance(balance_id):
    """Удалить остаток на счете"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM account_balances 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (balance_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ОБЯЗАТЕЛЬСТВА ====================

@financial_bp.route('/liabilities')
@login_required
def get_liabilities():
    """Получить список обязательств"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM liabilities 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY due_date ASC, date DESC
    """, (session['user_id'], session.get('role')))
    
    liabilities = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(liabilities)

@financial_bp.route('/liabilities/add', methods=['POST'])
@login_required
def add_liability():
    """Добавить обязательство"""
    data = request.json
    
    if not data.get('due_date') or not data.get('description') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO liabilities (date, due_date, description, amount, portfolio, comments, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['due_date'],
            data['description'],
            data['amount'],
            data.get('portfolio'),
            data.get('comments'),
            data.get('status', 'pending'),
            session['user_id']
        ))
        
        liability_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': liability_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@financial_bp.route('/liabilities/update/<int:liability_id>', methods=['PUT'])
@login_required
def update_liability(liability_id):
    """Обновить обязательство"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE liabilities 
            SET date = %s, due_date = %s, description = %s, amount = %s, 
                portfolio = %s, comments = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data.get('date'),
            data['due_date'],
            data['description'],
            data['amount'],
            data.get('portfolio'),
            data.get('comments'),
            data.get('status'),
            liability_id,
            session['user_id'],
            session.get('role')
        ))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@financial_bp.route('/liabilities/delete/<int:liability_id>', methods=['DELETE'])
@login_required
def delete_liability(liability_id):
    """Удалить обязательство"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM liabilities 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (liability_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== КРЕДИТЫ И ЗАЙМЫ ====================

@financial_bp.route('/credits')
@login_required
def get_credits():
    """Получить список кредитов и займов"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM credits_loans 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    credits = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(credits)

@financial_bp.route('/credits/add', methods=['POST'])
@login_required
def add_credit():
    """Добавить кредит/займ"""
    data = request.json
    
    if not data.get('date') or not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO credits_loans (date, counterparty, purpose, service_type, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['counterparty'],
            data.get('purpose'),
            data.get('service_type'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        credit_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': credit_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== АРЕНДА И ИНФОРМАЦИОННЫЕ УСЛУГИ ====================

@financial_bp.route('/rent_inf')
@login_required
def get_rent_inf():
    """Получить список аренды и информационных услуг"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM rent_inf_services 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    services = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(services)

@financial_bp.route('/rent_inf/add', methods=['POST'])
@login_required
def add_rent_inf():
    """Добавить аренду или инфоуслугу"""
    data = request.json
    
    if not data.get('date') or not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO rent_inf_services (date, counterparty, purpose, service_type, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['counterparty'],
            data.get('purpose'),
            data.get('service_type'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        service_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': service_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ЭВАКУАЦИЯ ====================

@financial_bp.route('/evacuations')
@login_required
def get_evacuations():
    """Получить список эвакуаций"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM evacuations 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    evacuations = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(evacuations)

@financial_bp.route('/evacuations/add', methods=['POST'])
@login_required
def add_evacuation():
    """Добавить эвакуацию"""
    data = request.json
    
    if not data.get('date') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO evacuations (date, counterparty, purpose, portfolio, amount, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data.get('counterparty'),
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('status', 'pending'),
            session['user_id']
        ))
        
        evacuation_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': evacuation_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== СТОЯНКИ ====================

@financial_bp.route('/parkings')
@login_required
def get_parkings():
    """Получить список стоянок"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM parkings 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    parkings = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(parkings)

@financial_bp.route('/parkings/add', methods=['POST'])
@login_required
def add_parking():
    """Добавить стоянку"""
    data = request.json
    
    if not data.get('date') or not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO parkings (date, counterparty, period, purpose, portfolio, amount, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['counterparty'],
            data.get('period'),
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('status', 'pending'),
            session['user_id']
        ))
        
        parking_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': parking_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ЧУЖИЕ ДЕНЬГИ ====================

@financial_bp.route('/third_party')
@login_required
def get_third_party():
    """Получить список чужих денег"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM third_party_funds 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY due_date ASC, date DESC
    """, (session['user_id'], session.get('role')))
    
    funds = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(funds)

@financial_bp.route('/third_party/add', methods=['POST'])
@login_required
def add_third_party():
    """Добавить чужие деньги"""
    data = request.json
    
    if not data.get('date') or not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO third_party_funds (date, counterparty, purpose, portfolio, amount, due_date, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('due_date'),
            data.get('status', 'pending'),
            session['user_id']
        ))
        
        fund_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': fund_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== НАЛОГИ ====================

@financial_bp.route('/taxes')
@login_required
def get_taxes():
    """Получить список налогов"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM taxes 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    taxes = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(taxes)

@financial_bp.route('/taxes/add', methods=['POST'])
@login_required
def add_tax():
    """Добавить налог"""
    data = request.json
    
    if not data.get('date') or not data.get('tax_type') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO taxes (date, tax_type, portfolio, amount, quarter, penalty, status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data['tax_type'],
            data.get('portfolio'),
            data['amount'],
            data.get('quarter'),
            data.get('penalty', 0),
            data.get('status', 'pending'),
            session['user_id']
        ))
        
        tax_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': tax_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ЗАРПЛАТА ====================

@financial_bp.route('/salaries')
@login_required
def get_salaries():
    """Получить список зарплат"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM salaries 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    salaries = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(salaries)

@financial_bp.route('/salaries/add', methods=['POST'])
@login_required
def add_salary():
    """Добавить зарплату"""
    data = request.json
    
    if not data.get('date') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO salaries (date, portfolio, amount, tax_amount, user_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data.get('portfolio'),
            data['amount'],
            data.get('tax_amount', 0),
            session['user_id']
        ))
        
        salary_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': salary_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ГОСПОШЛИНЫ ====================

@financial_bp.route('/state_duties')
@login_required
def get_state_duties():
    """Получить список госпошлин"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM state_duties 
        WHERE user_id = %s OR %s = 'admin'
        ORDER BY date DESC
    """, (session['user_id'], session.get('role')))
    
    duties = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(duties)

@financial_bp.route('/state_duties/add', methods=['POST'])
@login_required
def add_state_duty():
    """Добавить госпошлину"""
    data = request.json
    
    if not data.get('date') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO state_duties (date, portfolio, case_name, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data['date'],
            data.get('portfolio'),
            data.get('case_name'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        duty_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': duty_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== СВОДНЫЕ ДАННЫЕ ====================

@financial_bp.route('/summary')
@login_required
def get_summary():
    """Получить сводные данные"""
    conn = get_db()
    cur = conn.cursor()
    
    # Получаем общую сумму остатков
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_balance
        FROM account_balances
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_balance = cur.fetchone()['total_balance']
    
    # Получаем общую сумму обязательств (pending)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_liabilities
        FROM liabilities
        WHERE (user_id = %s OR %s = 'admin') AND status = 'pending'
    """, (session['user_id'], session.get('role')))
    total_liabilities = cur.fetchone()['total_liabilities']
    
    # Получаем сумму чужих денег (pending)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_third_party
        FROM third_party_funds
        WHERE (user_id = %s OR %s = 'admin') AND status = 'pending'
    """, (session['user_id'], session.get('role')))
    total_third_party = cur.fetchone()['total_third_party']
    
    # Получаем сумму налогов (pending)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_taxes
        FROM taxes
        WHERE (user_id = %s OR %s = 'admin') AND status = 'pending'
    """, (session['user_id'], session.get('role')))
    total_taxes = cur.fetchone()['total_taxes']
    
    # Получаем сумму зарплат (последний месяц)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_salaries
        FROM salaries
        WHERE (user_id = %s OR %s = 'admin')
        AND date >= date_trunc('month', CURRENT_DATE)
    """, (session['user_id'], session.get('role')))
    total_salaries = cur.fetchone()['total_salaries']
    
    # Получаем сумму госпошлин (последний месяц)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_duties
        FROM state_duties
        WHERE (user_id = %s OR %s = 'admin')
        AND date >= date_trunc('month', CURRENT_DATE)
    """, (session['user_id'], session.get('role')))
    total_duties = cur.fetchone()['total_duties']
    
    cur.close()
    conn.close()
    
    deficit = total_balance - total_liabilities
    
    return jsonify({
        'total_balance': total_balance,
        'total_liabilities': total_liabilities,
        'total_third_party': total_third_party,
        'total_taxes': total_taxes,
        'total_salaries': total_salaries,
        'total_duties': total_duties,
        'deficit': deficit
    })

# ==================== ЭКСПОРТ ====================

@financial_bp.route('/export/<string:section>')
@login_required
def export_section(section):
    """Экспорт раздела в Excel"""
    conn = get_db()
    cur = conn.cursor()
    
    # Определяем таблицу и поля для экспорта
    export_config = {
        'balances': {
            'table': 'account_balances',
            'columns': ['id', 'date', 'bank_name', 'portfolio', 'amount', 'created_at'],
            'headers': ['ID', 'Дата', 'Банк', 'Портфель', 'Сумма', 'Дата создания']
        },
        'liabilities': {
            'table': 'liabilities',
            'columns': ['id', 'date', 'due_date', 'description', 'amount', 'portfolio', 'comments', 'status'],
            'headers': ['ID', 'Дата создания', 'Срок оплаты', 'Описание', 'Сумма', 'Портфель', 'Комментарий', 'Статус']
        },
        'credits': {
            'table': 'credits_loans',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'service_type', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Тип услуги', 'Портфель', 'Сумма', 'Ответственный']
        },
        'rent_inf': {
            'table': 'rent_inf_services',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'service_type', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Тип услуги', 'Портфель', 'Сумма', 'Ответственный']
        },
        'evacuations': {
            'table': 'evacuations',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'status'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Портфель', 'Сумма', 'Статус']
        },
        'parkings': {
            'table': 'parkings',
            'columns': ['id', 'date', 'counterparty', 'period', 'purpose', 'portfolio', 'amount', 'status'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Период', 'Назначение', 'Портфель', 'Сумма', 'Статус']
        },
        'third_party': {
            'table': 'third_party_funds',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'due_date', 'status'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Портфель', 'Сумма', 'Срок возврата', 'Статус']
        },
        'taxes': {
            'table': 'taxes',
            'columns': ['id', 'date', 'tax_type', 'portfolio', 'amount', 'quarter', 'penalty', 'status'],
            'headers': ['ID', 'Дата', 'Тип налога', 'Портфель', 'Сумма', 'Квартал', 'Пени', 'Статус']
        },
        'salaries': {
            'table': 'salaries',
            'columns': ['id', 'date', 'portfolio', 'amount', 'tax_amount'],
            'headers': ['ID', 'Дата', 'Портфель', 'Сумма', 'Сумма налога']
        },
        'state_duties': {
            'table': 'state_duties',
            'columns': ['id', 'date', 'portfolio', 'case_name', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Портфель', 'Название дела', 'Сумма', 'Ответственный']
        }
    }
    
    if section not in export_config:
        return jsonify({'error': 'Неизвестный раздел'}), 400
    
    config = export_config[section]
    
    try:
        cur.execute(f"""
            SELECT {', '.join(config['columns'])}
            FROM {config['table']}
            WHERE user_id = %s OR %s = 'admin'
            ORDER BY date DESC
        """, (session['user_id'], session.get('role')))
        
        data = cur.fetchall()
        
        # Преобразуем в DataFrame
        df_data = []
        for row in data:
            df_row = {}
            for i, col in enumerate(config['columns']):
                value = row[col]
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d')
                df_row[config['headers'][i]] = value
            df_data.append(df_row)
        
        df = pd.DataFrame(df_data)
        filename = f"{section}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = tmp.name
        
        cur.close()
        conn.close()
        
        # Отправляем файл
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ИМПОРТ ====================

@financial_bp.route('/import/<string:section>', methods=['POST'])
@login_required
def import_section(section):
    """Импорт раздела из Excel"""
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return jsonify({'error': 'Пожалуйста, загрузите файл Excel (.xlsx, .xls)'}), 400
    
    # Конфигурация импорта для каждого раздела
    import_config = {
        'balances': {
            'table': 'account_balances',
            'columns': ['date', 'bank_name', 'portfolio', 'amount'],
            'required': ['date', 'bank_name', 'amount']
        },
        'liabilities': {
            'table': 'liabilities',
            'columns': ['date', 'due_date', 'description', 'amount', 'portfolio', 'comments', 'status'],
            'required': ['due_date', 'description', 'amount']
        },
        'credits': {
            'table': 'credits_loans',
            'columns': ['date', 'counterparty', 'purpose', 'service_type', 'portfolio', 'amount', 'responsible'],
            'required': ['date', 'counterparty', 'amount']
        },
        'rent_inf': {
            'table': 'rent_inf_services',
            'columns': ['date', 'counterparty', 'purpose', 'service_type', 'portfolio', 'amount', 'responsible'],
            'required': ['date', 'counterparty', 'amount']
        },
        'evacuations': {
            'table': 'evacuations',
            'columns': ['date', 'counterparty', 'purpose', 'portfolio', 'amount', 'status'],
            'required': ['date', 'amount']
        },
        'parkings': {
            'table': 'parkings',
            'columns': ['date', 'counterparty', 'period', 'purpose', 'portfolio', 'amount', 'status'],
            'required': ['date', 'counterparty', 'amount']
        },
        'third_party': {
            'table': 'third_party_funds',
            'columns': ['date', 'counterparty', 'purpose', 'portfolio', 'amount', 'due_date', 'status'],
            'required': ['date', 'counterparty', 'amount']
        },
        'taxes': {
            'table': 'taxes',
            'columns': ['date', 'tax_type', 'portfolio', 'amount', 'quarter', 'penalty', 'status'],
            'required': ['date', 'tax_type', 'amount']
        },
        'salaries': {
            'table': 'salaries',
            'columns': ['date', 'portfolio', 'amount', 'tax_amount'],
            'required': ['date', 'amount']
        },
        'state_duties': {
            'table': 'state_duties',
            'columns': ['date', 'portfolio', 'case_name', 'amount', 'responsible'],
            'required': ['date', 'amount']
        }
    }
    
    if section not in import_config:
        return jsonify({'error': 'Неизвестный раздел'}), 400
    
    config = import_config[section]
    
    try:
        # Читаем файл
        df = pd.read_excel(file)
        
        # Проверяем наличие необходимых колонок
        missing_columns = []
        for col in config['required']:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            return jsonify({'error': f'В файле отсутствуют колонки: {", ".join(missing_columns)}'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        successful = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Подготавливаем значения для вставки
                values = []
                for col in config['columns']:
                    if col in row and pd.notna(row[col]):
                        value = row[col]
                        # Преобразуем даты
                        if col == 'date' or col == 'due_date':
                            if isinstance(value, str):
                                value = datetime.strptime(value, '%Y-%m-%d')
                            else:
                                value = pd.to_datetime(value).to_pydatetime()
                        values.append(value)
                    else:
                        values.append(None)
                
                # Добавляем user_id в конец
                values.append(session['user_id'])
                
                # Создаем SQL запрос
                placeholders = ', '.join(['%s'] * (len(config['columns']) + 1))
                columns = ', '.join(config['columns'] + ['user_id'])
                
                cur.execute(f"""
                    INSERT INTO {config['table']} ({columns})
                    VALUES ({placeholders})
                """, values)
                
                successful += 1
                
            except Exception as e:
                errors.append(f"Строка {index + 2}: {str(e)}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'imported': successful,
            'errors': errors[:10]  # Возвращаем первые 10 ошибок
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500