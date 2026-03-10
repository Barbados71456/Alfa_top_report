import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from functools import wraps
from datetime import datetime
import hashlib
from dotenv import load_dotenv
import pandas as pd
import io
import csv
import tempfile

# Загружаем переменные из .env файла
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Database configuration - берем из переменных окружения
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'dbname': os.environ.get('POSTGRES_DB'),
    'user': os.environ.get('POSTGRES_USER'),
    'password': os.environ.get('POSTGRES_PASSWORD')
}

# Проверяем, что все параметры БД заданы
if not all([DB_CONFIG['host'], DB_CONFIG['dbname'], DB_CONFIG['user'], DB_CONFIG['password']]):
    print("ОШИБКА: Не все параметры подключения к БД заданы в .env файле!")
    print("Текущие параметры:", {k: v if k != 'password' else '***' for k, v in DB_CONFIG.items()})

def get_db():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Ошибка подключения к БД: {e}")
        print("Проверьте параметры подключения в .env файле")
        raise

def init_db():
    """Initialize database tables"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Create users table with password_hash instead of password
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(200) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create periods table for editing control
        cur.execute('''
            CREATE TABLE IF NOT EXISTS periods (
                id SERIAL PRIMARY KEY,
                year INTEGER,
                month INTEGER,
                is_closed BOOLEAN DEFAULT FALSE,
                closed_by_user_id INTEGER REFERENCES users(id),
                closed_at TIMESTAMP,
                UNIQUE(year, month)
            )
        ''')
        
        # Create reference tables
        cur.execute('''
            CREATE TABLE IF NOT EXISTS signs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                sign_id INTEGER REFERENCES signs(id) ON DELETE CASCADE,
                UNIQUE(name, sign_id)
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                UNIQUE(name, category_id)
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS counterparties (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS wallet_types (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                wallet_type_id INTEGER REFERENCES wallet_types(id) ON DELETE CASCADE,
                UNIQUE(name, wallet_type_id)
            )
        ''')
        
        # Create main expenses table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                year INTEGER,
                month INTEGER,
                sign_id INTEGER REFERENCES signs(id),
                category_id INTEGER REFERENCES categories(id),
                article_id INTEGER REFERENCES articles(id),
                project_id INTEGER REFERENCES projects(id),
                counterparty_id INTEGER REFERENCES counterparties(id),
                wallet_type_id INTEGER REFERENCES wallet_types(id),
                wallet_id INTEGER REFERENCES wallets(id),
                amount DECIMAL(10,2) NOT NULL,
                comments TEXT,
                pl VARCHAR(255),
                user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default data if not exists
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()['count']
        if user_count == 0:
            admin_password = hashlib.sha256(os.environ.get('ADMIN_PASSWORD', 'admin123').encode()).hexdigest()
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (os.environ.get('ADMIN_USERNAME', 'admin'), admin_password, 'admin')
            )
            print("Создан пользователь admin")
        
        # Insert default reference data
        default_signs = ['IN', 'OUT']
        for sign in default_signs:
            cur.execute("INSERT INTO signs (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (sign,))
        
        default_categories = [
            ('Доходы', 'IN'),
            ('Расходы', 'OUT')
        ]
        for cat_name, sign_name in default_categories:
            cur.execute("SELECT id FROM signs WHERE name = %s", (sign_name,))
            sign_row = cur.fetchone()
            if sign_row:
                cur.execute(
                    "INSERT INTO categories (name, sign_id) VALUES (%s, %s) ON CONFLICT (name, sign_id) DO NOTHING",
                    (cat_name, sign_row['id'])
                )
        
        default_projects = ['Основной', 'Личный', 'Бизнес']
        for project in default_projects:
            cur.execute("INSERT INTO projects (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (project,))
        
        default_counterparties = ['Клиент 1', 'Поставщик 1', 'Сотрудник']
        for counterparty in default_counterparties:
            cur.execute("INSERT INTO counterparties (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (counterparty,))
        
        default_wallet_types = ['Наличные', 'Банковская карта', 'Электронный кошелек']
        for wt in default_wallet_types:
            cur.execute("INSERT INTO wallet_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (wt,))
        
        conn.commit()
        cur.close()
        conn.close()
        print("База данных успешно инициализирована")
    except Exception as e:
        print(f"Ошибка при инициализации БД: {e}")
        raise

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Check if period is editable
def is_period_editable(date):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT is_closed FROM periods WHERE year = %s AND month = %s",
        (date.year, date.month)
    )
    period = cur.fetchone()
    cur.close()
    conn.close()
    
    if period and period['is_closed']:
        return False
    return True

def get_month_name(month_num):
    """Возвращает название месяца на русском"""
    months = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    return months.get(month_num, '')

@app.route('/')
@login_required
def index():
    conn = get_db()
    cur = conn.cursor()
    
    if session['role'] == 'admin':
        cur.execute('''
            SELECT e.*, u.username, s.name as sign_name, c.name as category_name,
                   a.name as article_name, p.name as project_name, cp.name as counterparty_name,
                   wt.name as wallet_type_name, w.name as wallet_name
            FROM expenses e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN signs s ON e.sign_id = s.id
            LEFT JOIN categories c ON e.category_id = c.id
            LEFT JOIN articles a ON e.article_id = a.id
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN counterparties cp ON e.counterparty_id = cp.id
            LEFT JOIN wallet_types wt ON e.wallet_type_id = wt.id
            LEFT JOIN wallets w ON e.wallet_id = w.id
            ORDER BY e.date DESC
        ''')
        expenses = cur.fetchall()
        
        # Подсчет сумм для админа (все записи)
        cur.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as total_in,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as total_out,
                COALESCE(SUM(amount), 0) as total_balance
            FROM expenses
        ''')
    else:
        cur.execute('''
            SELECT e.*, u.username, s.name as sign_name, c.name as category_name,
                   a.name as article_name, p.name as project_name, cp.name as counterparty_name,
                   wt.name as wallet_type_name, w.name as wallet_name
            FROM expenses e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN signs s ON e.sign_id = s.id
            LEFT JOIN categories c ON e.category_id = c.id
            LEFT JOIN articles a ON e.article_id = a.id
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN counterparties cp ON e.counterparty_id = cp.id
            LEFT JOIN wallet_types wt ON e.wallet_type_id = wt.id
            LEFT JOIN wallets w ON e.wallet_id = w.id
            WHERE e.user_id = %s
            ORDER BY e.date DESC
        ''', (session['user_id'],))
        expenses = cur.fetchall()
        
        # Подсчет сумм для конкретного пользователя
        cur.execute('''
            SELECT 
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as total_in,
                COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as total_out,
                COALESCE(SUM(amount), 0) as total_balance
            FROM expenses
            WHERE user_id = %s
        ''', (session['user_id'],))
    
    totals = cur.fetchone()
    
    # Добавляем название месяца к каждой записи
    for expense in expenses:
        expense['month_name'] = get_month_name(expense['month'])
    
    cur.close()
    conn.close()
    
    return render_template('index.html', 
                         expenses=expenses,
                         total_in=totals['total_in'],
                         total_out=totals['total_out'],
                         total_balance=totals['total_balance'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM users WHERE username = %s AND password_hash = %s",
                (username, password)
            )
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                flash('Успешный вход в систему', 'success')
                return redirect(url_for('index'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        except Exception as e:
            flash(f'Ошибка подключения к базе данных: {str(e)}', 'danger')
            print(f"Login error: {e}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@admin_required  # Добавляем требование прав администратора
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        try:
            conn = get_db()
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'user')",
                    (username, password)
                )
                conn.commit()
                flash(f'Пользователь {username} успешно создан', 'success')
                return redirect(url_for('manage_users'))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash('Пользователь с таким именем уже существует', 'danger')
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            flash(f'Ошибка подключения к базе данных: {str(e)}', 'danger')
            print(f"Register error: {e}")
    
    return render_template('register.html')

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        
        if not is_period_editable(date):
            flash('Этот период закрыт для редактирования', 'danger')
            return redirect(url_for('index'))
        
        conn = get_db()
        cur = conn.cursor()
        
        try:
            cur.execute('''
                INSERT INTO expenses (
                    date, year, month, sign_id, category_id, article_id,
                    project_id, counterparty_id, wallet_type_id, wallet_id,
                    amount, comments, pl, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                date, date.year, date.month,
                request.form['sign_id'] or None,
                request.form['category_id'] or None,
                request.form['article_id'] or None,
                request.form['project_id'] or None,
                request.form['counterparty_id'] or None,
                request.form['wallet_type_id'] or None,
                request.form['wallet_id'] or None,
                request.form['amount'],
                request.form['comments'],
                request.form['pl'],
                session['user_id']
            ))
            conn.commit()
            flash('Запись успешно добавлена', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при добавлении: {str(e)}', 'danger')
        finally:
            cur.close()
            conn.close()
        
        return redirect(url_for('index'))
    
    # GET request - show form
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM signs ORDER BY name")
    signs = cur.fetchall()
    
    cur.execute("SELECT * FROM categories ORDER BY name")
    categories = cur.fetchall()
    
    cur.execute("SELECT * FROM articles ORDER BY name")
    articles = cur.fetchall()
    
    cur.execute("SELECT * FROM projects ORDER BY name")
    projects = cur.fetchall()
    
    cur.execute("SELECT * FROM counterparties ORDER BY name")
    counterparties = cur.fetchall()
    
    cur.execute("SELECT * FROM wallet_types ORDER BY name")
    wallet_types = cur.fetchall()
    
    cur.execute("SELECT * FROM wallets ORDER BY name")
    wallets = cur.fetchall()
    
    cur.close()
    conn.close()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('add_expense.html', 
                         signs=signs, categories=categories, articles=articles,
                         projects=projects, counterparties=counterparties,
                         wallet_types=wallet_types, wallets=wallets,
                         today=today)

@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    conn = get_db()
    cur = conn.cursor()
    
    # Get expense data
    cur.execute('''
        SELECT e.*, s.name as sign_name, c.name as category_name,
               a.name as article_name, p.name as project_name,
               cp.name as counterparty_name, wt.name as wallet_type_name,
               w.name as wallet_name
        FROM expenses e
        LEFT JOIN signs s ON e.sign_id = s.id
        LEFT JOIN categories c ON e.category_id = c.id
        LEFT JOIN articles a ON e.article_id = a.id
        LEFT JOIN projects p ON e.project_id = p.id
        LEFT JOIN counterparties cp ON e.counterparty_id = cp.id
        LEFT JOIN wallet_types wt ON e.wallet_type_id = wt.id
        LEFT JOIN wallets w ON e.wallet_id = w.id
        WHERE e.id = %s
    ''', (expense_id,))
    expense = cur.fetchone()
    
    if not expense:
        flash('Запись не найдена', 'danger')
        return redirect(url_for('index'))
    
    # Check permissions
    if session['role'] != 'admin' and expense['user_id'] != session['user_id']:
        flash('У вас нет прав на редактирование этой записи', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        
        if not is_period_editable(date) and session['role'] != 'admin':
            flash('Этот период закрыт для редактирования', 'danger')
            return redirect(url_for('index'))
        
        try:
            cur.execute('''
                UPDATE expenses SET
                    date = %s, year = %s, month = %s,
                    sign_id = %s, category_id = %s, article_id = %s,
                    project_id = %s, counterparty_id = %s,
                    wallet_type_id = %s, wallet_id = %s,
                    amount = %s, comments = %s, pl = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (
                date, date.year, date.month,
                request.form['sign_id'] or None,
                request.form['category_id'] or None,
                request.form['article_id'] or None,
                request.form['project_id'] or None,
                request.form['counterparty_id'] or None,
                request.form['wallet_type_id'] or None,
                request.form['wallet_id'] or None,
                request.form['amount'],
                request.form['comments'],
                request.form['pl'],
                expense_id
            ))
            conn.commit()
            flash('Запись успешно обновлена', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при обновлении: {str(e)}', 'danger')
        
        return redirect(url_for('index'))
    
    # GET request - show edit form
    cur.execute("SELECT * FROM signs ORDER BY name")
    signs = cur.fetchall()
    
    cur.execute("SELECT * FROM categories ORDER BY name")
    categories = cur.fetchall()
    
    cur.execute("SELECT * FROM articles ORDER BY name")
    articles = cur.fetchall()
    
    cur.execute("SELECT * FROM projects ORDER BY name")
    projects = cur.fetchall()
    
    cur.execute("SELECT * FROM counterparties ORDER BY name")
    counterparties = cur.fetchall()
    
    cur.execute("SELECT * FROM wallet_types ORDER BY name")
    wallet_types = cur.fetchall()
    
    cur.execute("SELECT * FROM wallets ORDER BY name")
    wallets = cur.fetchall()
    
    cur.close()
    conn.close()
    
    expense['date'] = expense['date'].strftime('%Y-%m-%d')
    
    return render_template('edit_expense.html',
                         expense=expense, signs=signs,
                         categories=categories, articles=articles,
                         projects=projects, counterparties=counterparties,
                         wallet_types=wallet_types, wallets=wallets)

@app.route('/delete/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    conn = get_db()
    cur = conn.cursor()
    
    # Get expense data to check permissions
    cur.execute("SELECT user_id, date FROM expenses WHERE id = %s", (expense_id,))
    expense = cur.fetchone()
    
    if not expense:
        flash('Запись не найдена', 'danger')
        return redirect(url_for('index'))
    
    # Check permissions
    if session['role'] != 'admin' and expense['user_id'] != session['user_id']:
        flash('У вас нет прав на удаление этой записи', 'danger')
        return redirect(url_for('index'))
    
    if session['role'] != 'admin' and not is_period_editable(expense['date']):
        flash('Этот период закрыт для редактирования', 'danger')
        return redirect(url_for('index'))
    
    try:
        cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        conn.commit()
        flash('Запись успешно удалена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('index'))

# ==================== УПРАВЛЕНИЕ СПРАВОЧНИКАМИ ====================

@app.route('/admin/references')
@admin_required
def manage_references():
    """Главная страница управления справочниками"""
    return render_template('manage_references.html')

# ---- Управление признаками (signs) ----
@app.route('/admin/references/signs')
@admin_required
def manage_signs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.*, COUNT(c.id) as categories_count 
        FROM signs s 
        LEFT JOIN categories c ON s.id = c.sign_id 
        GROUP BY s.id 
        ORDER BY s.name
    ''')
    signs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_signs.html', signs=signs)

@app.route('/admin/references/signs/add', methods=['POST'])
@admin_required
def add_sign():
    name = request.form['name']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO signs (name) VALUES (%s)", (name,))
        conn.commit()
        flash('Признак успешно добавлен', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Признак с таким именем уже существует', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_signs'))

@app.route('/admin/references/signs/delete/<int:sign_id>')
@admin_required
def delete_sign(sign_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли признак
        cur.execute("SELECT COUNT(*) FROM expenses WHERE sign_id = %s", (sign_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить признак, который используется в записях', 'danger')
            return redirect(url_for('manage_signs'))
        
        cur.execute("DELETE FROM signs WHERE id = %s", (sign_id,))
        conn.commit()
        flash('Признак успешно удален', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_signs'))

# ---- Управление категориями ----
@app.route('/admin/references/categories')
@admin_required
def manage_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT c.*, s.name as sign_name, COUNT(a.id) as articles_count 
        FROM categories c 
        JOIN signs s ON c.sign_id = s.id 
        LEFT JOIN articles a ON c.id = a.category_id 
        GROUP BY c.id, s.name 
        ORDER BY s.name, c.name
    ''')
    categories = cur.fetchall()
    
    cur.execute("SELECT * FROM signs ORDER BY name")
    signs = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('manage_categories.html', categories=categories, signs=signs)

@app.route('/admin/references/categories/add', methods=['POST'])
@admin_required
def add_category():
    name = request.form['name']
    sign_id = request.form['sign_id']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO categories (name, sign_id) VALUES (%s, %s)",
            (name, sign_id)
        )
        conn.commit()
        flash('Категория успешно добавлена', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Категория с таким именем уже существует для данного признака', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_categories'))

@app.route('/admin/references/categories/delete/<int:category_id>')
@admin_required
def delete_category(category_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли категория
        cur.execute("SELECT COUNT(*) FROM expenses WHERE category_id = %s", (category_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить категорию, которая используется в записях', 'danger')
            return redirect(url_for('manage_categories'))
        
        cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        conn.commit()
        flash('Категория успешно удалена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_categories'))

# ---- Управление статьями ----
@app.route('/admin/references/articles')
@admin_required
def manage_articles():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT a.*, c.name as category_name, s.name as sign_name,
               COUNT(e.id) as expenses_count 
        FROM articles a 
        JOIN categories c ON a.category_id = c.id 
        JOIN signs s ON c.sign_id = s.id 
        LEFT JOIN expenses e ON a.id = e.article_id 
        GROUP BY a.id, c.name, s.name 
        ORDER BY s.name, c.name, a.name
    ''')
    articles = cur.fetchall()
    
    cur.execute('''
        SELECT c.*, s.name as sign_name 
        FROM categories c 
        JOIN signs s ON c.sign_id = s.id 
        ORDER BY s.name, c.name
    ''')
    categories = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('manage_articles.html', articles=articles, categories=categories)

@app.route('/admin/references/articles/add', methods=['POST'])
@admin_required
def add_article():
    name = request.form['name']
    category_id = request.form['category_id']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO articles (name, category_id) VALUES (%s, %s)",
            (name, category_id)
        )
        conn.commit()
        flash('Статья успешно добавлена', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Статья с таким именем уже существует для данной категории', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_articles'))

@app.route('/admin/references/articles/delete/<int:article_id>')
@admin_required
def delete_article(article_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли статья
        cur.execute("SELECT COUNT(*) FROM expenses WHERE article_id = %s", (article_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить статью, которая используется в записях', 'danger')
            return redirect(url_for('manage_articles'))
        
        cur.execute("DELETE FROM articles WHERE id = %s", (article_id,))
        conn.commit()
        flash('Статья успешно удалена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_articles'))

# ---- Управление проектами ----
@app.route('/admin/references/projects')
@admin_required
def manage_projects():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.*, COUNT(e.id) as expenses_count 
        FROM projects p 
        LEFT JOIN expenses e ON p.id = e.project_id 
        GROUP BY p.id 
        ORDER BY p.name
    ''')
    projects = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_projects.html', projects=projects)

@app.route('/admin/references/projects/add', methods=['POST'])
@admin_required
def add_project():
    name = request.form['name']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO projects (name) VALUES (%s)", (name,))
        conn.commit()
        flash('Проект успешно добавлен', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Проект с таким именем уже существует', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_projects'))

@app.route('/admin/references/projects/delete/<int:project_id>')
@admin_required
def delete_project(project_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли проект
        cur.execute("SELECT COUNT(*) FROM expenses WHERE project_id = %s", (project_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить проект, который используется в записях', 'danger')
            return redirect(url_for('manage_projects'))
        
        cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        conn.commit()
        flash('Проект успешно удален', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_projects'))

# ---- Управление контрагентами ----
@app.route('/admin/references/counterparties')
@admin_required
def manage_counterparties():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT c.*, COUNT(e.id) as expenses_count 
        FROM counterparties c 
        LEFT JOIN expenses e ON c.id = e.counterparty_id 
        GROUP BY c.id 
        ORDER BY c.name
    ''')
    counterparties = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_counterparties.html', counterparties=counterparties)

@app.route('/admin/references/counterparties/add', methods=['POST'])
@admin_required
def add_counterparty():
    name = request.form['name']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO counterparties (name) VALUES (%s)", (name,))
        conn.commit()
        flash('Контрагент успешно добавлен', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Контрагент с таким именем уже существует', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_counterparties'))

@app.route('/admin/references/counterparties/delete/<int:counterparty_id>')
@admin_required
def delete_counterparty(counterparty_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли контрагент
        cur.execute("SELECT COUNT(*) FROM expenses WHERE counterparty_id = %s", (counterparty_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить контрагента, который используется в записях', 'danger')
            return redirect(url_for('manage_counterparties'))
        
        cur.execute("DELETE FROM counterparties WHERE id = %s", (counterparty_id,))
        conn.commit()
        flash('Контрагент успешно удален', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_counterparties'))

# ---- Управление типами кошельков ----
@app.route('/admin/references/wallet_types')
@admin_required
def manage_wallet_types():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT wt.*, COUNT(w.id) as wallets_count 
        FROM wallet_types wt 
        LEFT JOIN wallets w ON wt.id = w.wallet_type_id 
        GROUP BY wt.id 
        ORDER BY wt.name
    ''')
    wallet_types = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('manage_wallet_types.html', wallet_types=wallet_types)

@app.route('/admin/references/wallet_types/add', methods=['POST'])
@admin_required
def add_wallet_type():
    name = request.form['name']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO wallet_types (name) VALUES (%s)", (name,))
        conn.commit()
        flash('Тип кошелька успешно добавлен', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Тип кошелька с таким именем уже существует', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_wallet_types'))

@app.route('/admin/references/wallet_types/delete/<int:wallet_type_id>')
@admin_required
def delete_wallet_type(wallet_type_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли тип кошелька
        cur.execute("SELECT COUNT(*) FROM expenses WHERE wallet_type_id = %s", (wallet_type_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить тип кошелька, который используется в записях', 'danger')
            return redirect(url_for('manage_wallet_types'))
        
        cur.execute("DELETE FROM wallet_types WHERE id = %s", (wallet_type_id,))
        conn.commit()
        flash('Тип кошелька успешно удален', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_wallet_types'))

# ---- Управление кошельками ----
@app.route('/admin/references/wallets')
@admin_required
def manage_wallets():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT w.*, wt.name as wallet_type_name, COUNT(e.id) as expenses_count 
        FROM wallets w 
        JOIN wallet_types wt ON w.wallet_type_id = wt.id 
        LEFT JOIN expenses e ON w.id = e.wallet_id 
        GROUP BY w.id, wt.name 
        ORDER BY wt.name, w.name
    ''')
    wallets = cur.fetchall()
    
    cur.execute("SELECT * FROM wallet_types ORDER BY name")
    wallet_types = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('manage_wallets.html', wallets=wallets, wallet_types=wallet_types)

@app.route('/admin/references/wallets/add', methods=['POST'])
@admin_required
def add_wallet():
    name = request.form['name']
    wallet_type_id = request.form['wallet_type_id']
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO wallets (name, wallet_type_id) VALUES (%s, %s)",
            (name, wallet_type_id)
        )
        conn.commit()
        flash('Кошелек успешно добавлен', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Кошелек с таким именем уже существует для данного типа', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_wallets'))

@app.route('/admin/references/wallets/delete/<int:wallet_id>')
@admin_required
def delete_wallet(wallet_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # Проверяем, используется ли кошелек
        cur.execute("SELECT COUNT(*) FROM expenses WHERE wallet_id = %s", (wallet_id,))
        if cur.fetchone()['count'] > 0:
            flash('Нельзя удалить кошелек, который используется в записях', 'danger')
            return redirect(url_for('manage_wallets'))
        
        cur.execute("DELETE FROM wallets WHERE id = %s", (wallet_id,))
        conn.commit()
        flash('Кошелек успешно удален', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_wallets'))

# ==================== ИМПОРТ ИЗ EXCEL ====================

@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_expenses():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
            flash('Пожалуйста, загрузите файл Excel (.xlsx, .xls) или CSV', 'danger')
            return redirect(request.url)
        
        try:
            # Читаем файл
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Проверяем наличие колонки sign, если нет - определяем по сумме
            if 'sign' not in df.columns:
                df['sign'] = df['amount'].apply(lambda x: 'IN' if float(x) >= 0 else 'OUT')
                flash('Колонка "sign" не найдена. Признак определен автоматически по сумме (IN для положительных, OUT для отрицательных)', 'info')
            
            # Ожидаемые колонки
            expected_columns = ['date', 'amount', 'sign', 'category', 'article', 
                               'project', 'counterparty', 'wallet_type', 'wallet', 
                               'comments', 'pl']
            
            # Проверяем наличие необходимых колонок
            required_columns = ['date', 'amount']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                flash(f'В файле отсутствуют обязательные колонки: {", ".join(missing_columns)}', 'danger')
                return redirect(request.url)
            
            conn = get_db()
            cur = conn.cursor()
            
            # Получаем все справочники для маппинга
            cur.execute("SELECT id, name FROM signs")
            signs = {row['name']: row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT c.id, c.name, s.name as sign_name FROM categories c JOIN signs s ON c.sign_id = s.id")
            categories = {(row['name'], row['sign_name']): row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT a.id, a.name, c.name as category_name FROM articles a JOIN categories c ON a.category_id = c.id")
            articles = {(row['name'], row['category_name']): row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT id, name FROM projects")
            projects = {row['name']: row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT id, name FROM counterparties")
            counterparties = {row['name']: row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT id, name FROM wallet_types")
            wallet_types = {row['name']: row['id'] for row in cur.fetchall()}
            
            cur.execute("SELECT w.id, w.name, wt.name as wallet_type_name FROM wallets w JOIN wallet_types wt ON w.wallet_type_id = wt.id")
            wallets = {(row['name'], row['wallet_type_name']): row['id'] for row in cur.fetchall()}
            
            successful = 0
            failed = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Парсим дату
                    if isinstance(row['date'], str):
                        date = datetime.strptime(row['date'], '%Y-%m-%d')
                    else:
                        date = pd.to_datetime(row['date']).to_pydatetime()
                    
                    # Проверяем, открыт ли период
                    if not is_period_editable(date) and session['role'] != 'admin':
                        failed += 1
                        errors.append(f"Строка {index + 2}: Период {date.year}-{date.month:02d} закрыт")
                        continue
                    
                    # Получаем ID справочников
                    sign_id = None
                    if 'sign' in row and pd.notna(row['sign']):
                        sign_id = signs.get(row['sign'])
                    
                    category_id = None
                    if 'category' in row and pd.notna(row['category']) and sign_id:
                        sign_name = next((s for s, id in signs.items() if id == sign_id), None)
                        if sign_name:
                            category_id = categories.get((row['category'], sign_name))
                    
                    article_id = None
                    if 'article' in row and pd.notna(row['article']) and category_id:
                        category_name = next((c for (c, s), id in categories.items() if id == category_id), None)
                        if category_name:
                            article_id = articles.get((row['article'], category_name))
                    
                    project_id = None
                    if 'project' in row and pd.notna(row['project']):
                        project_id = projects.get(row['project'])
                    
                    counterparty_id = None
                    if 'counterparty' in row and pd.notna(row['counterparty']):
                        counterparty_id = counterparties.get(row['counterparty'])
                    
                    wallet_type_id = None
                    if 'wallet_type' in row and pd.notna(row['wallet_type']):
                        wallet_type_id = wallet_types.get(row['wallet_type'])
                    
                    wallet_id = None
                    if 'wallet' in row and pd.notna(row['wallet']) and wallet_type_id:
                        wallet_type_name = next((wt for wt, id in wallet_types.items() if id == wallet_type_id), None)
                        if wallet_type_name:
                            wallet_id = wallets.get((row['wallet'], wallet_type_name))
                    
                    # Вставляем запись
                    cur.execute('''
                        INSERT INTO expenses (
                            date, year, month, sign_id, category_id, article_id,
                            project_id, counterparty_id, wallet_type_id, wallet_id,
                            amount, comments, pl, user_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        date, date.year, date.month,
                        sign_id,
                        category_id,
                        article_id,
                        project_id,
                        counterparty_id,
                        wallet_type_id,
                        wallet_id,
                        row['amount'],
                        row.get('comments', '') if pd.notna(row.get('comments', '')) else '',
                        row.get('pl', '') if pd.notna(row.get('pl', '')) else '',
                        session['user_id']
                    ))
                    
                    successful += 1
                    
                except Exception as e:
                    failed += 1
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            conn.commit()
            
            if successful > 0:
                flash(f'Успешно импортировано: {successful} записей', 'success')
            if failed > 0:
                flash(f'Ошибок при импорте: {failed}. Подробности в консоли', 'warning')
                for error in errors[:5]:  # Показываем первые 5 ошибок
                    print(error)
            
            cur.close()
            conn.close()
            
        except Exception as e:
            flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
            print(f"Import error: {e}")
        
        return redirect(url_for('index'))
    
    return render_template('import.html')

# ==================== ЭКСПОРТ СПРАВОЧНИКОВ ====================

@app.route('/admin/references/export/<string:ref_type>')
@admin_required
def export_reference(ref_type):
    """Экспорт справочника в Excel"""
    conn = get_db()
    cur = conn.cursor()
    
    # Определяем данные для экспорта в зависимости от типа справочника
    if ref_type == 'signs':
        cur.execute('''
            SELECT s.id, s.name as "Признак",
                   COUNT(c.id) as "Количество категорий"
            FROM signs s
            LEFT JOIN categories c ON s.id = c.sign_id
            GROUP BY s.id
            ORDER BY s.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"priznaki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'categories':
        cur.execute('''
            SELECT c.id, c.name as "Категория",
                   s.name as "Признак",
                   COUNT(a.id) as "Количество статей"
            FROM categories c
            JOIN signs s ON c.sign_id = s.id
            LEFT JOIN articles a ON c.id = a.category_id
            GROUP BY c.id, s.name
            ORDER BY s.name, c.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"kategorii_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'articles':
        cur.execute('''
            SELECT a.id, a.name as "Статья",
                   c.name as "Категория",
                   s.name as "Признак",
                   COUNT(e.id) as "Использований"
            FROM articles a
            JOIN categories c ON a.category_id = c.id
            JOIN signs s ON c.sign_id = s.id
            LEFT JOIN expenses e ON a.id = e.article_id
            GROUP BY a.id, c.name, s.name
            ORDER BY s.name, c.name, a.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"stati_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'projects':
        cur.execute('''
            SELECT p.id, p.name as "Проект",
                   COUNT(e.id) as "Использований"
            FROM projects p
            LEFT JOIN expenses e ON p.id = e.project_id
            GROUP BY p.id
            ORDER BY p.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"proekty_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'counterparties':
        cur.execute('''
            SELECT c.id, c.name as "Контрагент",
                   COUNT(e.id) as "Использований"
            FROM counterparties c
            LEFT JOIN expenses e ON c.id = e.counterparty_id
            GROUP BY c.id
            ORDER BY c.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"kontragenty_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'wallet_types':
        cur.execute('''
            SELECT wt.id, wt.name as "Тип кошелька",
                   COUNT(w.id) as "Количество кошельков"
            FROM wallet_types wt
            LEFT JOIN wallets w ON wt.id = w.wallet_type_id
            GROUP BY wt.id
            ORDER BY wt.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"tipy_koshelkov_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
    elif ref_type == 'wallets':
        cur.execute('''
            SELECT w.id, w.name as "Кошелек",
                   wt.name as "Тип кошелька",
                   COUNT(e.id) as "Использований"
            FROM wallets w
            JOIN wallet_types wt ON w.wallet_type_id = wt.id
            LEFT JOIN expenses e ON w.id = e.wallet_id
            GROUP BY w.id, wt.name
            ORDER BY wt.name, w.name
        ''')
        data = cur.fetchall()
        df = pd.DataFrame(data)
        filename = f"koshelki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    else:
        flash('Неизвестный тип справочника', 'danger')
        return redirect(url_for('manage_references'))
    
    cur.close()
    conn.close()
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        tmp_path = tmp.name
    
    # Отправляем файл
    return send_file(
        tmp_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ==================== ИМПОРТ СПРАВОЧНИКОВ ====================

@app.route('/admin/references/import/<string:ref_type>', methods=['POST'])
@admin_required
def import_reference(ref_type):
    """Импорт справочника из Excel"""
    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer or url_for('manage_references'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer or url_for('manage_references'))
    
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        flash('Пожалуйста, загрузите файл Excel (.xlsx, .xls)', 'danger')
        return redirect(request.referrer or url_for('manage_references'))
    
    try:
        # Читаем файл
        df = pd.read_excel(file)
        
        conn = get_db()
        cur = conn.cursor()
        
        successful = 0
        errors = []
        
        if ref_type == 'signs':
            # Ожидаемые колонки: Признак
            if 'Признак' not in df.columns:
                flash('В файле отсутствует колонка "Признак"', 'danger')
                return redirect(request.referrer)
            
            for index, row in df.iterrows():
                try:
                    name = row['Признак']
                    cur.execute(
                        "INSERT INTO signs (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (name,)
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано признаков: {successful}', 'success')
            
        elif ref_type == 'categories':
            # Ожидаемые колонки: Категория, Признак
            if 'Категория' not in df.columns or 'Признак' not in df.columns:
                flash('В файле отсутствуют необходимые колонки ("Категория", "Признак")', 'danger')
                return redirect(request.referrer)
            
            # Получаем словарь признаков
            cur.execute("SELECT id, name FROM signs")
            signs = {row['name']: row['id'] for row in cur.fetchall()}
            
            for index, row in df.iterrows():
                try:
                    name = row['Категория']
                    sign_name = row['Признак']
                    
                    if sign_name not in signs:
                        errors.append(f"Строка {index + 2}: Признак '{sign_name}' не найден")
                        continue
                    
                    cur.execute(
                        "INSERT INTO categories (name, sign_id) VALUES (%s, %s) ON CONFLICT (name, sign_id) DO NOTHING",
                        (name, signs[sign_name])
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано категорий: {successful}', 'success')
            
        elif ref_type == 'articles':
            # Ожидаемые колонки: Статья, Категория, Признак
            if 'Статья' not in df.columns or 'Категория' not in df.columns or 'Признак' not in df.columns:
                flash('В файле отсутствуют необходимые колонки ("Статья", "Категория", "Признак")', 'danger')
                return redirect(request.referrer)
            
            # Получаем соответствия категорий
            cur.execute("""
                SELECT c.id, c.name, s.name as sign_name 
                FROM categories c
                JOIN signs s ON c.sign_id = s.id
            """)
            categories = {(row['name'], row['sign_name']): row['id'] for row in cur.fetchall()}
            
            for index, row in df.iterrows():
                try:
                    name = row['Статья']
                    category_name = row['Категория']
                    sign_name = row['Признак']
                    
                    category_key = (category_name, sign_name)
                    if category_key not in categories:
                        errors.append(f"Строка {index + 2}: Категория '{category_name}' с признаком '{sign_name}' не найдена")
                        continue
                    
                    cur.execute(
                        "INSERT INTO articles (name, category_id) VALUES (%s, %s) ON CONFLICT (name, category_id) DO NOTHING",
                        (name, categories[category_key])
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано статей: {successful}', 'success')
            
        elif ref_type == 'projects':
            # Ожидаемые колонки: Проект
            if 'Проект' not in df.columns:
                flash('В файле отсутствует колонка "Проект"', 'danger')
                return redirect(request.referrer)
            
            for index, row in df.iterrows():
                try:
                    name = row['Проект']
                    cur.execute(
                        "INSERT INTO projects (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (name,)
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано проектов: {successful}', 'success')
            
        elif ref_type == 'counterparties':
            # Ожидаемые колонки: Контрагент
            if 'Контрагент' not in df.columns:
                flash('В файле отсутствует колонка "Контрагент"', 'danger')
                return redirect(request.referrer)
            
            for index, row in df.iterrows():
                try:
                    name = row['Контрагент']
                    cur.execute(
                        "INSERT INTO counterparties (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (name,)
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано контрагентов: {successful}', 'success')
            
        elif ref_type == 'wallet_types':
            # Ожидаемые колонки: Тип кошелька
            if 'Тип кошелька' not in df.columns:
                flash('В файле отсутствует колонка "Тип кошелька"', 'danger')
                return redirect(request.referrer)
            
            for index, row in df.iterrows():
                try:
                    name = row['Тип кошелька']
                    cur.execute(
                        "INSERT INTO wallet_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (name,)
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано типов кошельков: {successful}', 'success')
            
        elif ref_type == 'wallets':
            # Ожидаемые колонки: Кошелек, Тип кошелька
            if 'Кошелек' not in df.columns or 'Тип кошелька' not in df.columns:
                flash('В файле отсутствуют необходимые колонки ("Кошелек", "Тип кошелька")', 'danger')
                return redirect(request.referrer)
            
            # Получаем словарь типов кошельков
            cur.execute("SELECT id, name FROM wallet_types")
            wallet_types = {row['name']: row['id'] for row in cur.fetchall()}
            
            for index, row in df.iterrows():
                try:
                    name = row['Кошелек']
                    wallet_type_name = row['Тип кошелька']
                    
                    if wallet_type_name not in wallet_types:
                        errors.append(f"Строка {index + 2}: Тип кошелька '{wallet_type_name}' не найден")
                        continue
                    
                    cur.execute(
                        "INSERT INTO wallets (name, wallet_type_id) VALUES (%s, %s) ON CONFLICT (name, wallet_type_id) DO NOTHING",
                        (name, wallet_types[wallet_type_name])
                    )
                    if cur.rowcount > 0:
                        successful += 1
                except Exception as e:
                    errors.append(f"Строка {index + 2}: {str(e)}")
            
            flash(f'Успешно импортировано кошельков: {successful}', 'success')
        
        else:
            flash('Неизвестный тип справочника', 'danger')
            return redirect(url_for('manage_references'))
        
        conn.commit()
        
        if errors:
            for error in errors[:5]:
                flash(error, 'warning')
                print(error)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
        print(f"Import reference error: {e}")
    
    return redirect(request.referrer or url_for('manage_references'))

@app.route('/download_template')
@login_required
def download_template():
    """Скачать шаблон Excel для импорта"""
    import tempfile
    import os
    
    # Создаем DataFrame с примером данных
    data = {
        'date': ['2024-01-15', '2024-01-16'],
        'amount': [1000.50, -500.25],
        'sign': ['IN', 'OUT'],
        'category': ['Доходы', 'Расходы'],
        'article': ['Зарплата', 'Продукты'],
        'project': ['Основной', 'Личный'],
        'counterparty': ['Клиент 1', 'Магазин'],
        'wallet_type': ['Банковская карта', 'Наличные'],
        'wallet': ['Основная карта', 'Кошелек'],
        'comments': ['Зарплата за январь', 'Покупка продуктов'],
        'pl': ['PL1', 'PL2']
    }
    
    df = pd.DataFrame(data)
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        tmp_path = tmp.name
    
    # Читаем файл для отправки
    with open(tmp_path, 'rb') as f:
        content = f.read()
    
    # Удаляем временный файл
    os.unlink(tmp_path)
    
    # Отправляем файл
    response = app.response_class(
        content,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment;filename=import_template.xlsx'}
    )
    return response

@app.route('/admin/periods')
@admin_required
def manage_periods():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT p.*, u.username as closed_by_username
        FROM periods p
        LEFT JOIN users u ON p.closed_by_user_id = u.id
        ORDER BY p.year DESC, p.month DESC
    ''')
    periods = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('manage_periods.html', periods=periods)

@app.route('/admin/period/toggle/<int:year>/<int:month>')
@admin_required
def toggle_period(year, month):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT is_closed FROM periods WHERE year = %s AND month = %s",
        (year, month)
    )
    period = cur.fetchone()
    
    if period:
        new_status = not period['is_closed']
        cur.execute(
            "UPDATE periods SET is_closed = %s, closed_by_user_id = %s, closed_at = CURRENT_TIMESTAMP WHERE year = %s AND month = %s",
            (new_status, session['user_id'] if new_status else None, year, month)
        )
    else:
        cur.execute(
            "INSERT INTO periods (year, month, is_closed, closed_by_user_id, closed_at) VALUES (%s, %s, %s, %s, %s)",
            (year, month, True, session['user_id'], datetime.now())
        )
    
    conn.commit()
    cur.close()
    conn.close()
    
    status = "закрыт" if new_status else "открыт"
    flash(f'Период {year}-{month:02d} {status}', 'success')
    return redirect(url_for('manage_periods'))

@app.route('/admin/users')
@admin_required
def manage_users():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('manage_users.html', users=users)

@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == 'POST':
        role = request.form['role']
        cur.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
        conn.commit()
        flash('Роль пользователя обновлена', 'success')
        return redirect(url_for('manage_users'))
    
    cur.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/user/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('manage_users'))
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM expenses WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash('Пользователь и его записи удалены', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('manage_users'))

@app.route('/get_categories/<int:sign_id>')
def get_categories(sign_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories WHERE sign_id = %s ORDER BY name", (sign_id,))
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return {'categories': categories}

@app.route('/get_articles/<int:category_id>')
def get_articles(category_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM articles WHERE category_id = %s ORDER BY name", (category_id,))
    articles = cur.fetchall()
    cur.close()
    conn.close()
    return {'articles': articles}

@app.route('/get_wallets/<int:wallet_type_id>')
def get_wallets(wallet_type_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM wallets WHERE wallet_type_id = %s ORDER BY name", (wallet_type_id,))
    wallets = cur.fetchall()
    cur.close()
    conn.close()
    return {'wallets': wallets}

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Смена пароля пользователя"""
    if request.method == 'POST':
        current_password = hashlib.sha256(request.form['current_password'].encode()).hexdigest()
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Проверяем, что новый пароль и подтверждение совпадают
        if new_password != confirm_password:
            flash('Новый пароль и подтверждение не совпадают', 'danger')
            return redirect(url_for('change_password'))
        
        # Проверяем минимальную длину пароля
        if len(new_password) < 6:
            flash('Пароль должен содержать не менее 6 символов', 'danger')
            return redirect(url_for('change_password'))
        
        conn = get_db()
        cur = conn.cursor()
        
        # Проверяем текущий пароль
        cur.execute(
            "SELECT * FROM users WHERE id = %s AND password_hash = %s",
            (session['user_id'], current_password)
        )
        user = cur.fetchone()
        
        if not user:
            flash('Текущий пароль указан неверно', 'danger')
            cur.close()
            conn.close()
            return redirect(url_for('change_password'))
        
        # Обновляем пароль
        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_password_hash, session['user_id'])
        )
        conn.commit()
        
        cur.close()
        conn.close()
        
        flash('Пароль успешно изменен', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html')

@app.route('/admin/reset_password', methods=['POST'])
@admin_required
def reset_password():
    """Сброс пароля пользователя администратором"""
    user_id = request.form['user_id']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password != confirm_password:
        flash('Пароли не совпадают', 'danger')
        return redirect(url_for('manage_users'))
    
    if len(new_password) < 6:
        flash('Пароль должен содержать не менее 6 символов', 'danger')
        return redirect(url_for('manage_users'))
    
    conn = get_db()
    cur = conn.cursor()
    
    new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
    cur.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (new_password_hash, user_id)
    )
    conn.commit()
    
    cur.close()
    conn.close()
    
    flash('Пароль пользователя успешно сброшен', 'success')
    return redirect(url_for('manage_users'))

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}, 500

if __name__ == '__main__':
    print("Запуск приложения...")
    print("Параметры подключения к БД:")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Database: {DB_CONFIG['dbname']}")
    print(f"User: {DB_CONFIG['user']}")
    print(f"Password: {'***' if DB_CONFIG['password'] else 'НЕ ЗАДАН!'}")
    
    try:
        init_db()
        debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
        app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("Проверьте:")
        print("1. Наличие файла .env в корневой директории")
        print("2. Правильность пароля в .env файле")
        print("3. Доступность хоста PostgreSQL")