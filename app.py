from flask import Flask, render_template, jsonify, request, session
from flask_login import LoginManager, login_required, current_user
from config import Config
from database import db
from models import User, FinancialData, FinancialDataAggregated, ContragentSummaryView
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, case, and_, extract, text
from sqlalchemy.sql import label
import json
import traceback

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

# ====== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ======

def get_year_data_optimized(projects, distributions, months, year):
    """Оптимизированное получение данных за конкретный год"""
    # Используем агрегированное представление
    query = db.session.query(
        FinancialDataAggregated.СтатьяУровень1,
        FinancialDataAggregated.СтатьяУровень2,
        FinancialDataAggregated.СтатьяУровень3,
        FinancialDataAggregated.СтатьяУровень4,
        FinancialDataAggregated.сумма_итого.label('Сумма'),
        FinancialDataAggregated.Проект,
        FinancialDataAggregated.Контрагент
    ).filter(
        FinancialDataAggregated.год == year,
        FinancialDataAggregated.месяц.in_(months)
    )
    
    if projects:
        query = query.filter(FinancialDataAggregated.Проект.in_(projects))
    
    if distributions:
        query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
    
    return query.all()

def get_year_data_for_hierarchy_optimized(projects, distributions, months, year, config):
    """Оптимизированное получение данных за конкретный год для иерархии"""
    query = db.session.query(
        FinancialDataAggregated.СтатьяУровень1,
        FinancialDataAggregated.СтатьяУровень2,
        FinancialDataAggregated.СтатьяУровень3,
        FinancialDataAggregated.СтатьяУровень4,
        FinancialDataAggregated.сумма_итого.label('Сумма'),
        FinancialDataAggregated.Проект,
        FinancialDataAggregated.Контрагент
    ).filter(
        FinancialDataAggregated.год == year,
        FinancialDataAggregated.месяц.in_(months)
    )
    
    if projects:
        query = query.filter(FinancialDataAggregated.Проект.in_(projects))
    
    if distributions:
        query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
    
    if config:
        if 'СтатьяУровень1' in config:
            if isinstance(config['СтатьяУровень1'], list):
                query = query.filter(FinancialDataAggregated.СтатьяУровень1.in_(config['СтатьяУровень1']))
            else:
                query = query.filter(FinancialDataAggregated.СтатьяУровень1 == config['СтатьяУровень1'])
        if 'СтатьяУровень2' in config:
            query = query.filter(FinancialDataAggregated.СтатьяУровень2 == config['СтатьяУровень2'])
    
    return query.all()

def get_contragent_data_optimized(projects, distributions, months, year, level1=None, level2=None, level3=None, level4=None):
    """Оптимизированное получение данных по контрагентам"""
    query = db.session.query(
        ContragentSummaryView.Контрагент,
        ContragentSummaryView.сумма_итого.label('total')
    ).filter(
        ContragentSummaryView.год == year,
        ContragentSummaryView.Проект.in_(projects)
    )
    
    if distributions:
        # Для контрагентного представления нужно использовать исходную таблицу
        query_contragent = db.session.query(
            FinancialData.Контрагент,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Период.isnot(None),
            FinancialData.Проект.in_(projects),
            extract('year', FinancialData.Период) == year,
            extract('month', FinancialData.Период).in_(months)
        )
        
        if distributions:
            query_contragent = query_contragent.filter(FinancialData.Распределение.in_(distributions))
        
        if level1:
            query_contragent = query_contragent.filter(FinancialData.СтатьяУровень1 == level1)
        if level2:
            query_contragent = query_contragent.filter(FinancialData.СтатьяУровень2 == level2)
        if level3:
            query_contragent = query_contragent.filter(FinancialData.СтатьяУровень3 == level3)
        if level4:
            query_contragent = query_contragent.filter(FinancialData.СтатьяУровень4 == level4)
        
        query_contragent = query_contragent.group_by(FinancialData.Контрагент)
        results = query_contragent.all()
        
        contragents = {}
        for contragent, total in results:
            contragents[contragent or 'Не указано'] = float(total or 0)
        return contragents
    
    else:
        if level1:
            query = query.filter(ContragentSummaryView.СтатьяУровень1 == level1)
        if level2:
            query = query.filter(ContragentSummaryView.СтатьяУровень2 == level2)
        if level3:
            query = query.filter(ContragentSummaryView.СтатьяУровень3 == level3)
        if level4:
            query = query.filter(ContragentSummaryView.СтатьяУровень4 == level4)
        
        results = query.all()
        
        contragents = {}
        for contragent, total in results:
            contragents[contragent or 'Не указано'] = float(total or 0)
        return contragents

# ====== ОБЩИЕ ФУНКЦИИ (остаются без изменений) ======

def calculate_total(rows):
    """Сумма всех сумм (чистый денежный поток)"""
    return sum(row.Сумма or 0 for row in rows)

def calculate_od_result(rows):
    """Расчет результата ОД = Поступления по ОД + Отток по ОД"""
    od_income = sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Поступления по ОД')
    od_expense = sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Отток по ОД')
    return od_income + od_expense

def calculate_od_income(rows):
    """Расчет поступлений по ОД"""
    return sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Поступления по ОД')

def calculate_od_expense(rows):
    """Расчет оттока по ОД"""
    return sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Отток по ОД')

def calculate_variables(rows):
    """Расчет переменных расходов"""
    return sum(row.Сумма or 0 for row in rows 
               if row.СтатьяУровень1 == 'Отток по ОД' 
               and row.СтатьяУровень2 == 'Отток по ОД (переменные)')

def calculate_constants(rows):
    """Расчет постоянных расходов"""
    return sum(row.Сумма or 0 for row in rows 
               if row.СтатьяУровень1 == 'Отток по ОД' 
               and row.СтатьяУровень2 == 'Отток по ОД (постоянные)')

def calculate_id_result(rows):
    """Расчет результата по ИД"""
    return sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Результат по ИД')

def calculate_fin_result(rows):
    """Расчет результата финансов"""
    return sum(row.Сумма or 0 for row in rows if row.СтатьяУровень1 == 'Финансы')

def calculate_indicator(rows, indicator_key):
    """Рассчитывает значение показателя по ключу"""
    if indicator_key == 'net_cash_flow':
        return calculate_total(rows)
    elif indicator_key == 'od_result':
        return calculate_od_result(rows)
    elif indicator_key == 'od_income':
        return calculate_od_income(rows)
    elif indicator_key == 'od_expense':
        return calculate_od_expense(rows)
    elif indicator_key == 'variables':
        return calculate_variables(rows)
    elif indicator_key == 'constants':
        return calculate_constants(rows)
    elif indicator_key == 'id_result':
        return calculate_id_result(rows)
    elif indicator_key == 'fin_result':
        return calculate_fin_result(rows)
    else:
        return 0

# ====== API ДЛЯ ОТЧЕТА 1 ======

# API: Данные для фильтров (оптимизированная версия)
@app.route('/api/report1/filters-data')
@login_required
def get_filters_data():
    """Возвращает данные для инициализации фильтров (оптимизированная версия)"""
    try:
        # Используем представление для быстрых фильтров
        # Для этого лучше использовать прямой SQL запрос к представлению
        with db.engine.connect() as connection:
            # Годы
            years_result = connection.execute(
                text("SELECT DISTINCT год FROM financial_data_aggregated ORDER BY год")
            )
            year_list = [int(row[0]) for row in years_result if row[0]]
            
            # Проекты
            projects_result = connection.execute(
                text("SELECT DISTINCT Проект FROM financial_data_aggregated WHERE Проект IS NOT NULL AND Проект != '' ORDER BY Проект")
            )
            projects = [row[0] for row in projects_result if row[0]]
            
            # Распределения
            distributions_result = connection.execute(
                text("SELECT DISTINCT Распределение FROM financial_data_aggregated WHERE Распределение IS NOT NULL AND Распределение != '' ORDER BY Распределение")
            )
            dist_list = [row[0] for row in distributions_result if row[0]]
        
        return jsonify({
            'success': True,
            'years': year_list,
            'projects': projects,
            'distributions': dist_list
        })
        
    except Exception as e:
        logger.error(f"Error in filters data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Агрегированная таблица эффективности (оптимизированная)
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
        
        # Получаем данные за минимальный год (оптимизированно)
        data_min_year = get_year_data_optimized(projects, distributions, months, year_min)
        # Получаем данные за максимальный год (оптимизированно)
        data_max_year = get_year_data_optimized(projects, distributions, months, year_max)
        
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

# API: Детализация иерархии (оптимизированная)
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
        
        # Получаем данные за оба года (оптимизированно)
        data_min_year = get_year_data_for_hierarchy_optimized(projects, distributions, months, year_min, config)
        data_max_year = get_year_data_for_hierarchy_optimized(projects, distributions, months, year_max, config)
        
        # Строим иерархию
        hierarchy = build_hierarchy_with_years(data_min_year, data_max_year, year_min, year_max)
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy
        })
        
    except Exception as e:
        logger.error(f"Error in hierarchy details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Анализ по контрагентам (оптимизированная)
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
        
        # Получаем контрагентов за оба года (оптимизированно)
        contragents_min = get_contragent_data_optimized(projects, distributions, months, year_min, level1, level2, level3, level4)
        contragents_max = get_contragent_data_optimized(projects, distributions, months, year_max, level1, level2, level3, level4)
        
        # Объединяем и считаем отклонения
        contragents = calculate_contragent_deviations(contragents_min, contragents_max)
        
        return jsonify({
            'success': True,
            'contragents': contragents[:50]  # Ограничиваем 50 контрагентами
        })
        
    except Exception as e:
        logger.error(f"Error in contragent analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Поиск контрагентов по уровню (оптимизированная)
@app.route('/api/report1/find-contragents-by-level', methods=['POST'])
@login_required
def find_contragents_by_level():
    try:
        data = request.get_json()
        level = data.get('level')
        level_name = data.get('level_name')
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects or not months or not year_min or not year_max or not level_name:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Для оптимальной производительности используем агрегированное представление
        contragents_min = {}
        contragents_max = {}
        
        for year in [year_min, year_max]:
            # Используем агрегированное представление
            query = db.session.query(
                FinancialDataAggregated.Контрагент,
                func.sum(FinancialDataAggregated.сумма_итого).label('total')
            ).filter(
                FinancialDataAggregated.год == year,
                FinancialDataAggregated.месяц.in_(months),
                FinancialDataAggregated.Проект.in_(projects)
            )
            
            # Определяем поле для фильтрации по уровню
            if level == 1:
                query = query.filter(FinancialDataAggregated.СтатьяУровень1 == level_name)
            elif level == 2:
                query = query.filter(FinancialDataAggregated.СтатьяУровень2 == level_name)
            elif level == 3:
                query = query.filter(FinancialDataAggregated.СтатьяУровень3 == level_name)
            elif level == 4:
                query = query.filter(FinancialDataAggregated.СтатьяУровень4 == level_name)
            else:
                return jsonify({'success': False, 'error': 'Неверный уровень'}), 400
            
            if distributions:
                query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
            
            query = query.group_by(FinancialDataAggregated.Контрагент)
            results = query.all()
            
            if year == year_min:
                for contragent, total in results:
                    contragents_min[contragent or 'Не указано'] = float(total or 0)
            else:
                for contragent, total in results:
                    contragents_max[contragent or 'Не указано'] = float(total or 0)
        
        # Объединяем и считаем отклонения
        all_contragents = set(list(contragents_min.keys()) + list(contragents_max.keys()))
        contragents = []
        
        for contragent in all_contragents:
            min_value = contragents_min.get(contragent, 0)
            max_value = contragents_max.get(contragent, 0)
            deviation = max_value - min_value
            
            contragents.append({
                'contragent': contragent,
                'min_year': min_value,
                'max_year': max_value,
                'deviation': deviation
            })
        
        # Сортируем по абсолютному значению отклонения
        contragents.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        # Рассчитываем проценты
        total_deviation = sum(abs(c['deviation']) for c in contragents)
        for c in contragents:
            c['percentage'] = round((abs(c['deviation']) / total_deviation * 100), 2) if total_deviation > 0 else 0
        
        return jsonify({
            'success': True,
            'contragents': contragents[:50],  # Ограничиваем 50 контрагентами
            'level': level,
            'level_name': level_name
        })
        
    except Exception as e:
        logger.error(f"Error finding contragents by level: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные для таблицы по месяцам (оптимизированная)
@app.route('/api/report1/monthly-data', methods=['POST'])
@login_required
def get_monthly_data():
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
            'net_cash_flow': {},  # Все статьи
            'od_result': {'СтатьяУровень1': ['Поступления по ОД', 'Отток по ОД']}
        }
        
        config = indicator_config.get(indicator_key, {})
        
        # Получаем данные по месяцам через агрегированное представление
        monthly_data = {year_min: {}, year_max: {}}
        
        for year in [year_min, year_max]:
            query = db.session.query(
                FinancialDataAggregated.месяц,
                func.sum(FinancialDataAggregated.сумма_итого).label('total')
            ).filter(
                FinancialDataAggregated.год == year,
                FinancialDataAggregated.месяц.in_(months),
                FinancialDataAggregated.Проект.in_(projects)
            )
            
            if distributions:
                query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
            
            if config:
                if 'СтатьяУровень1' in config:
                    if isinstance(config['СтатьяУровень1'], list):
                        query = query.filter(FinancialDataAggregated.СтатьяУровень1.in_(config['СтатьяУровень1']))
                    else:
                        query = query.filter(FinancialDataAggregated.СтатьяУровень1 == config['СтатьяУровень1'])
                if 'СтатьяУровень2' in config:
                    query = query.filter(FinancialDataAggregated.СтатьяУровень2 == config['СтатьяУровень2'])
            
            query = query.group_by(FinancialDataAggregated.месяц)
            results = query.all()
            
            for month, total in results:
                if month:
                    monthly_data[year][int(month)] = float(total or 0)
        
        return jsonify({
            'success': True,
            'monthly_data': monthly_data
        })
        
    except Exception as e:
        logger.error(f"Error in monthly data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Анализ распределений (оптимизированная)
@app.route('/api/report1/distribution-analysis', methods=['POST'])
@login_required
def get_distribution_analysis():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not projects or not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Анализируем распределения через агрегированное представление
        distribution_stats = {}
        
        for year in [year_min, year_max]:
            query = db.session.query(
                FinancialDataAggregated.Распределение,
                func.sum(FinancialDataAggregated.сумма_итого).label('total')
            ).filter(
                FinancialDataAggregated.год == year,
                FinancialDataAggregated.месяц.in_(months),
                FinancialDataAggregated.Проект.in_(projects)
            )
            
            if distributions:
                query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
            
            query = query.group_by(FinancialDataAggregated.Распределение)
            results = query.all()
            
            for dist, total in results:
                if dist not in distribution_stats:
                    distribution_stats[dist] = {'min_year': 0, 'max_year': 0}
                
                if year == year_min:
                    distribution_stats[dist]['min_year'] = float(total or 0)
                else:
                    distribution_stats[dist]['max_year'] = float(total or 0)
        
        # Формируем результат
        result = []
        for dist, data in distribution_stats.items():
            deviation = data['max_year'] - data['min_year']
            result.append({
                'distribution': dist or 'Не указано',
                'min_year': data['min_year'],
                'max_year': data['max_year'],
                'deviation': deviation
            })
        
        # Сортируем по отклонению
        result.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        # Рассчитываем общие суммы
        total_min = sum(item['min_year'] for item in result)
        total_max = sum(item['max_year'] for item in result)
        total_deviation = total_max - total_min
        
        return jsonify({
            'success': True,
            'distribution_stats': {
                'distributions': result,
                'total_min': total_min,
                'total_max': total_max,
                'total_deviation': total_deviation
            }
        })
        
    except Exception as e:
        logger.error(f"Error in distribution analysis: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== API ДЛЯ ОТЧЕТА 2 (остальные аналогично Report 1) ======

# API: Данные для фильтров (без проектов)
@app.route('/api/report2/filters-data')
@login_required
def get_report2_filters_data():
    """Возвращает данные для инициализации фильтров (без проектов)"""
    try:
        # Используем представление для быстрых фильтров
        with db.engine.connect() as connection:
            # Годы
            years_result = connection.execute(
                text("SELECT DISTINCT год FROM financial_data_aggregated ORDER BY год")
            )
            year_list = [int(row[0]) for row in years_result if row[0]]
            
            # Распределения
            distributions_result = connection.execute(
                text("SELECT DISTINCT Распределение FROM financial_data_aggregated WHERE Распределение IS NOT NULL AND Распределение != '' ORDER BY Распределение")
            )
            dist_list = [row[0] for row in distributions_result if row[0]]
        
        return jsonify({
            'success': True,
            'years': year_list,
            'distributions': dist_list
        })
        
    except Exception as e:
        logger.error(f"Error in report2 filters data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Агрегированная таблица эффективности (итого по всем проектам)
@app.route('/api/report2/aggregated', methods=['POST'])
@login_required
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
        
        # Получаем все проекты через представление
        with db.engine.connect() as connection:
            projects_result = connection.execute(
                text("SELECT DISTINCT Проект FROM financial_data_aggregated WHERE Проект IS NOT NULL AND Проект != ''")
            )
            all_projects = [row[0] for row in projects_result if row[0]]
        
        # Получаем данные за минимальный год (все проекты)
        data_min_year = get_year_data_optimized(all_projects, distributions, months, year_min)
        # Получаем данные за максимальный год (все проекты)
        data_max_year = get_year_data_optimized(all_projects, distributions, months, year_max)
        
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
        logger.error(f"Error in report2 aggregated table: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== API ДЛЯ ОТЧЕТА 3 ======

# API: Данные для фильтров (без проектов, но с выбором показателя)
@app.route('/api/report3/filters-data')
@login_required
def get_report3_filters_data():
    """Возвращает данные для инициализации фильтров"""
    try:
        # Используем представление для быстрых фильтров
        with db.engine.connect() as connection:
            # Годы
            years_result = connection.execute(
                text("SELECT DISTINCT год FROM financial_data_aggregated ORDER BY год")
            )
            year_list = [int(row[0]) for row in years_result if row[0]]
            
            # Распределения
            distributions_result = connection.execute(
                text("SELECT DISTINCT Распределение FROM financial_data_aggregated WHERE Распределение IS NOT NULL AND Распределение != '' ORDER BY Распределение")
            )
            dist_list = [row[0] for row in distributions_result if row[0]]
        
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
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные по проектам для таблицы (оптимизированная)
@app.route('/api/report3/projects-data', methods=['POST'])
@login_required
def get_report3_projects_data():
    try:
        data = request.get_json()
        indicator_key = data.get('indicator_key')
        distributions = data.get('distributions', [])
        months = data.get('months', [])
        year_min = data.get('year_min')
        year_max = data.get('year_max')
        
        if not indicator_key or not months or not year_min or not year_max:
            return jsonify({'success': False, 'error': 'Недостаточно данных'}), 400
        
        # Получаем все проекты через представление
        with db.engine.connect() as connection:
            projects_result = connection.execute(
                text("SELECT DISTINCT Проект FROM financial_data_aggregated WHERE Проект IS NOT NULL AND Проект != '' ORDER BY Проект")
            )
            all_projects = [row[0] for row in projects_result if row[0]]
        
        # Данные для результата
        projects_data = []
        
        for project in all_projects:
            # Получаем данные за минимальный год для этого проекта
            data_min_year = get_year_data_optimized([project], distributions, months, year_min)
            # Получаем данные за максимальный год для этого проекта
            data_max_year = get_year_data_optimized([project], distributions, months, year_max)
            
            # Рассчитываем показатель для этого проекта
            min_value = calculate_indicator(data_min_year, indicator_key)
            max_value = calculate_indicator(data_max_year, indicator_key)
            deviation = max_value - min_value
            
            projects_data.append({
                'project': project,
                'min_year': min_value,
                'max_year': max_value,
                'deviation': deviation
            })
        
        # Сортируем по отклонению (по модулю)
        projects_data.sort(key=lambda x: abs(x['deviation']), reverse=True)
        
        return jsonify({
            'success': True,
            'projects_data': projects_data,
            'year_min': year_min,
            'year_max': year_max,
            'indicator_key': indicator_key
        })
        
    except Exception as e:
        logger.error(f"Error in report3 projects data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (остаются без изменений) ======

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
        all_data[key]['min_year'] += row.Сумма or 0
    
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
        all_data[key]['max_year'] += row.Сумма or 0
    
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
        all_data[key]['min_year'] += row.Сумма or 0
    
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
        all_data[key]['max_year'] += row.Сумма or 0
    
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

def get_deviation_data_by_levels(projects, distributions, months, year_min, year_max, indicator_key):
    """Получает данные для анализа отклонений по уровням"""
    # Определяем какие статьи анализировать
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
    
    # Получаем данные за оба года (оптимизированно)
    data_min_year = get_year_data_for_hierarchy_optimized(projects, distributions, months, year_min, config)
    data_max_year = get_year_data_for_hierarchy_optimized(projects, distributions, months, year_max, config)
    
    # Группируем по уровням
    level1_data = {}
    level2_data = {}
    level3_data = {}
    level4_data = {}
    
    # Собираем данные за минимальный год
    for row in data_min_year:
        level1 = row.СтатьяУровень1 or 'Не указано'
        level2 = row.СтатьяУровень2 or 'Не указано'
        level3 = row.СтатьяУровень3 or 'Не указано'
        level4 = row.СтатьяУровень4 or 'Не указано'
        
        if level1 not in level1_data:
            level1_data[level1] = {'min_year': 0, 'max_year': 0}
        level1_data[level1]['min_year'] += row.Сумма or 0
        
        if level2 not in level2_data:
            level2_data[level2] = {'min_year': 0, 'max_year': 0}
        level2_data[level2]['min_year'] += row.Сумма or 0
        
        if level3 not in level3_data:
            level3_data[level3] = {'min_year': 0, 'max_year': 0}
        level3_data[level3]['min_year'] += row.Сумма or 0
        
        if level4 not in level4_data:
            level4_data[level4] = {'min_year': 0, 'max_year': 0}
        level4_data[level4]['min_year'] += row.Сумма or 0
    
    # Собираем данные за максимальный год
    for row in data_max_year:
        level1 = row.СтатьяУровень1 or 'Не указано'
        level2 = row.СтатьяУровень2 or 'Не указано'
        level3 = row.СтатьяУровень3 or 'Не указано'
        level4 = row.СтатьяУровень4 or 'Не указано'
        
        if level1 not in level1_data:
            level1_data[level1] = {'min_year': 0, 'max_year': 0}
        level1_data[level1]['max_year'] += row.Сумма or 0
        
        if level2 not in level2_data:
            level2_data[level2] = {'min_year': 0, 'max_year': 0}
        level2_data[level2]['max_year'] += row.Сумма or 0
        
        if level3 not in level3_data:
            level3_data[level3] = {'min_year': 0, 'max_year': 0}
        level3_data[level3]['max_year'] += row.Сумма or 0
        
        if level4 not in level4_data:
            level4_data[level4] = {'min_year': 0, 'max_year': 0}
        level4_data[level4]['max_year'] += row.Сумма or 0
    
    # Формируем результат
    result = {
        'level1': [],
        'level2': [],
        'level3': [],
        'level4': []
    }
    
    # Уровень 1
    for name, data in level1_data.items():
        deviation = data['max_year'] - data['min_year']
        if deviation != 0:
            result['level1'].append({
                'name': name,
                'min_year': data['min_year'],
                'max_year': data['max_year'],
                'deviation': deviation
            })
    
    # Уровень 2
    for name, data in level2_data.items():
        deviation = data['max_year'] - data['min_year']
        if deviation != 0:
            result['level2'].append({
                'name': name,
                'min_year': data['min_year'],
                'max_year': data['max_year'],
                'deviation': deviation
            })
    
    # Уровень 3
    for name, data in level3_data.items():
        deviation = data['max_year'] - data['min_year']
        if deviation != 0:
            result['level3'].append({
                'name': name,
                'min_year': data['min_year'],
                'max_year': data['max_year'],
                'deviation': deviation
            })
    
    # Уровень 4
    for name, data in level4_data.items():
        deviation = data['max_year'] - data['min_year']
        if deviation != 0:
            result['level4'].append({
                'name': name,
                'min_year': data['min_year'],
                'max_year': data['max_year'],
                'deviation': deviation
            })
    
    # Сортируем по отклонению
    result['level1'].sort(key=lambda x: abs(x['deviation']), reverse=True)
    result['level2'].sort(key=lambda x: abs(x['deviation']), reverse=True)
    result['level3'].sort(key=lambda x: abs(x['deviation']), reverse=True)
    result['level4'].sort(key=lambda x: abs(x['deviation']), reverse=True)
    
    return result

def get_monthly_comparison_data(projects, distributions, months, year_min, year_max, indicator_key):
    """Получает данные по месяцам для таблицы сравнения"""
    # Определяем какие статьи анализировать
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
    
    # Получаем данные по месяцам через агрегированное представление
    monthly_data = {year_min: {}, year_max: {}}
    
    for year in [year_min, year_max]:
        query = db.session.query(
            FinancialDataAggregated.месяц,
            func.sum(FinancialDataAggregated.сумма_итого).label('total')
        ).filter(
            FinancialDataAggregated.год == year,
            FinancialDataAggregated.месяц.in_(months),
            FinancialDataAggregated.Проект.in_(projects)
        )
        
        if distributions:
            query = query.filter(FinancialDataAggregated.Распределение.in_(distributions))
        
        if config:
            if 'СтатьяУровень1' in config:
                if isinstance(config['СтатьяУровень1'], list):
                    query = query.filter(FinancialDataAggregated.СтатьяУровень1.in_(config['СтатьяУровень1']))
                else:
                    query = query.filter(FinancialDataAggregated.СтатьяУровень1 == config['СтатьяУровень1'])
            if 'СтатьяУровень2' in config:
                query = query.filter(FinancialDataAggregated.СтатьяУровень2 == config['СтатьяУровень2'])
        
        query = query.group_by(FinancialDataAggregated.месяц)
        results = query.all()
        
        for month, total in results:
            if month:
                monthly_data[year][int(month)] = float(total or 0)
    
    return monthly_data

# ====== СТАРЫЕ API (для совместимости) ======

@app.route('/api/debug/data')
def debug_data():
    try:
        stats = db.session.query(
            FinancialDataAggregated.СтатьяУровень1,
            func.sum(FinancialDataAggregated.количество_записей).label('count'),
            func.sum(FinancialDataAggregated.сумма_итого).label('total')
        ).group_by(FinancialDataAggregated.СтатьяУровень1).all()
        
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

@app.route('/api/report4/data')
@login_required
def get_report4_data():
    try:
        # Здесь будет логика для отчета 4
        return jsonify({'success': True, 'message': 'Report 4 data endpoint'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ====== ИНИЦИАЛИЗАЦИЯ ======

with app.app_context():
    try:
        db.create_all()
        init_admin()
        
        # Создаем представления (если они еще не существуют)
        try:
            # Проверяем существование представлений и создаем их при необходимости
            with db.engine.connect() as connection:
                # Проверяем существование financial_data_aggregated
                check_view = connection.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'financial_data_aggregated')")
                ).scalar()
                
                if not check_view:
                    logger.info("Creating database views...")
                    # Здесь можно выполнить SQL для создания представлений
                    # В продакшене лучше использовать миграции
                    pass
                    
        except Exception as e:
            logger.warning(f"Could not check/create views: {e}")
        
        print('✅ Приложение инициализировано')
    except Exception as e:
        print(f'❌ Ошибка: {e}')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)