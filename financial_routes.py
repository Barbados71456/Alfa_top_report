# financial_routes.py
import os
import pandas as pd
import tempfile
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, send_file
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from db_utils import get_db

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
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM account_balances 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    balances = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(balances)


@financial_bp.route('/balances/add', methods=['POST'])
@login_required
def add_balance():
    """Добавить остаток на счете"""
    data = request.json
    
    if not data.get('bank_name') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO account_balances (date, bank_name, amount, user_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['bank_name'],
            data['amount'],
            session['user_id']
        ))
        
        balance_id = cur.fetchone()[0]
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
            SET bank_name = %s, amount = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['bank_name'],
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
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM liabilities 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY due_date ASC
    """, (session['user_id'], session.get('role'), date))
    
    liabilities = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(liabilities)


@financial_bp.route('/liabilities/add', methods=['POST'])
@login_required
def add_liability():
    """Добавить обязательство"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO liabilities (date, counterparty, purpose, amount, due_date, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data['amount'],
            data.get('due_date'),
            session['user_id']
        ))
        
        liability_id = cur.fetchone()[0]
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
            SET counterparty = %s, purpose = %s, amount = %s, due_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data['amount'],
            data.get('due_date'),
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


# ==================== ДЕБИТОРСКАЯ ЗАДОЛЖЕННОСТЬ ====================

@financial_bp.route('/receivables')
@login_required
def get_receivables():
    """Получить список дебиторской задолженности"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM receivables 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY due_date ASC
    """, (session['user_id'], session.get('role'), date))
    
    receivables = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(receivables)


@financial_bp.route('/receivables/add', methods=['POST'])
@login_required
def add_receivable():
    """Добавить дебиторскую задолженность"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO receivables (date, counterparty, purpose, portfolio, amount, due_date, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('due_date'),
            session['user_id']
        ))
        
        receivable_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': receivable_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/receivables/update/<int:receivable_id>', methods=['PUT'])
@login_required
def update_receivable(receivable_id):
    """Обновить дебиторскую задолженность"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE receivables 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, due_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('due_date'),
            receivable_id,
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


@financial_bp.route('/receivables/delete/<int:receivable_id>', methods=['DELETE'])
@login_required
def delete_receivable(receivable_id):
    """Удалить дебиторскую задолженность"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM receivables 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (receivable_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== АРЕНДА И ИНФОРМАЦИОННЫЕ УСЛУГИ ====================

@financial_bp.route('/rent_inf')
@login_required
def get_rent_inf():
    """Получить список аренды и информационных услуг"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM rent_inf_services 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    services = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(services)


@financial_bp.route('/rent_inf/add', methods=['POST'])
@login_required
def add_rent_inf():
    """Добавить аренду или инфоуслугу"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO rent_inf_services (date, counterparty, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        service_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': service_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/rent_inf/update/<int:service_id>', methods=['PUT'])
@login_required
def update_rent_inf(service_id):
    """Обновить аренду или инфоуслугу"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE rent_inf_services 
            SET counterparty = %s, portfolio = %s, amount = %s, responsible = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            service_id,
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


@financial_bp.route('/rent_inf/delete/<int:service_id>', methods=['DELETE'])
@login_required
def delete_rent_inf(service_id):
    """Удалить аренду или инфоуслугу"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM rent_inf_services 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (service_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ЭВАКУАЦИЯ ====================

@financial_bp.route('/evacuations')
@login_required
def get_evacuations():
    """Получить список эвакуаций"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM evacuations 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    evacuations = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(evacuations)


@financial_bp.route('/evacuations/add', methods=['POST'])
@login_required
def add_evacuation():
    """Добавить эвакуацию"""
    data = request.json
    
    if not data.get('purpose') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO evacuations (date, purpose, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['purpose'],
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        evacuation_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': evacuation_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/evacuations/update/<int:evacuation_id>', methods=['PUT'])
@login_required
def update_evacuation(evacuation_id):
    """Обновить эвакуацию"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE evacuations 
            SET purpose = %s, portfolio = %s, amount = %s, responsible = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['purpose'],
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            evacuation_id,
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


@financial_bp.route('/evacuations/delete/<int:evacuation_id>', methods=['DELETE'])
@login_required
def delete_evacuation(evacuation_id):
    """Удалить эвакуацию"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM evacuations 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (evacuation_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== СТОЯНКИ ====================

@financial_bp.route('/parkings')
@login_required
def get_parkings():
    """Получить список стоянок"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM parkings 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    parkings = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(parkings)


@financial_bp.route('/parkings/add', methods=['POST'])
@login_required
def add_parking():
    """Добавить стоянку"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO parkings (date, counterparty, purpose, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        parking_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': parking_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/parkings/update/<int:parking_id>', methods=['PUT'])
@login_required
def update_parking(parking_id):
    """Обновить стоянку"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE parkings 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, responsible = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            parking_id,
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


@financial_bp.route('/parkings/delete/<int:parking_id>', methods=['DELETE'])
@login_required
def delete_parking(parking_id):
    """Удалить стоянку"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM parkings 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (parking_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ЧУЖИЕ ДЕНЬГИ ====================

@financial_bp.route('/third_party')
@login_required
def get_third_party():
    """Получить список чужих денег"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM third_party_funds 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    funds = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(funds)


@financial_bp.route('/third_party/add', methods=['POST'])
@login_required
def add_third_party():
    """Добавить чужие деньги"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO third_party_funds (date, counterparty, purpose, portfolio, amount, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            session['user_id']
        ))
        
        fund_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': fund_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/third_party/update/<int:fund_id>', methods=['PUT'])
@login_required
def update_third_party(fund_id):
    """Обновить чужие деньги"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE third_party_funds 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            fund_id,
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


@financial_bp.route('/third_party/delete/<int:fund_id>', methods=['DELETE'])
@login_required
def delete_third_party(fund_id):
    """Удалить чужие деньги"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM third_party_funds 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (fund_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== НАЛОГИ ====================

@financial_bp.route('/taxes')
@login_required
def get_taxes():
    """Получить список налогов"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM taxes 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    taxes = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(taxes)


@financial_bp.route('/taxes/add', methods=['POST'])
@login_required
def add_tax():
    """Добавить налог"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO taxes (date, counterparty, purpose, portfolio, amount, responsible, ndfl, est, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            data.get('ndfl', 0),
            data.get('est', 0),
            session['user_id']
        ))
        
        tax_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': tax_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/taxes/update/<int:tax_id>', methods=['PUT'])
@login_required
def update_tax(tax_id):
    """Обновить налог"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE taxes 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, 
                responsible = %s, ndfl = %s, est = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            data.get('ndfl', 0),
            data.get('est', 0),
            tax_id,
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


@financial_bp.route('/taxes/delete/<int:tax_id>', methods=['DELETE'])
@login_required
def delete_tax(tax_id):
    """Удалить налог"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM taxes 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (tax_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ЗАРПЛАТА ====================

@financial_bp.route('/salaries')
@login_required
def get_salaries():
    """Получить список зарплат"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM salaries 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    salaries = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(salaries)


@financial_bp.route('/salaries/add', methods=['POST'])
@login_required
def add_salary():
    """Добавить зарплату"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO salaries (date, counterparty, purpose, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        salary_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': salary_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/salaries/update/<int:salary_id>', methods=['PUT'])
@login_required
def update_salary(salary_id):
    """Обновить зарплату"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE salaries 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, responsible = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            salary_id,
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


@financial_bp.route('/salaries/delete/<int:salary_id>', methods=['DELETE'])
@login_required
def delete_salary(salary_id):
    """Удалить зарплату"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM salaries 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (salary_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== ГОСПОШЛИНЫ ====================

@financial_bp.route('/state_duties')
@login_required
def get_state_duties():
    """Получить список госпошлин"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM state_duties 
        WHERE (user_id = %s OR %s = 'admin') AND date = %s
        ORDER BY id DESC
    """, (session['user_id'], session.get('role'), date))
    
    duties = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(duties)


@financial_bp.route('/state_duties/add', methods=['POST'])
@login_required
def add_state_duty():
    """Добавить госпошлину"""
    data = request.json
    
    if not data.get('counterparty') or not data.get('amount'):
        return jsonify({'error': 'Не заполнены обязательные поля'}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO state_duties (date, counterparty, purpose, portfolio, amount, responsible, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            session['user_id']
        ))
        
        duty_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'id': duty_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@financial_bp.route('/state_duties/update/<int:duty_id>', methods=['PUT'])
@login_required
def update_state_duty(duty_id):
    """Обновить госпошлину"""
    data = request.json
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE state_duties 
            SET counterparty = %s, purpose = %s, portfolio = %s, amount = %s, responsible = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (
            data['counterparty'],
            data.get('purpose'),
            data.get('portfolio'),
            data['amount'],
            data.get('responsible'),
            duty_id,
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


@financial_bp.route('/state_duties/delete/<int:duty_id>', methods=['DELETE'])
@login_required
def delete_state_duty(duty_id):
    """Удалить госпошлину"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM state_duties 
            WHERE id = %s AND (user_id = %s OR %s = 'admin')
        """, (duty_id, session['user_id'], session.get('role')))
        
        if cur.rowcount == 0:
            return jsonify({'error': 'Запись не найдена или нет прав'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== СВОДНЫЕ ДАННЫЕ ====================

@financial_bp.route('/summary')
@login_required
def get_summary():
    """Получить сводные данные"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Получаем общую сумму остатков (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_balance
        FROM account_balances
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_balance = cur.fetchone()['total_balance']
    
    # Получаем общую сумму обязательств (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_liabilities
        FROM liabilities
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_liabilities = cur.fetchone()['total_liabilities']
    
    # Получаем сумму дебиторской задолженности (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_receivables
        FROM receivables
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_receivables = cur.fetchone()['total_receivables']
    
    # Получаем сумму чужих денег (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_third_party
        FROM third_party_funds
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_third_party = cur.fetchone()['total_third_party']
    
    # Получаем сумму налогов (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_taxes
        FROM taxes
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_taxes = cur.fetchone()['total_taxes']
    
    # Получаем сумму зарплат (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_salaries
        FROM salaries
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_salaries = cur.fetchone()['total_salaries']
    
    # Получаем сумму госпошлин (все даты)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_duties
        FROM state_duties
        WHERE user_id = %s OR %s = 'admin'
    """, (session['user_id'], session.get('role')))
    total_duties = cur.fetchone()['total_duties']
    
    cur.close()
    conn.close()
    
    deficit = total_balance - total_liabilities
    
    return jsonify({
        'total_balance': total_balance,
        'total_liabilities': total_liabilities,
        'total_receivables': total_receivables,
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
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Определяем таблицу и поля для экспорта
    export_config = {
        'balances': {
            'table': 'account_balances',
            'columns': ['id', 'date', 'bank_name', 'amount'],
            'headers': ['ID', 'Дата', 'Банк/Наличные', 'Сумма']
        },
        'liabilities': {
            'table': 'liabilities',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'amount', 'due_date'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Сумма', 'Срок оплаты']
        },
        'receivables': {
            'table': 'receivables',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'due_date'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение', 'Портфель', 'Сумма', 'Срок оплаты']
        },
        'rent_inf': {
            'table': 'rent_inf_services',
            'columns': ['id', 'date', 'counterparty', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Портфель', 'Сумма', 'Ответственный']
        },
        'evacuations': {
            'table': 'evacuations',
            'columns': ['id', 'date', 'purpose', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Назначение платежа', 'Портфель', 'Сумма', 'Ответственный']
        },
        'parkings': {
            'table': 'parkings',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение платежа', 'Портфель', 'Сумма', 'Ответственный']
        },
        'third_party': {
            'table': 'third_party_funds',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение платежа', 'Портфель', 'Сумма']
        },
        'taxes': {
            'table': 'taxes',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'responsible', 'ndfl', 'est'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение платежа', 'Портфель', 'Сумма', 'Ответственный', 'НДФЛ', 'ЕСТ']
        },
        'salaries': {
            'table': 'salaries',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение платежа', 'Портфель', 'Сумма', 'Ответственный']
        },
        'state_duties': {
            'table': 'state_duties',
            'columns': ['id', 'date', 'counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'headers': ['ID', 'Дата', 'Контрагент', 'Назначение платежа', 'Портфель', 'Сумма', 'Ответственный']
        }
    }
    
    if section not in export_config:
        return jsonify({'error': 'Неизвестный раздел'}), 400
    
    config = export_config[section]
    
    try:
        cur.execute(f"""
            SELECT {', '.join(config['columns'])}
            FROM {config['table']}
            WHERE (user_id = %s OR %s = 'admin') AND date = %s
            ORDER BY id DESC
        """, (session['user_id'], session.get('role'), date))
        
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
        filename = f"{section}_{date}_{datetime.now().strftime('%H%M%S')}.xlsx"
        
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
    
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # Конфигурация импорта для каждого раздела
    import_config = {
        'balances': {
            'table': 'account_balances',
            'columns': ['bank_name', 'amount'],
            'required': ['bank_name', 'amount']
        },
        'liabilities': {
            'table': 'liabilities',
            'columns': ['counterparty', 'purpose', 'amount', 'due_date'],
            'required': ['counterparty', 'amount']
        },
        'receivables': {
            'table': 'receivables',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount', 'due_date'],
            'required': ['counterparty', 'amount']
        },
        'rent_inf': {
            'table': 'rent_inf_services',
            'columns': ['counterparty', 'portfolio', 'amount', 'responsible'],
            'required': ['counterparty', 'amount']
        },
        'evacuations': {
            'table': 'evacuations',
            'columns': ['purpose', 'portfolio', 'amount', 'responsible'],
            'required': ['purpose', 'amount']
        },
        'parkings': {
            'table': 'parkings',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'required': ['counterparty', 'amount']
        },
        'third_party': {
            'table': 'third_party_funds',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount'],
            'required': ['counterparty', 'amount']
        },
        'taxes': {
            'table': 'taxes',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount', 'responsible', 'ndfl', 'est'],
            'required': ['counterparty', 'amount']
        },
        'salaries': {
            'table': 'salaries',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'required': ['counterparty', 'amount']
        },
        'state_duties': {
            'table': 'state_duties',
            'columns': ['counterparty', 'purpose', 'portfolio', 'amount', 'responsible'],
            'required': ['counterparty', 'amount']
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
                values = [date]  # дата
                for col in config['columns']:
                    if col in row and pd.notna(row[col]):
                        value = row[col]
                        values.append(value)
                    else:
                        values.append(None)
                values.append(session['user_id'])
                
                # Создаем SQL запрос
                placeholders = ', '.join(['%s'] * (len(config['columns']) + 2))
                columns = 'date, ' + ', '.join(config['columns']) + ', user_id'
                
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
            'errors': errors[:10]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500