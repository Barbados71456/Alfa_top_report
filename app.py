from flask import Flask, render_template, jsonify, request, session
from flask_login import LoginManager, login_required, current_user
from config import Config
from database import db
from models import User, FinancialData
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, case, and_, extract
from sqlalchemy.sql import label
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth_bp, url_prefix='/auth')

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

# ====== НОВЫЕ API ДЛЯ ОТЧЕТА 1 ======

# API: Список распределений
@app.route('/api/distribution')
@login_required
def get_distribution():
    try:
        distributions = db.session.query(
            FinancialData.Распределение
        ).filter(
            FinancialData.Распределение.isnot(None),
            FinancialData.Распределение != ''
        ).distinct().order_by(FinancialData.Распределение).all()
        
        dist_list = [d[0] for d in distributions if d[0]]
        
        return jsonify(dist_list)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Список проектов
@app.route('/api/projects')
@login_required
def get_projects():
    try:
        projects_query = db.session.query(
            FinancialData.Проект
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
        ).distinct().order_by(FinancialData.Проект).all()
        
        projects = [p[0] for p in projects_query if p[0]]
        
        return jsonify(projects)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Данные для фильтров
@app.route('/api/report1/filters-data')
@login_required
def get_filters_data():
    """Возвращает данные для инициализации фильтров"""
    try:
        # Годы
        years = db.session.query(
            extract('year', FinancialData.Период).label('year')
        ).filter(
            FinancialData.Период.isnot(None)
        ).distinct().order_by('year').all()
        
        year_list = [int(y[0]) for y in years if y[0]]
        
        # Проекты
        projects_query = db.session.query(
            FinancialData.Проект
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
        ).distinct().order_by(FinancialData.Проект).all()
        
        projects = [p[0] for p in projects_query if p[0]]
        
        # Распределения
        distributions = db.session.query(
            FinancialData.Распределение
        ).filter(
            FinancialData.Распределение.isnot(None),
            FinancialData.Распределение != ''
        ).distinct().order_by(FinancialData.Распределение).all()
        
        dist_list = [d[0] for d in distributions if d[0]]
        
        # Месяцы (1-12)
        months = list(range(1, 13))
        
        return jsonify({
            'success': True,
            'years': year_list,
            'projects': projects,
            'distributions': dist_list,
            'months': months
        })
        
    except Exception as e:
        logger.error(f"Error in filters data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Агрегированная таблица эффективности
@app.route('/api/report1/aggregated', methods=['POST'])
@login_required
def get_aggregated_table():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects:
            return jsonify({'success': False, 'error': 'Не выбраны проекты'}), 400
        
        if not months:
            return jsonify({'success': False, 'error': 'Не выбраны месяцы'}), 400
        
        if not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Не выбран период'}), 400
        
        # Получаем данные за минимальный год
        data_min_year = get_year_data(projects, distributions, months, year_min)
        # Получаем данные за максимальный год
        data_max_year = get_year_data(projects, distributions, months, year_max)
        
        # Рассчитываем показатели
        result = {
            'net_cash_flow': {
                'min_year': calculate_total(data_min_year),
                'max_year': calculate_total(data_max_year)
            },
            'od_result': {
                'min_year': calculate_od_result(data_min_year),
                'max_year': calculate_od_result(data_max_year)
            },
            'od_income': {
                'min_year': calculate_od_income(data_min_year),
                'max_year': calculate_od_income(data_max_year)
            },
            'od_expense': {
                'min_year': calculate_od_expense(data_min_year),
                'max_year': calculate_od_expense(data_max_year)
            },
            'variables': {
                'min_year': calculate_variables(data_min_year),
                'max_year': calculate_variables(data_max_year)
            },
            'constants': {
                'min_year': calculate_constants(data_min_year),
                'max_year': calculate_constants(data_max_year)
            },
            'id_result': {
                'min_year': calculate_id_result(data_min_year),
                'max_year': calculate_id_result(data_max_year)
            },
            'fin_result': {
                'min_year': calculate_fin_result(data_min_year),
                'max_year': calculate_fin_result(data_max_year)
            }
        }
        
        return jsonify({
            'success': True,
            'data': result,
            'year_min': year_min,
            'year_max': year_max
        })
        
    except Exception as e:
        logger.error(f"Error in aggregated table: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Детализация иерархии
@app.route('/api/report1/hierarchy', methods=['POST'])
@login_required
def get_hierarchy_details():
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects or not months or not year_min or not year_max:
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
        
        # Получаем данные за оба года
        data_min_year = get_year_data_for_hierarchy(projects, distributions, months, year_min, config)
        data_max_year = get_year_data_for_hierarchy(projects, distributions, months, year_max, config)
        
        # Строим иерархию
        hierarchy = build_hierarchy_with_years(data_min_year, data_max_year, year_min, year_max)
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy
        })
        
    except Exception as e:
        logger.error(f"Error in hierarchy details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Факторный анализ
@app.route('/api/report1/factor-analysis', methods=['POST'])
@login_required
def get_factor_analysis():
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects or not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
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
        
        # Получаем данные за оба года
        data_min_year = get_year_data_for_hierarchy(projects, distributions, months, year_min, config)
        data_max_year = get_year_data_for_hierarchy(projects, distributions, months, year_max, config)
        
        # Анализируем статьи уровня 4
        factors = analyze_level4_factors(data_min_year, data_max_year)
        
        return jsonify({
            'success': True,
            'factors': factors[:20]  # Ограничиваем 20 самыми значимыми
        })
        
    except Exception as e:
        logger.error(f"Error in factor analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Анализ по контрагентам
@app.route('/api/report1/contragent-analysis', methods=['POST'])
@login_required
def get_contragent_analysis():
    try:
        data = request.get_json()
        level1 = data.get('level1')
        level2 = data.get('level2')
        level3 = data.get('level3')
        level4 = data.get('level4')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects or not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Получаем контрагентов за оба года
        contragents_min = get_contragent_data(projects, distributions, months, year_min, level1, level2, level3, level4)
        contragents_max = get_contragent_data(projects, distributions, months, year_max, level1, level2, level3, level4)
        
        # Объединяем и считаем отклонения
        contragents = calculate_contragent_deviations(contragents_min, contragents_max)
        
        return jsonify({
            'success': True,
            'contragents': contragents[:50]  # Ограничиваем 50 контрагентами
        })
        
    except Exception as e:
        logger.error(f"Error in contragent analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======

def get_year_data(projects, distributions, months, year):
    """Получает данные за конкретный год с преобразованием отклонения"""
    query = db.session.query(
        FinancialData.СтатьяУровень1,
        FinancialData.СтатьяУровень2,
        FinancialData.СтатьяУровень3,
        FinancialData.СтатьяУровень4,
        FinancialData.Сумма,
        case(
            (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
            else_=-FinancialData.Сумма
        ).label('отклонение')
    ).filter(
        FinancialData.Период.isnot(None),
        FinancialData.Проект.in_(projects),
        extract('year', FinancialData.Период) == year,
        extract('month', FinancialData.Период).in_(months)
    )
    
    if distributions:
        query = query.filter(FinancialData.Распределение.in_(distributions))
    
    return query.all()

def get_year_data_for_hierarchy(projects, distributions, months, year, config):
    """Получает данные за конкретный год для иерархии"""
    query = db.session.query(
        FinancialData.СтатьяУровень1,
        FinancialData.СтатьяУровень2,
        FinancialData.СтатьяУровень3,
        FinancialData.СтатьяУровень4,
        case(
            (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
            else_=-FinancialData.Сумма
        ).label('отклонение')
    ).filter(
        FinancialData.Период.isnot(None),
        FinancialData.Проект.in_(projects),
        extract('year', FinancialData.Период) == year,
        extract('month', FinancialData.Период).in_(months)
    )
    
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
    
    return query.all()

def calculate_total(rows):
    """Сумма всех отклонений (с учетом знаков)"""
    return sum(row.отклонение or 0 for row in rows)

def calculate_od_result(rows):
    """Расчет результата ОД = Поступления по ОД + Отток по ОД (с учетом знаков)"""
    od_income = sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Поступления по ОД')
    od_expense = sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Отток по ОД')
    return od_income + od_expense  # od_expense уже с минусом в отклонении

def calculate_od_income(rows):
    """Расчет поступлений по ОД"""
    return sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Поступления по ОД')

def calculate_od_expense(rows):
    """Расчет оттока по ОД (отрицательное число)"""
    return sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Отток по ОД')

def calculate_variables(rows):
    """Расчет переменных расходов"""
    return sum(row.отклонение or 0 for row in rows 
               if row.СтатьяУровень1 == 'Отток по ОД' 
               and row.СтатьяУровень2 == 'Отток по ОД (переменные)')

def calculate_constants(rows):
    """Расчет постоянных расходов"""
    return sum(row.отклонение or 0 for row in rows 
               if row.СтатьяУровень1 == 'Отток по ОД' 
               and row.СтатьяУровень2 == 'Отток по ОД (постоянные)')

def calculate_id_result(rows):
    """Расчет результата по ИД"""
    return sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Результат по ИД')

def calculate_fin_result(rows):
    """Расчет результата финансов"""
    return sum(row.отклонение or 0 for row in rows if row.СтатьяУровень1 == 'Финансы')

def build_hierarchy_with_years(rows_min, rows_max, year_min, year_max):
    """Строит иерархию с данными за оба года"""
    # Объединяем все уникальные записи
    all_data = {}
    
    # Добавляем данные за минимальный год
    for row in rows_min:
        key = f"{row.СтатьяУровень1 or ''}|{row.СтатьяУровень2 or ''}|{row.СтатьяУровень3 or ''}|{row.СтатьяУровень4 or ''}"
        if key not in all_data:
            all_data[key] = {
                'level1': row.СтатьяУровень1,
                'level2': row.СтатьяУровень2,
                'level3': row.СтатьяУровень3,
                'level4': row.СтатьяУровень4,
                'min_year': 0,
                'max_year': 0
            }
        all_data[key]['min_year'] += row.отклонение or 0
    
    # Добавляем данные за максимальный год
    for row in rows_max:
        key = f"{row.СтатьяУровень1 or ''}|{row.СтатьяУровень2 or ''}|{row.СтатьяУровень3 or ''}|{row.СтатьяУровень4 or ''}"
        if key not in all_data:
            all_data[key] = {
                'level1': row.СтатьяУровень1,
                'level2': row.СтатьяУровень2,
                'level3': row.СтатьяУровень3,
                'level4': row.СтатьяУровень4,
                'min_year': 0,
                'max_year': 0
            }
        all_data[key]['max_year'] += row.отклонение or 0
    
    # Строим дерево
    hierarchy = []
    
    # Группируем по level1
    level1_groups = {}
    for item in all_data.values():
        level1 = item['level1'] or 'Не указано'
        if level1 not in level1_groups:
            level1_groups[level1] = []
        level1_groups[level1].append(item)
    
    for level1_name, level1_items in level1_groups.items():
        level1_total_min = sum(item['min_year'] for item in level1_items)
        level1_total_max = sum(item['max_year'] for item in level1_items)
        
        level1_node = {
            'name': level1_name,
            'min_year': level1_total_min,
            'max_year': level1_total_max,
            'deviation': level1_total_max - level1_total_min,
            'children': []
        }
        
        # Группируем по level2
        level2_groups = {}
        for item in level1_items:
            level2 = item['level2'] or 'Не указано'
            if level2 not in level2_groups:
                level2_groups[level2] = []
            level2_groups[level2].append(item)
        
        for level2_name, level2_items in level2_groups.items():
            level2_total_min = sum(item['min_year'] for item in level2_items)
            level2_total_max = sum(item['max_year'] for item in level2_items)
            
            level2_node = {
                'name': level2_name,
                'min_year': level2_total_min,
                'max_year': level2_total_max,
                'deviation': level2_total_max - level2_total_min,
                'children': []
            }
            
            # Группируем по level3
            level3_groups = {}
            for item in level2_items:
                level3 = item['level3'] or 'Не указано'
                if level3 not in level3_groups:
                    level3_groups[level3] = []
                level3_groups[level3].append(item)
            
            for level3_name, level3_items in level3_groups.items():
                level3_total_min = sum(item['min_year'] for item in level3_items)
                level3_total_max = sum(item['max_year'] for item in level3_items)
                
                level3_node = {
                    'name': level3_name,
                    'min_year': level3_total_min,
                    'max_year': level3_total_max,
                    'deviation': level3_total_max - level3_total_min,
                    'children': []
                }
                
                # Добавляем level4
                for item in level3_items:
                    level4_node = {
                        'name': item['level4'] or 'Не указано',
                        'min_year': item['min_year'],
                        'max_year': item['max_year'],
                        'deviation': item['max_year'] - item['min_year']
                    }
                    level3_node['children'].append(level4_node)
                
                level2_node['children'].append(level3_node)
            
            level1_node['children'].append(level2_node)
        
        hierarchy.append(level1_node)
    
    return hierarchy

def analyze_level4_factors(rows_min, rows_max):
    """Анализирует факторы на уровне 4 статей"""
    all_data = {}
    
    # Собираем данные за минимальный год
    for row in rows_min:
        key = f"{row.СтатьяУровень1 or ''}|{row.СтатьяУровень2 or ''}|{row.СтатьяУровень3 or ''}|{row.СтатьяУровень4 or ''}"
        if key not in all_data:
            all_data[key] = {
                'level1': row.СтатьяУровень1,
                'level2': row.СтатьяУровень2,
                'level3': row.СтатьяУровень3,
                'level4': row.СтатьяУровень4,
                'min_year': 0,
                'max_year': 0
            }
        all_data[key]['min_year'] += row.отклонение or 0
    
    # Собираем данные за максимальный год
    for row in rows_max:
        key = f"{row.СтатьяУровень1 or ''}|{row.СтатьяУровень2 or ''}|{row.СтатьяУровень3 or ''}|{row.СтатьяУровень4 or ''}"
        if key not in all_data:
            all_data[key] = {
                'level1': row.СтатьяУровень1,
                'level2': row.СтатьяУровень2,
                'level3': row.СтатьяУровень3,
                'level4': row.СтатьяУровень4,
                'min_year': 0,
                'max_year': 0
            }
        all_data[key]['max_year'] += row.отклонение or 0
    
    # Рассчитываем отклонения
    factors = []
    for item in all_data.values():
        deviation = item['max_year'] - item['min_year']
        if deviation != 0:  # Только ненулевые отклонения
            factors.append({
                'level1': item['level1'] or 'Не указано',
                'level2': item['level2'] or 'Не указано',
                'level3': item['level3'] or 'Не указано',
                'level4': item['level4'] or 'Не указано',
                'min_year': item['min_year'],
                'max_year': item['max_year'],
                'deviation': deviation
            })
    
    # Сортируем по абсолютному значению отклонения
    factors.sort(key=lambda x: abs(x['deviation']), reverse=True)
    
    # Рассчитываем проценты
    total_deviation = sum(abs(f['deviation']) for f in factors)
    for factor in factors:
        factor['percentage'] = round((abs(factor['deviation']) / total_deviation * 100), 2) if total_deviation > 0 else 0
    
    return factors

def get_contragent_data(projects, distributions, months, year, level1=None, level2=None, level3=None, level4=None):
    """Получает данные по контрагентам за конкретный год"""
    query = db.session.query(
        FinancialData.Контрагент,
        case(
            (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
            else_=-FinancialData.Сумма
        ).label('отклонение')
    ).filter(
        FinancialData.Период.isnot(None),
        FinancialData.Проект.in_(projects),
        extract('year', FinancialData.Период) == year,
        extract('month', FinancialData.Период).in_(months)
    )
    
    if distributions:
        query = query.filter(FinancialData.Распределение.in_(distributions))
    
    if level1:
        query = query.filter(FinancialData.СтатьяУровень1 == level1)
    if level2:
        query = query.filter(FinancialData.СтатьяУровень2 == level2)
    if level3:
        query = query.filter(FinancialData.СтатьяУровень3 == level3)
    if level4:
        query = query.filter(FinancialData.СтатьяУровень4 == level4)
    
    results = query.all()
    
    # Группируем по контрагентам
    contragents = {}
    for row in results:
        contragent = row.Контрагент or 'Не указано'
        if contragent not in contragents:
            contragents[contragent] = 0
        contragents[contragent] += row.отклонение or 0
    
    return contragents

def calculate_contragent_deviations(contragents_min, contragents_max):
    """Рассчитывает отклонения по контрагентам"""
    all_contragents = set(list(contragents_min.keys()) + list(contragents_max.keys()))
    
    deviations = []
    for contragent in all_contragents:
        min_value = contragents_min.get(contragent, 0)
        max_value = contragents_max.get(contragent, 0)
        deviation = max_value - min_value
        
        deviations.append({
            'contragent': contragent,
            'min_year': min_value,
            'max_year': max_value,
            'deviation': deviation
        })
    
    # Сортируем по абсолютному значению отклонения
    deviations.sort(key=lambda x: abs(x['deviation']), reverse=True)
    
    # Рассчитываем проценты
    total_deviation = sum(abs(d['deviation']) for d in deviations)
    for d in deviations:
        d['percentage'] = round((abs(d['deviation']) / total_deviation * 100), 2) if total_deviation > 0 else 0
    
    return deviations

# ====== СТАРЫЕ API (для совместимости) ======

@app.route('/api/debug/data')
def debug_data():
    try:
        stats = db.session.query(
            FinancialData.СтатьяУровень1,
            func.count('*').label('count'),
            func.sum(FinancialData.Сумма).label('total')
        ).group_by(FinancialData.СтатьяУровень1).all()
        
        samples = db.session.query(
            FinancialData.Проект,
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4,
            FinancialData.Сумма,
            FinancialData.Период
        ).limit(10).all()
        
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

@app.route('/api/report2/data')
@login_required
def get_report2_data():
    # ... (оставляем старый код)
    pass

@app.route('/api/report3/data')
@login_required
def get_report3_data():
    # ... (оставляем старый код)
    pass

@app.route('/api/report4/data')
@login_required
def get_report4_data():
    # ... (оставляем старый код)
    pass

# ====== ИНИЦИАЛИЗАЦИЯ ======

with app.app_context():
    try:
        db.create_all()
        init_admin()
        print('✅ Приложение инициализировано')
    except Exception as e:
        print(f'❌ Ошибка: {e}')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)