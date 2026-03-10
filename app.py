import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'dpg-d4im0jh5pdvs73834210-a.oregon-postgres.render.com'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'dbname': os.environ.get('POSTGRES_DB', 'alfa_collection'),
    'user': os.environ.get('POSTGRES_USER', 'alfa_collection_user'),
    'password': os.environ.get('POSTGRES_PASSWORD', '')
}

def get_db():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cur = conn.cursor()
    
    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(200) NOT NULL,
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
            sign_id INTEGER REFERENCES signs(id),
            UNIQUE(name, sign_id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category_id INTEGER REFERENCES categories(id),
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
            wallet_type_id INTEGER REFERENCES wallet_types(id),
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
    if cur.fetchone()['count'] == 0:
        admin_password = hashlib.sha256(os.environ.get('ADMIN_PASSWORD', 'admin123').encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (os.environ.get('ADMIN_USERNAME', 'admin'), admin_password, 'admin')
        )
    
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
        sign_id = cur.fetchone()
        if sign_id:
            cur.execute(
                "INSERT INTO categories (name, sign_id) VALUES (%s, %s) ON CONFLICT (name, sign_id) DO NOTHING",
                (cat_name, sign_id['id'])
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
    cur.close()
    conn.close()
    
    return render_template('index.html', expenses=expenses)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
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
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')",
                (username, password)
            )
            conn.commit()
            flash('Регистрация успешна. Войдите в систему.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Пользователь с таким именем уже существует', 'danger')
        finally:
            cur.close()
            conn.close()
    
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)