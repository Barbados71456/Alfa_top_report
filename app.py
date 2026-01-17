from flask import Flask, render_template, jsonify, request, session
from flask_login import LoginManager, login_required, current_user
from flask_caching import Cache
from config import Config
from database import db
from models import User, FinancialData
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, extract, case, and_, or_, text
from sqlalchemy.sql import label
import json
import traceback
import hashlib
from functools import wraps
import time
import psutil
import gc

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Инициализация кэша
cache = Cache(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth_bp, url_prefix='/auth')

# ====== ДЕКОРАТОРЫ ДЛЯ ОПТИМИЗАЦИИ ======

def cache_json_response(timeout=60):
    """Декоратор для кэширования JSON ответов"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Генерируем ключ кэша на основе аргументов
            cache_key_parts = [
                f.__name__,
                str(request.args.to_dict()),
                str(request.get_json(silent=True) or {})
            ]
            cache_key = hashlib.md5(json.dumps(cache_key_parts, sort_keys=True).encode()).hexdigest()
            
            # Пытаемся получить из кэша
            cached = cache.get(cache_key)
            if cached is not None:
                return jsonify(cached)
            
            # Выполняем функцию
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {f.__name__}: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
            
            execution_time = time.time() - start_time
            
            # Логируем медленные запросы
            if execution_time > 2.0:
                logger.warning(f"Slow endpoint {f.__name__}: {execution_time:.2f}s")
            
            # Кэшируем результат если успешно
            if isinstance(result, tuple):
                response, status = result
                if status == 200 and response.json.get('success'):
                    cache.set(cache_key, response.json, timeout=timeout)
                return response
            else:
                if result.json.get('success'):
                    cache.set(cache_key, result.json, timeout=timeout)
                return result
        return decorated_function
    return decorator

def paginate_response(default_per_page=50, max_per_page=100):
    """Декоратор для пагинации"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                page = request.args.get('page', 1, type=int)
                per_page = min(request.args.get('per_page', default_per_page, type=int), max_per_page)
                
                # Добавляем параметры пагинации в kwargs
                kwargs['page'] = page
                kwargs['per_page'] = per_page
            except:
                kwargs['page'] = 1
                kwargs['per_page'] = default_per_page
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ====== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ДАННЫХ ======

def get_aggregated_data(projects, distributions, months, year_min, year_max):
    """Получает агрегированные данные за оба года за один запрос"""
    try:
        # Базовый запрос
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_min, FinancialData.Сумма)],
                    else_=0
                )
            ).label('min_year_sum'),
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_max, FinancialData.Сумма)],
                    else_=0
                )
            ).label('max_year_sum')
        ).filter(
            FinancialData.Период.isnot(None),
            extract('year', FinancialData.Период).in_([year_min, year_max]),
            extract('month', FinancialData.Период).in_(months)
        )
        
        if projects:
            query = query.filter(FinancialData.Проект.in_(projects))
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        
        result = query.group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2
        ).all()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_aggregated_data: {str(e)}")
        return []

def calculate_indicators_from_aggregated(aggregated_data):
    """Рассчитывает показатели из агрегированных данных"""
    result = {
        'net_cash_flow': {'min_year': 0, 'max_year': 0},
        'od_result': {'min_year': 0, 'max_year': 0},
        'od_income': {'min_year': 0, 'max_year': 0},
        'od_expense': {'min_year': 0, 'max_year': 0},
        'variables': {'min_year': 0, 'max_year': 0},
        'constants': {'min_year': 0, 'max_year': 0},
        'id_result': {'min_year': 0, 'max_year': 0},
        'fin_result': {'min_year': 0, 'max_year': 0}
    }
    
    if not aggregated_data:
        return result
    
    for row in aggregated_data:
        level1 = row.СтатьяУровень1
        level2 = row.СтатьяУровень2
        min_sum = row.min_year_sum or 0
        max_sum = row.max_year_sum or 0
        
        # Чистый денежный поток (все статьи)
        result['net_cash_flow']['min_year'] += min_sum
        result['net_cash_flow']['max_year'] += max_sum
        
        # ОД операции
        if level1 == 'Поступления по ОД':
            result['od_income']['min_year'] += min_sum
            result['od_income']['max_year'] += max_sum
            result['od_result']['min_year'] += min_sum
            result['od_result']['max_year'] += max_sum
        elif level1 == 'Отток по ОД':
            result['od_expense']['min_year'] += min_sum
            result['od_expense']['max_year'] += max_sum
            result['od_result']['min_year'] -= min_sum  # Отрицательное влияние
            result['od_result']['max_year'] -= max_sum
            
            if level2 == 'Отток по ОД (переменные)':
                result['variables']['min_year'] += min_sum
                result['variables']['max_year'] += max_sum
            elif level2 == 'Отток по ОД (постоянные)':
                result['constants']['min_year'] += min_sum
                result['constants']['max_year'] += max_sum
        elif level1 == 'Результат по ИД':
            result['id_result']['min_year'] += min_sum
            result['id_result']['max_year'] += max_sum
        elif level1 == 'Финансы':
            result['fin_result']['min_year'] += min_sum
            result['fin_result']['max_year'] += max_sum
    
    return result

def get_hierarchy_data_optimized(projects, distributions, months, year_min, year_max, config=None):
    """Оптимизированная версия получения иерархии"""
    try:
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            extract('year', FinancialData.Период).label('year'),
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Период.isnot(None),
            extract('year', FinancialData.Период).in_([year_min, year_max]),
            extract('month', FinancialData.Период).in_(months)
        )
        
        if projects:
            query = query.filter(FinancialData.Проект.in_(projects))
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        
        if config:
            if 'СтатьяУровень1' in config:
                if isinstance(config['СтатьяУровень1'], list):
                    query = query.filter(FinancialData.СтатьяУровень1.in_(config['СтатьяУровень1']))
                else:
                    query = query.filter(FinancialData.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                query = query.filter(FinancialData.СтатьяУровень2 == config['СтатьяУровень2'])
        
        # Ограничиваем количество записей для производительности
        results = query.group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            extract('year', FinancialData.Период)
        ).limit(1000).all()
        
        # Структурируем данные
        hierarchy = {}
        for row in results:
            key = f"{row.СтатьяУровень1 or ''}|{row.СтатьяУровень2 or ''}|{row.СтатьяУровень3 or ''}|{row.СтатьяУровень4 or ''}"
            if key not in hierarchy:
                hierarchy[key] = {
                    'level1': row.СтатьяУровень1,
                    'level2': row.СтатьяУровень2,
                    'level3': row.СтатьяУровень3,
                    'level4': row.СтатьяУровень4,
                    'min_year': 0,
                    'max_year': 0
                }
            
            if row.year == year_min:
                hierarchy[key]['min_year'] += row.total or 0
            elif row.year == year_max:
                hierarchy[key]['max_year'] += row.total or 0
        
        return list(hierarchy.values())
        
    except Exception as e:
        logger.error(f"Error in get_hierarchy_data_optimized: {str(e)}")
        return []

# ====== ОСНОВНЫЕ ЭНДПОИНТЫ ======

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/report1')
@login_required
def report1():
    return render_template('report1.html')

@app.route('/report2')
@login_required
def report2():
    return render_template('report2.html')

@app.route('/report3')
@login_required
def report3():
    return render_template('report3.html')

@app.route('/report4')
@login_required
def report4():
    return render_template('report4.html')

# ====== API ДЛЯ ОТЧЕТА 1 ======

@app.route('/api/report1/filters-data')
@login_required
@cache_json_response(timeout=600)
def get_filters_data():
    """Возвращает данные для инициализации фильтров"""
    try:
        # Годы
        years_query = db.session.query(
            extract('year', FinancialData.Период).label('year')
        ).filter(
            FinancialData.Период.isnot(None)
        ).distinct().order_by('year')
        
        years_result = years_query.all()
        year_list = sorted([int(y[0]) for y in years_result if y[0]])
        
        # Проекты с ограничением
        projects_query = db.session.query(
            FinancialData.Проект
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
        ).distinct().order_by(FinancialData.Проект).limit(200)
        
        projects = [p[0] for p in projects_query if p[0]]
        
        # Распределения
        distributions_query = db.session.query(
            FinancialData.Распределение
        ).filter(
            FinancialData.Распределение.isnot(None),
            FinancialData.Распределение != ''
        ).distinct().order_by(FinancialData.Распределение).limit(100)
        
        dist_list = [d[0] for d in distributions_query if d[0]]
        
        return jsonify({
            'success': True,
            'years': year_list,
            'projects': projects,
            'distributions': dist_list
        })
        
    except Exception as e:
        logger.error(f"Error in filters data: {str(e)}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки фильтров'}), 500

@app.route('/api/report1/aggregated', methods=['POST'])
@login_required
@cache_json_response(timeout=120)
def get_aggregated_table():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        # Валидация
        if not months:
            return jsonify({'success': False, 'error': 'Не выбраны месяцы'}), 400
        
        if not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Не выбран период'}), 400
        
        # Ограничиваем количество проектов для производительности
        if len(projects) > 100:
            projects = projects[:100]
            logger.warning("Too many projects selected, limiting to 100")
        
        # Получаем агрегированные данные
        aggregated_data = get_aggregated_data(projects, distributions, months, year_min, year_max)
        
        # Рассчитываем показатели
        result = calculate_indicators_from_aggregated(aggregated_data)
        
        return jsonify({
            'success': True,
            'data': result,
            'year_min': year_min,
            'year_max': year_max
        })
        
    except Exception as e:
        logger.error(f"Error in aggregated table: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report1/hierarchy', methods=['POST'])
@login_required
@cache_json_response(timeout=60)
def get_hierarchy_details():
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        if not projects:
            projects = []
        
        # Определяем какие статьи включать в иерархию
        indicator_config = {
            'od_income': {'СтатьяУровень1': 'Поступления по ОД'},
            'od_expense': {'СтатьяУровень1': 'Отток по ОД'},
            'variables': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (переменные)'},
            'constants': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (постоянные)'},
            'id_result': {'СтатьяУровень1': 'Результат по ИД'},
            'fin_result': {'СтатьяУровень1': 'Финансы'},
            'net_cash_flow': {},  # Все статьи
            'od_result': {'СтатьяУровень1': ['Поступления по ОД', 'Отток по ОД']}
        }
        
        config = indicator_config.get(indicator_key, {})
        
        # Получаем данные за оба года
        hierarchy_data = get_hierarchy_data_optimized(projects, distributions, months, year_min, year_max, config)
        
        # Строим иерархию
        hierarchy = build_hierarchy_from_data(hierarchy_data)
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy[:50]  # Ограничиваем 50 элементами
        })
        
    except Exception as e:
        logger.error(f"Error in hierarchy details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report1/factor-analysis', methods=['POST'])
@login_required
@paginate_response(default_per_page=20, max_per_page=50)
def get_factor_analysis(page=1, per_page=20):
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        if not projects:
            projects = []
        
        # Определяем какие статьи анализировать
        indicator_config = {
            'od_income': {'СтатьяУровень1': 'Поступления по ОД'},
            'od_expense': {'СтатьяУровень1': 'Отток по ОД'},
            'variables': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (переменные)'},
            'constants': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (постоянные)'},
            'id_result': {'СтатьяУровень1': 'Результат по ИД'},
            'fin_result': {'СтатьяУровень1': 'Финансы'},
            'net_cash_flow': {},  # Все статьи уровня 4
            'od_result': {'СтатьяУровень1': ['Поступления по ОД', 'Отток по ОД']}
        }
        
        config = indicator_config.get(indicator_key, {})
        
        # Оптимизированный запрос для факторного анализа
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_min, FinancialData.Сумма)],
                    else_=0
                )
            ).label('min_year'),
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_max, FinancialData.Сумма)],
                    else_=0
                )
            ).label('max_year')
        ).filter(
            FinancialData.Период.isnot(None),
            extract('year', FinancialData.Период).in_([year_min, year_max]),
            extract('month', FinancialData.Период).in_(months)
        )
        
        if projects:
            query = query.filter(FinancialData.Проект.in_(projects))
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        if config:
            if 'СтатьяУровень1' in config:
                if isinstance(config['СтатьяУровень1'], list):
                    query = query.filter(FinancialData.СтатьяУровень1.in_(config['СтатьяУровень1']))
                else:
                    query = query.filter(FinancialData.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                query = query.filter(FinancialData.СтатьяУровень2 == config['СтатьяУровень2'])
        
        query = query.group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4
        )
        
        # Получаем общее количество
        count_query = query.subquery()
        total = db.session.query(func.count('*')).select_from(count_query).scalar()
        
        # Применяем пагинацию
        paginated_results = query.limit(per_page).offset((page - 1) * per_page).all()
        
        # Форматируем результаты
        factors = []
        for row in paginated_results:
            min_year = row.min_year or 0
            max_year = row.max_year or 0
            deviation = max_year - min_year
            
            factors.append({
                'level1': row.СтатьяУровень1 or 'Не указано',
                'level2': row.СтатьяУровень2 or 'Не указано',
                'level3': row.СтатьяУровень3 or 'Не указано',
                'level4': row.СтатьяУровень4 or 'Не указано',
                'min_year': min_year,
                'max_year': max_year,
                'deviation': deviation
            })
        
        # Сортируем по абсолютному значению отклонения
        factors.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        # Рассчитываем проценты для топ-факторов
        if factors:
            total_deviation = sum(abs(f['deviation']) for f in factors)
            if total_deviation > 0:
                for factor in factors:
                    factor['percentage'] = round((abs(factor['deviation']) / total_deviation * 100), 2)
        
        return jsonify({
            'success': True,
            'factors': factors,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if per_page > 0 else 0
            }
        })
        
    except Exception as e:
        logger.error(f"Error in factor analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== API ДЛЯ ОТЧЕТА 2 (ИТОГО) ======

@app.route('/api/report2/filters-data')
@login_required
@cache_json_response(timeout=600)
def get_report2_filters_data():
    """Оптимизированная версия без проектов"""
    try:
        # Годы
        years_query = db.session.query(
            extract('year', FinancialData.Период).label('year')
        ).filter(
            FinancialData.Период.isnot(None)
        ).distinct().order_by('year')
        
        years_result = years_query.all()
        year_list = sorted([int(y[0]) for y in years_result if y[0]])
        
        # Распределения
        distributions_query = db.session.query(
            FinancialData.Распределение
        ).filter(
            FinancialData.Распределение.isnot(None),
            FinancialData.Распределение != ''
        ).distinct().order_by(FinancialData.Распределение).limit(100)
        
        dist_list = [d[0] for d in distributions_query if d[0]]
        
        return jsonify({
            'success': True,
            'years': year_list,
            'distributions': dist_list
        })
        
    except Exception as e:
        logger.error(f"Error in report2 filters data: {str(e)}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки фильтров'}), 500

@app.route('/api/report2/aggregated', methods=['POST'])
@login_required
@cache_json_response(timeout=120)
def get_report2_aggregated_table():
    try:
        data = request.get_json()
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not months:
            return jsonify({'success': False, 'error': 'Не выбраны месяцы'}), 400
        
        if not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Не выбран период'}), 400
        
        # Используем оптимизированную функцию без фильтра по проектам
        aggregated_data = get_aggregated_data([], distributions, months, year_min, year_max)
        result = calculate_indicators_from_aggregated(aggregated_data)
        
        return jsonify({
            'success': True,
            'data': result,
            'year_min': year_min,
            'year_max': year_max
        })
        
    except Exception as e:
        logger.error(f"Error in report2 aggregated table: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report2/hierarchy', methods=['POST'])
@login_required
@cache_json_response(timeout=60)
def get_report2_hierarchy_details():
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Определяем какие статьи включать в иерархию
        indicator_config = {
            'od_income': {'СтатьяУровень1': 'Поступления по ОД'},
            'od_expense': {'СтатьяУровень1': 'Отток по ОД'},
            'variables': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (переменные)'},
            'constants': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (постоянные)'},
            'id_result': {'СтатьяУровень1': 'Результат по ИД'},
            'fin_result': {'СтатьяУровень1': 'Финансы'},
            'net_cash_flow': {},  # Все статьи
            'od_result': {'СтатьяУровень1': ['Поступления по ОД', 'Отток по ОД']}
        }
        
        config = indicator_config.get(indicator_key, {})
        
        # Получаем данные за оба года (все проекты)
        hierarchy_data = get_hierarchy_data_optimized([], distributions, months, year_min, year_max, config)
        
        # Строим иерархию
        hierarchy = build_hierarchy_from_data(hierarchy_data)
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy[:50]  # Ограничиваем 50 элементами
        })
        
    except Exception as e:
        logger.error(f"Error in report2 hierarchy details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== API ДЛЯ ОТЧЕТА 3 (АНАЛИЗ ПО ПРОЕКТАМ) ======

@app.route('/api/report3/filters-data')
@login_required
@cache_json_response(timeout=600)
def get_report3_filters_data():
    """Возвращает данные для инициализации фильтров"""
    try:
        # Годы
        years_query = db.session.query(
            extract('year', FinancialData.Период).label('year')
        ).filter(
            FinancialData.Период.isnot(None)
        ).distinct().order_by('year')
        
        years_result = years_query.all()
        year_list = sorted([int(y[0]) for y in years_result if y[0]])
        
        # Распределения
        distributions_query = db.session.query(
            FinancialData.Распределение
        ).filter(
            FinancialData.Распределение.isnot(None),
            FinancialData.Распределение != ''
        ).distinct().order_by(FinancialData.Распределение).limit(100)
        
        dist_list = [d[0] for d in distributions_query if d[0]]
        
        # Показатели для выбора
        indicators = [
            {'key': 'net_cash_flow', 'name': 'Чистый денежный поток'},
            {'key': 'od_result', 'name': 'Результат ОД'},
            {'key': 'od_income', 'name': 'Поступления по ОД'},
            {'key': 'od_expense', 'name': 'Отток по ОД'},
            {'key': 'variables', 'name': 'Переменные расходы'},
            {'key': 'constants', 'name': 'Постоянные расходы'},
            {'key': 'id_result', 'name': 'Результат по ИД'},
            {'key': 'fin_result', 'name': 'Результат фин'}
        ]
        
        return jsonify({
            'success': True,
            'years': year_list,
            'distributions': dist_list,
            'indicators': indicators
        })
        
    except Exception as e:
        logger.error(f"Error in report3 filters data: {str(e)}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки фильтров'}), 500

@app.route('/api/report3/projects-data', methods=['POST'])
@login_required
@paginate_response(default_per_page=50, max_per_page=100)
def get_report3_projects_data(page=1, per_page=50):
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not indicator_key or not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Оптимизированный запрос для получения данных по проектам
        query = db.session.query(
            FinancialData.Проект,
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_min, FinancialData.Сумма)],
                    else_=0
                )
            ).label('min_year'),
            func.sum(
                case(
                    [(extract('year', FinancialData.Период) == year_max, FinancialData.Сумма)],
                    else_=0
                )
            ).label('max_year')
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != '',
            extract('year', FinancialData.Период).in_([year_min, year_max]),
            extract('month', FinancialData.Период).in_(months)
        )
        
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        
        # Фильтр по статье в зависимости от показателя
        indicator_config = {
            'od_income': {'СтатьяУровень1': 'Поступления по ОД'},
            'od_expense': {'СтатьяУровень1': 'Отток по ОД'},
            'variables': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (переменные)'},
            'constants': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (постоянные)'},
            'id_result': {'СтатьяУровень1': 'Результат по ИД'},
            'fin_result': {'СтатьяУровень1': 'Финансы'},
            'net_cash_flow': {},  # Все статьи
            'od_result': {'СтатьяУровень1': ['Поступления по ОД', 'Отток по ОД']}
        }
        
        config = indicator_config.get(indicator_key, {})
        if config:
            if 'СтатьяУровень1' in config:
                if isinstance(config['СтатьяУровень1'], list):
                    query = query.filter(FinancialData.СтатьяУровень1.in_(config['СтатьяУровень1']))
                else:
                    query = query.filter(FinancialData.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                query = query.filter(FinancialData.СтатьяУровень2 == config['СтатьяУровень2'])
        
        query = query.group_by(FinancialData.Проект)
        
        # Получаем общее количество
        count_query = query.subquery()
        total = db.session.query(func.count('*')).select_from(count_query).scalar()
        
        # Применяем пагинацию
        paginated_results = query.limit(per_page).offset((page - 1) * per_page).all()
        
        # Данные для результата
        projects_data = []
        for row in paginated_results:
            min_value = row.min_year or 0
            max_value = row.max_year or 0
            deviation = max_value - min_value
            
            projects_data.append({
                'project': row.Проект,
                'min_year': min_value,
                'max_year': max_value,
                'deviation': deviation
            })
        
        # Сортируем по отклонению (по модулю)
        projects_data.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        return jsonify({
            'success': True,
            'projects_data': projects_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if per_page > 0 else 0
            },
            'year_min': year_min,
            'year_max': year_max,
            'indicator_key': indicator_key
        })
        
    except Exception as e:
        logger.error(f"Error in report3 projects data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======

def build_hierarchy_from_data(data):
    """Строит иерархию из данных"""
    if not data:
        return []
    
    # Создаем структуру дерева
    tree = {}
    
    for item in data:
        level1 = item['level1'] or 'Не указано'
        level2 = item['level2'] or 'Не указано'
        level3 = item['level3'] or 'Не указано'
        level4 = item['level4'] or 'Не указано'
        
        if level1 not in tree:
            tree[level1] = {
                'name': level1,
                'min_year': 0,
                'max_year': 0,
                'deviation': 0,
                'children': {}
            }
        
        if level2 not in tree[level1]['children']:
            tree[level1]['children'][level2] = {
                'name': level2,
                'min_year': 0,
                'max_year': 0,
                'deviation': 0,
                'children': {}
            }
        
        if level3 not in tree[level1]['children'][level2]['children']:
            tree[level1]['children'][level2]['children'][level3] = {
                'name': level3,
                'min_year': 0,
                'max_year': 0,
                'deviation': 0,
                'children': []
            }
        
        # Добавляем данные
        tree[level1]['min_year'] += item['min_year']
        tree[level1]['max_year'] += item['max_year']
        tree[level1]['deviation'] = tree[level1]['max_year'] - tree[level1]['min_year']
        
        tree[level1]['children'][level2]['min_year'] += item['min_year']
        tree[level1]['children'][level2]['max_year'] += item['max_year']
        tree[level1]['children'][level2]['deviation'] = tree[level1]['children'][level2]['max_year'] - tree[level1]['children'][level2]['min_year']
        
        tree[level1]['children'][level2]['children'][level3]['min_year'] += item['min_year']
        tree[level1]['children'][level2]['children'][level3]['max_year'] += item['max_year']
        tree[level1]['children'][level2]['children'][level3]['deviation'] = tree[level1]['children'][level2]['children'][level3]['max_year'] - tree[level1]['children'][level2]['children'][level3]['min_year']
        
        # Добавляем уровень 4
        level4_item = {
            'name': level4,
            'min_year': item['min_year'],
            'max_year': item['max_year'],
            'deviation': item['max_year'] - item['min_year']
        }
        
        # Проверяем, нет ли уже такой записи
        existing = next((x for x in tree[level1]['children'][level2]['children'][level3]['children'] 
                        if x['name'] == level4), None)
        if existing:
            existing['min_year'] += item['min_year']
            existing['max_year'] += item['max_year']
            existing['deviation'] = existing['max_year'] - existing['min_year']
        else:
            tree[level1]['children'][level2]['children'][level3]['children'].append(level4_item)
    
    # Преобразуем в формат для фронтенда
    hierarchy = []
    for level1_name, level1_data in tree.items():
        level1_node = {
            'name': level1_name,
            'min_year': level1_data['min_year'],
            'max_year': level1_data['max_year'],
            'deviation': level1_data['deviation'],
            'children': []
        }
        
        for level2_name, level2_data in level1_data['children'].items():
            level2_node = {
                'name': level2_name,
                'min_year': level2_data['min_year'],
                'max_year': level2_data['max_year'],
                'deviation': level2_data['deviation'],
                'children': []
            }
            
            for level3_name, level3_data in level2_data['children'].items():
                level3_node = {
                    'name': level3_name,
                    'min_year': level3_data['min_year'],
                    'max_year': level3_data['max_year'],
                    'deviation': level3_data['deviation'],
                    'children': level3_data['children'][:20]  # Ограничиваем 20 элементами
                }
                
                level2_node['children'].append(level3_node)
            
            level1_node['children'].append(level2_node)
        
        hierarchy.append(level1_node)
    
    return hierarchy

# ====== МОНИТОРИНГ И ДИАГНОСТИКА ======

@app.route('/api/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Проверяем соединение с БД
        db.session.execute(text('SELECT 1'))
        
        # Информация о памяти
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'memory_mb': memory_info.rss / 1024 / 1024,
            'cpu_percent': process.cpu_percent(interval=0.1),
            'active_threads': len(process.threads()),
            'cache_stats': 'available' if cache else 'not_available'
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/api/debug/performance')
@login_required
def debug_performance():
    """Информация о производительности (только для админов)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Недостаточно прав'}), 403
    
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Информация о GC
        gc.collect()
        
        return jsonify({
            'memory_usage_mb': round(memory_info.rss / 1024 / 1024, 2),
            'memory_percent': process.memory_percent(),
            'cpu_percent': process.cpu_percent(),
            'threads': len(process.threads()),
            'open_files': len(process.open_files()),
            'gc_stats': gc.get_stats(),
            'db_pool_status': str(db.engine.pool.status())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/clear-cache')
@login_required
def clear_cache():
    """Очистка кэша (только для админов)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Недостаточно прав'}), 403
    
    try:
        cache.clear()
        return jsonify({'success': True, 'message': 'Кэш очищен'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ====== СТАРЫЕ API (для совместимости) ======

@app.route('/api/debug/data')
def debug_data():
    try:
        stats = db.session.query(
            FinancialData.СтатьяУровень1,
            func.count('*').label('count'),
            func.sum(FinancialData.Сумма).label('total')
        ).group_by(FinancialData.СтатьяУровень1).limit(10).all()
        
        samples = db.session.query(
            FinancialData.Проект,
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4,
            FinancialData.Сумма,
            FinancialData.Период
        ).limit(5).all()
        
        return jsonify({
            'success': True,
            'stats': [
                {
                    'level1': s.СтатьяУровень1,
                    'count': s.count,
                    'total': s.total
                }
                for s in stats
            ],
            'samples': [
                {
                    'project': sm.Проект,
                    'level1': sm.СтатьяУровень1,
                    'level2': sm.СтатьяУровень2,
                    'level4': sm.СтатьяУровень4,
                    'amount': sm.Сумма,
                    'period': sm.Период.strftime('%Y-%m-%d') if sm.Период else None
                }
                for sm in samples
            ]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report4/data')
@login_required
def get_report4_data():
    try:
        return jsonify({'success': True, 'message': 'Report 4 data endpoint'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ИНИЦИАЛИЗАЦИЯ ======

with app.app_context():
    try:
        db.create_all()
        init_admin()
        logger.info('✅ Приложение инициализировано')
    except Exception as e:
        logger.error(f'❌ Ошибка инициализации: {e}')
        traceback.print_exc()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)