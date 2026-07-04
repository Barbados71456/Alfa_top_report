import hashlib
import logging
from functools import wraps

from flask import session, redirect, url_for, flash, request

from db import query_one, execute
import audit

auth_logger = logging.getLogger('auth')
auth_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('auth.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s - IP: %(client_ip)s - User: %(username)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
auth_logger.addHandler(file_handler)


def _log(username, action, success=True, extra_info=None):
    extra = {'client_ip': request.remote_addr if request else 'N/A', 'username': username}
    message = f"{action} - {'Успешно' if success else 'Неудачно'}"
    if extra_info:
        message += f" - {extra_info}"
    (auth_logger.info if success else auth_logger.warning)(message, extra=extra)


def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Требуется авторизация', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Доступ только ролям из roles. Роли: admin, accountant (бухгалтер),
    shareholder (акционер)."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Недостаточно прав', 'danger')
                return redirect(url_for('svod1'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


admin_required = role_required('admin')
report_required = role_required('admin', 'accountant', 'shareholder')
classifier_required = role_required('admin', 'accountant')


def authenticate_user(username, password):
    user = query_one(
        'SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s',
        (username,)
    )
    if not user:
        _log(username, 'Вход в систему', success=False, extra_info='Пользователь не найден')
        audit.log_action(username, 'login_failed', 'Пользователь не найден')
        return False, None

    if user['is_active'] is False:
        _log(username, 'Вход в систему', success=False, extra_info='Пользователь не активен')
        audit.log_action(username, 'login_failed', 'Пользователь не активен')
        return False, None

    if user['password_hash'] != hash_password(password):
        _log(username, 'Вход в систему', success=False, extra_info='Неверный пароль')
        audit.log_action(username, 'login_failed', 'Неверный пароль')
        return False, None

    _log(username, 'Вход в систему', success=True)
    audit.log_action(username, 'login', 'Успешный вход')
    return True, {'id': user['id'], 'username': user['username'], 'role': user['role']}


def set_password(username, password):
    execute('UPDATE users SET password_hash = %s WHERE username = %s', (hash_password(password), username))
