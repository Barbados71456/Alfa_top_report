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

# API: Список проектов (обновленный)
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
        
        # Базовый запрос с вашим SQL
        base_query = db.session.query(
            FinancialData.Распределение,
            FinancialData.СтатьяУровень0,
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            FinancialData.Сумма,
            extract('month', FinancialData.Период).label('Месяц'),
            extract('year', FinancialData.Период).label('Год'),
            case(
                (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
                else_=-FinancialData.Сумма
            ).label('отклонение'),
            FinancialData.Проект,
            FinancialData.Контрагент
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.in_(projects)
        )
        
        # Применяем фильтры
        if distributions:
            base_query = base_query.filter(FinancialData.Распределение.in_(distributions))
        
        if months:
            base_query = base_query.filter(extract('month', FinancialData.Период).in_(months))
        
        if year_min and year_max:
            base_query = base_query.filter(
                extract('year', FinancialData.Период).between(year_min, year_max)
            )
        
        # Получаем все данные
        all_data = base_query.all()
        
        # Группируем данные для расчетов
        data_by_year = {}
        for row in all_data:
            year = int(row.Год) if row.Год else None
            if year not in data_by_year:
                data_by_year[year] = []
            data_by_year[year].append(row)
        
        # Рассчитываем показатели
        result = {
            'net_cash_flow': calculate_net_cash_flow(data_by_year, year_min, year_max),
            'od_result': calculate_od_result(data_by_year, year_min, year_max),
            'od_income': calculate_od_income(data_by_year, year_min, year_max),
            'od_expense': calculate_od_expense(data_by_year, year_min, year_max),
            'variables': calculate_variables(data_by_year, year_min, year_max),
            'constants': calculate_constants(data_by_year, year_min, year_max),
            'id_result': calculate_id_result(data_by_year, year_min, year_max),
            'fin_result': calculate_fin_result(data_by_year, year_min, year_max)
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
        
        # Определяем какие статьи включать в иерархию
        indicator_config = {
            'od_income': {'СтатьяУровень1': 'Поступления по ОД'},
            'od_expense': {'СтатьяУровень1': 'Отток по ОД'},
            'variables': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (переменные)'},
            'constants': {'СтатьяУровень1': 'Отток по ОД', 'СтатьяУровень2': 'Отток по ОД (постоянные)'},
            'id_result': {'СтатьяУровень1': 'Результат по ИД'},
            'fin_result': {'СтатьяУровень1': 'Финансы'},
            'net_cash_flow': {},  # Все статьи
            'od_result': {}  # Поступления и Отток по ОД
        }
        
        config = indicator_config.get(indicator_key, {})
        
        base_query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            func.sum(case(
                (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
                else_=-FinancialData.Сумма
            )).label('отклонение')
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.in_(projects)
        )
        
        # Применяем фильтры
        if distributions:
            base_query = base_query.filter(FinancialData.Распределение.in_(distributions))
        
        if months:
            base_query = base_query.filter(extract('month', FinancialData.Период).in_(months))
        
        if year_min and year_max:
            base_query = base_query.filter(
                extract('year', FinancialData.Период).between(year_min, year_max)
            )
        
        # Фильтры по статьям
        if config:
            if 'СтатьяУровень1' in config:
                base_query = base_query.filter(FinancialData.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                base_query = base_query.filter(FinancialData.СтатьяУровень2 == config['СтатьяУровень2'])
        
        # Группируем
        if indicator_key in ['od_income', 'od_expense', 'variables', 'constants', 'id_result', 'fin_result']:
            base_query = base_query.group_by(
                FinancialData.СтатьяУровень1,
                FinancialData.СтатьяУровень2,
                FinancialData.СтатьяУровень3,
                FinancialData.СтатьяУровень4
            )
        elif indicator_key == 'od_result':
            base_query = base_query.filter(
                FinancialData.СтатьяУровень1.in_(['Поступления по ОД', 'Отток по ОД'])
            ).group_by(
                FinancialData.СтатьяУровень1,
                FinancialData.СтатьяУровень2,
                FinancialData.СтатьяУровень3,
                FinancialData.СтатьяУровень4
            )
        else:  # net_cash_flow
            base_query = base_query.group_by(
                FinancialData.СтатьяУровень1,
                FinancialData.СтатьяУровень2,
                FinancialData.СтатьяУровень3,
                FinancialData.СтатьяУровень4
            )
        
        results = base_query.all()
        
        # Формируем иерархию
        hierarchy = build_hierarchy(results, year_min, year_max)
        
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
        
        # Запрос для статей уровня 4
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4,
            func.sum(case(
                (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
                else_=-FinancialData.Сумма
            )).label('отклонение')
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.in_(projects)
        )
        
        # Фильтры
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        
        if months:
            query = query.filter(extract('month', FinancialData.Период).in_(months))
        
        if year_min and year_max:
            query = query.filter(
                extract('year', FinancialData.Период).between(year_min, year_max)
            )
        
        # Фильтры по статьям
        if config:
            if 'СтатьяУровень1' in config:
                if isinstance(config['СтатьяУровень1'], list):
                    query = query.filter(FinancialData.СтатьяУровень1.in_(config['СтатьяУровень1']))
                else:
                    query = query.filter(FinancialData.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                query = query.filter(FinancialData.СтатьяУровень2 == config['СтатьяУровень2'])
        
        # Группируем по уровню 4
        query = query.group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень3,
            FinancialData.СтатьяУровень4
        ).order_by(func.abs(func.sum(case(
            (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
            else_=-FinancialData.Сумма
        ))).desc())
        
        results = query.all()
        
        # Рассчитываем проценты
        total = sum(abs(float(r.отклонение or 0)) for r in results)
        
        factors = []
        for row in results:
            if row.отклонение and float(row.отклонение) != 0:
                deviation = float(row.отклонение)
                percentage = (abs(deviation) / total * 100) if total > 0 else 0
                
                factors.append({
                    'level1': row.СтатьяУровень1 or 'Не указано',
                    'level2': row.СтатьяУровень2 or 'Не указано',
                    'level3': row.СтатьяУровень3 or 'Не указано',
                    'level4': row.СтатьяУровень4 or 'Не указано',
                    'deviation': deviation,
                    'percentage': round(percentage, 2)
                })
        
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
        
        # Запрос для контрагентов
        query = db.session.query(
            FinancialData.Контрагент,
            func.sum(case(
                (extract('year', FinancialData.Период) == 2025, FinancialData.Сумма),
                else_=-FinancialData.Сумма
            )).label('отклонение')
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.in_(projects)
        )
        
        # Фильтры по статьям
        if level1:
            query = query.filter(FinancialData.СтатьяУровень1 == level1)
        if level2:
            query = query.filter(FinancialData.СтатьяУровень2 == level2)
        if level3:
            query = query.filter(FinancialData.СтатьяУровень3 == level3)
        if level4:
            query = query.filter(FinancialData.СтатьяУровень4 == level4)
        
        # Дополнительные фильтры
        if distributions:
            query = query.filter(FinancialData.Распределение.in_(distributions))
        
        if months:
            query = query.filter(extract('month', FinancialData.Период).in_(months))
        
        if year_min and year_max:
            query = query.filter(
                extract('year', FinancialData.Период).between(year_min, year_max)
            )
        
        # Группируем по контрагентам
        query = query.group_by(FinancialData.Контрагент)
        results = query.all()
        
        # Рассчитываем проценты
        contragents = []
        for row in results:
            if row.Контрагент and row.отклонение:
                deviation = float(row.отклонение)
                
                contragents.append({
                    'contragent': row.Контрагент,
                    'deviation': deviation
                })
        
        # Сортируем по абсолютному значению отклонения
        contragents.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        # Рассчитываем проценты
        total = sum(abs(c['deviation']) for c in contragents)
        for c in contragents:
            c['percentage'] = round((abs(c['deviation']) / total * 100), 2) if total > 0 else 0
        
        return jsonify({
            'success': True,
            'contragents': contragents[:50]  # Ограничиваем 50 контрагентами
        })
        
    except Exception as e:
        logger.error(f"Error in contragent analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======

def calculate_net_cash_flow(data_by_year, year_min, year_max):
    """Расчет чистого денежного потока"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        if year == year_min:
            result['min_year'] = sum(row.отклонение or 0 for row in rows)
        elif year == year_max:
            result['max_year'] = sum(row.отклонение or 0 for row in rows)
    
    return result

def calculate_od_result(data_by_year, year_min, year_max):
    """Расчет результата ОД"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        od_income = sum(row.отклонение or 0 for row in rows 
                       if row.СтатьяУровень1 == 'Поступления по ОД')
        od_expense = sum(row.отклонение or 0 for row in rows 
                        if row.СтатьяУровень1 == 'Отток по ОД')
        
        if year == year_min:
            result['min_year'] = od_income - abs(od_expense)
        elif year == year_max:
            result['max_year'] = od_income - abs(od_expense)
    
    return result

def calculate_od_income(data_by_year, year_min, year_max):
    """Расчет поступлений по ОД"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(row.отклонение or 0 for row in rows 
                   if row.СтатьяУровень1 == 'Поступления по ОД')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def calculate_od_expense(data_by_year, year_min, year_max):
    """Расчет оттока по ОД (положительное число)"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(abs(row.отклонение or 0) for row in rows 
                   if row.СтатьяУровень1 == 'Отток по ОД')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def calculate_variables(data_by_year, year_min, year_max):
    """Расчет переменных расходов"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(abs(row.отклонение or 0) for row in rows 
                   if row.СтатьяУровень1 == 'Отток по ОД' 
                   and row.СтатьяУровень2 == 'Отток по ОД (переменные)')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def calculate_constants(data_by_year, year_min, year_max):
    """Расчет постоянных расходов"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(abs(row.отклонение or 0) for row in rows 
                   if row.СтатьяУровень1 == 'Отток по ОД' 
                   and row.СтатьяУровень2 == 'Отток по ОД (постоянные)')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def calculate_id_result(data_by_year, year_min, year_max):
    """Расчет результата по ИД"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(row.отклонение or 0 for row in rows 
                   if row.СтатьяУровень1 == 'Результат по ИД')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def calculate_fin_result(data_by_year, year_min, year_max):
    """Расчет результата финансов"""
    result = {'min_year': 0, 'max_year': 0}
    
    for year, rows in data_by_year.items():
        total = sum(row.отклонение or 0 for row in rows 
                   if row.СтатьяУровень1 == 'Финансы')
        if year == year_min:
            result['min_year'] = total
        elif year == year_max:
            result['max_year'] = total
    
    return result

def build_hierarchy(results, year_min, year_max):
    """Построение иерархии статей"""
    hierarchy = []
    
    # Группируем по уровням
    level1_groups = {}
    for row in results:
        level1 = row.СтатьяУровень1 or 'Не указано'
        if level1 not in level1_groups:
            level1_groups[level1] = []
        level1_groups[level1].append(row)
    
    # Строим дерево
    for level1_name, level1_rows in level1_groups.items():
        level1_item = {
            'name': level1_name,
            'min_year': sum(r.отклонение or 0 for r in level1_rows),
            'max_year': sum(r.отклонение or 0 for r in level1_rows),
            'deviation': 0,
            'children': []
        }
        
        # Группируем по уровню 2
        level2_groups = {}
        for row in level1_rows:
            level2 = row.СтатьяУровень2 or 'Не указано'
            if level2 not in level2_groups:
                level2_groups[level2] = []
            level2_groups[level2].append(row)
        
        for level2_name, level2_rows in level2_groups.items():
            level2_item = {
                'name': level2_name,
                'min_year': sum(r.отклонение or 0 for r in level2_rows),
                'max_year': sum(r.отклонение or 0 for r in level2_rows),
                'deviation': 0,
                'children': []
            }
            
            # Группируем по уровню 3
            level3_groups = {}
            for row in level2_rows:
                level3 = row.СтатьяУровень3 or 'Не указано'
                if level3 not in level3_groups:
                    level3_groups[level3] = []
                level3_groups[level3].append(row)
            
            for level3_name, level3_rows in level3_groups.items():
                level3_item = {
                    'name': level3_name,
                    'min_year': sum(r.отклонение or 0 for r in level3_rows),
                    'max_year': sum(r.отклонение or 0 for r in level3_rows),
                    'deviation': 0,
                    'children': []
                }
                
                # Добавляем уровень 4
                for row in level3_rows:
                    level4_item = {
                        'name': row.СтатьяУровень4 or 'Не указано',
                        'min_year': row.отклонение or 0,
                        'max_year': row.отклонение or 0,
                        'deviation': 0
                    }
                    level3_item['children'].append(level4_item)
                
                level2_item['children'].append(level3_item)
            
            level1_item['children'].append(level2_item)
        
        hierarchy.append(level1_item)
    
    return hierarchy

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