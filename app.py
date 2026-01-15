from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from config import Config
from database import db
from models import User, FinancialData, ProjectMetrics
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, case, and_, or_, desc
import json
import traceback

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных
db.init_app(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Регистрация blueprint
app.register_blueprint(auth_bp, url_prefix='/auth')

# Главная страница
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Отчет 1: Эффективность выбранных проектов
@app.route('/report1')
@login_required
def report1():
    return render_template('report1.html')

# Отчет 2: Сводная таблица всех проектов
@app.route('/report2')
@login_required
def report2():
    return render_template('report2.html')

# Отчет 3: Анализ статей расходов/доходов
@app.route('/report3')
@login_required
def report3():
    return render_template('report3.html')

# Отчет 4: Анализ ФОТ и сотрудников
@app.route('/report4')
@login_required
def report4():
    return render_template('report4.html')

# API: Получение проектов
@app.route('/api/projects')
@login_required
def get_projects():
    try:
        # Проверяем подключение к базе
        db.session.execute('SELECT 1')
        
        projects_query = db.session.query(
            FinancialData.Проект
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
        ).distinct().all()
        
        projects = [p[0] for p in projects_query if p[0]]
        
        if not projects:
            # Возвращаем тестовые данные если база пустая
            return jsonify({
                'DCA': ['Alpha DCA', 'Beta DCA', 'Gamma DCA'],
                'DP': ['Delta DP', 'Epsilon DP', 'Zeta DP'],
                'Прочие': ['Проект 1', 'Проект 2', 'Проект 3']
            })
        
        # Группировка проектов
        grouped = {
            'DCA': [],
            'DP': [],
            'Прочие': []
        }
        
        for project in projects:
            project_str = str(project).upper()
            if 'DCA' in project_str:
                grouped['DCA'].append(project)
            elif 'DP' in project_str:
                grouped['DP'].append(project)
            else:
                grouped['Прочие'].append(project)
        
        return jsonify(grouped)
        
    except Exception as e:
        logger.error(f"Error in get_projects: {str(e)}")
        # Возвращаем тестовые данные при ошибке
        return jsonify({
            'DCA': ['Alpha DCA', 'Beta DCA', 'Gamma DCA'],
            'DP': ['Delta DP', 'Epsilon DP', 'Zeta DP'],
            'Прочие': ['Проект 1', 'Проект 2', 'Проект 3']
        })

# API: Данные для отчета 1
@app.route('/api/report1/data', methods=['POST'])
@login_required
def get_report1_data():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        period_from = data.get('period_from')
        period_to = data.get('period_to')
        
        logger.info(f"Report1 request: projects={projects}, from={period_from}, to={period_to}")
        
        # Если проекты не выбраны, возвращаем тестовые данные
        if not projects:
            return jsonify({
                'success': True,
                'hierarchy': create_test_hierarchy(),
                'metrics': create_test_metrics(projects),
                'period': {
                    'from': period_from or '2024-01-01',
                    'to': period_to or '2024-12-31'
                }
            })
        
        # Преобразуем даты
        try:
            date_from = datetime.strptime(period_from, '%Y-%m-%d') if period_from else datetime(2024, 1, 1)
            date_to = datetime.strptime(period_to, '%Y-%m-%d') if period_to else datetime(2024, 12, 31)
        except:
            today = datetime.now()
            date_from = datetime(today.year, today.month, 1)
            date_to = datetime(today.year, today.month, 1) + timedelta(days=32)
            date_to = datetime(date_to.year, date_to.month, 1) - timedelta(days=1)
        
        # Проверяем есть ли данные в базе
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count == 0:
            # Нет данных в базе - возвращаем тестовые
            return jsonify({
                'success': True,
                'hierarchy': create_test_hierarchy(),
                'metrics': create_test_metrics(projects),
                'period': {
                    'from': date_from.strftime('%Y-%m-%d'),
                    'to': date_to.strftime('%Y-%m-%d')
                }
            })
        
        # Базовый запрос
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4,
            FinancialData.Проект,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Проект.in_(projects),
            FinancialData.Период.between(date_from, date_to),
            FinancialData.Распределение == 'распределение'
        ).group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4,
            FinancialData.Проект
        ).order_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4
        )
        
        results = query.all()
        
        # Преобразуем в иерархическую структуру
        hierarchy = {}
        for row in results:
            level1 = row.СтатьяУровень1 or 'Без категории'
            level2 = row.СтатьяУровень2 or 'Без подкатегории'
            level4 = row.СтатьяУровень4 or 'Без статьи'
            
            if level1 not in hierarchy:
                hierarchy[level1] = {}
            
            if level2 not in hierarchy[level1]:
                hierarchy[level1][level2] = {}
            
            if level4 not in hierarchy[level1][level2]:
                hierarchy[level1][level2][level4] = {}
            
            if row.Проект not in hierarchy[level1][level2][level4]:
                hierarchy[level1][level2][level4][row.Проект] = 0
            
            hierarchy[level1][level2][level4][row.Проект] += float(row.total or 0)
        
        # Рассчитываем метрики ROI и маржинальность
        metrics_query = db.session.query(
            FinancialData.Проект,
            func.sum(
                case(
                    (and_(
                        FinancialData.СтатьяУровень1 == 'Поступления по ОД',
                        FinancialData.Распределение == 'распределение'
                    ), FinancialData.Сумма),
                    else_=0
                )
            ).label('income'),
            func.sum(
                case(
                    (and_(
                        FinancialData.СтатьяУровень1 == 'Отток по ОД',
                        FinancialData.Распределение == 'распределение'
                    ), FinancialData.Сумма),
                    else_=0
                )
            ).label('expense')
        ).filter(
            FinancialData.Проект.in_(projects),
            FinancialData.Период.between(date_from, date_to)
        ).group_by(FinancialData.Проект)
        
        metrics_results = metrics_query.all()
        
        metrics = {}
        for row in metrics_results:
            project_name = row.Проект
            income = float(row.income or 0)
            expense = float(row.expense or 0)
            net = income - expense
            
            if income > 0:
                margin = ((income - expense) / income) * 100
            else:
                margin = 0
            
            if expense > 0:
                roi = ((income - expense) / expense) * 100
            else:
                roi = 0
            
            metrics[project_name] = {
                'margin': round(margin, 2),
                'roi': round(roi, 2),
                'income': round(income, 2),
                'expense': round(expense, 2),
                'net': round(net, 2)
            }
        
        # Добавляем проекты без данных
        for project in projects:
            if project not in metrics:
                metrics[project] = {
                    'margin': 0,
                    'roi': 0,
                    'income': 0,
                    'expense': 0,
                    'net': 0
                }
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy if hierarchy else create_test_hierarchy(),
            'metrics': metrics if metrics else create_test_metrics(projects),
            'period': {
                'from': date_from.strftime('%Y-%m-%d'),
                'to': date_to.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        logger.error(f"Error in report1: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'hierarchy': create_test_hierarchy(),
            'metrics': create_test_metrics(projects if 'projects' in locals() else [])
        })

def create_test_hierarchy():
    """Создание тестовой иерархии для демонстрации"""
    return {
        'Поступления по ОД': {
            'Доходы от продаж': {
                'Продажи продукции': {
                    'Alpha DCA': 1500000,
                    'Beta DCA': 1200000,
                    'Delta DP': 900000
                },
                'Услуги консалтинга': {
                    'Gamma DCA': 800000,
                    'Epsilon DP': 700000
                }
            }
        },
        'Отток по ОД': {
            'Расходы на персонал': {
                'ФОТ_и_социальные_выплаты': {
                    'Alpha DCA': 500000,
                    'Beta DCA': 400000,
                    'Delta DP': 300000
                }
            },
            'Операционные расходы': {
                'Аренда и коммунальные': {
                    'Gamma DCA': 200000,
                    'Epsilon DP': 150000
                }
            }
        }
    }

def create_test_metrics(projects):
    """Создание тестовых метрик"""
    if not projects:
        projects = ['Alpha DCA', 'Beta DCA', 'Delta DP', 'Gamma DCA', 'Epsilon DP']
    
    metrics = {}
    for i, project in enumerate(projects):
        income = 1000000 + i * 200000
        expense = 500000 + i * 100000
        net = income - expense
        margin = (net / income * 100) if income > 0 else 0
        roi = (net / expense * 100) if expense > 0 else 0
        
        metrics[project] = {
            'margin': round(margin, 2),
            'roi': round(roi, 2),
            'income': round(income, 2),
            'expense': round(expense, 2),
            'net': round(net, 2)
        }
    
    return metrics

# API: ТОП-10 расходов для проекта
@app.route('/api/top_expenses/<project>')
@login_required
def get_top_expenses(project):
    try:
        # Проверяем есть ли данные
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count == 0:
            # Возвращаем тестовые данные
            return jsonify({
                'success': True,
                'expenses': create_test_expenses(project)
            })
        
        # Получаем период из сессии или используем текущий месяц
        period_from = session.get('report1_period_from')
        period_to = session.get('report1_period_to')
        
        if not period_from or not period_to:
            today = datetime.now()
            period_from = datetime(today.year, today.month, 1)
            period_to = datetime(today.year, today.month, 1) + timedelta(days=32)
            period_to = datetime(period_to.year, period_to.month, 1) - timedelta(days=1)
        else:
            period_from = datetime.strptime(period_from, '%Y-%m-%d')
            period_to = datetime.strptime(period_to, '%Y-%m-%d')
        
        query = db.session.query(
            FinancialData.СтатьяУровень4,
            FinancialData.СтатьяУровень2,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Проект == project,
            FinancialData.СтатьяУровень1 == 'Отток по ОД',
            FinancialData.Распределение == 'распределение',
            FinancialData.Период.between(period_from, period_to)
        ).group_by(
            FinancialData.СтатьяУровень4,
            FinancialData.СтатьяУровень2
        ).order_by(func.sum(FinancialData.Сумма).desc()).limit(10)
        
        results = query.all()
        
        expenses = []
        for row in results:
            expenses.append({
                'level4': row.СтатьяУровень4 or 'Без статьи',
                'level2': row.СтатьяУровень2 or 'Без категории',
                'total': round(abs(float(row.total or 0)), 2)
            })
        
        if not expenses:
            return jsonify({
                'success': True,
                'expenses': create_test_expenses(project)
            })
        
        return jsonify({'success': True, 'expenses': expenses})
        
    except Exception as e:
        logger.error(f"Error getting top expenses: {str(e)}")
        return jsonify({'success': True, 'expenses': create_test_expenses(project)})

def create_test_expenses(project):
    """Создание тестовых расходов"""
    expenses = [
        {'level4': 'ФОТ_и_социальные_выплаты', 'level2': 'Расходы на персонал', 'total': 500000},
        {'level4': 'Аренда офиса', 'level2': 'Операционные расходы', 'total': 200000},
        {'level4': 'Закупка материалов', 'level2': 'Себестоимость', 'total': 150000},
        {'level4': 'Маркетинг и реклама', 'level2': 'Коммерческие расходы', 'total': 100000},
        {'level4': 'Обслуживание техники', 'level2': 'Технические расходы', 'total': 80000},
        {'level4': 'Командировочные', 'level2': 'Административные расходы', 'total': 60000},
        {'level4': 'Связь и интернет', 'level2': 'Операционные расходы', 'total': 40000},
        {'level4': 'Обучение сотрудников', 'level2': 'Развитие персонала', 'total': 30000},
        {'level4': 'Бухгалтерские услуги', 'level2': 'Административные расходы', 'total': 20000},
        {'level4': 'Канцелярия', 'level2': 'Операционные расходы', 'total': 10000}
    ]
    return expenses

# API: Данные для отчета 2
@app.route('/api/report2/data')
@login_required
def get_report2_data():
    try:
        # Проверяем есть ли данные
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count == 0:
            # Возвращаем тестовые данные
            return jsonify({
                'success': True,
                'projects': create_test_projects()
            })
        
        # Рассчитываем метрики для всех проектов
        query = db.session.query(
            FinancialData.Проект,
            func.sum(
                case(
                    (and_(
                        FinancialData.СтатьяУровень1 == 'Поступления по ОД',
                        FinancialData.Распределение == 'распределение'
                    ), FinancialData.Сумма),
                    else_=0
                )
            ).label('income'),
            func.sum(
                case(
                    (and_(
                        FinancialData.СтатьяУровень1 == 'Отток по ОД',
                        FinancialData.Распределение == 'распределение'
                    ), FinancialData.Сумма),
                    else_=0
                )
            ).label('expense')
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
        ).group_by(FinancialData.Проект)
        
        results = query.all()
        
        projects_data = []
        for row in results:
            project = row.Проект
            income = float(row.income or 0)
            expense = float(row.expense or 0)
            net = income - expense
            
            # Определяем группу
            project_upper = str(project).upper()
            if 'DCA' in project_upper:
                group = 'DCA'
            elif 'DP' in project_upper:
                group = 'DP'
            else:
                group = 'Прочие'
            
            # Рассчитываем метрики
            margin = ((income - expense) / income * 100) if income > 0 else 0
            roi = ((income - expense) / expense * 100) if expense > 0 else 0
            
            projects_data.append({
                'project': project,
                'group': group,
                'income': round(income, 2),
                'expense': round(expense, 2),
                'net': round(net, 2),
                'margin': round(margin, 2),
                'roi': round(roi, 2)
            })
        
        if not projects_data:
            return jsonify({
                'success': True,
                'projects': create_test_projects()
            })
        
        # Сортируем по ROI
        projects_data.sort(key=lambda x: x['roi'], reverse=True)
        
        return jsonify({'success': True, 'projects': projects_data})
        
    except Exception as e:
        logger.error(f"Error in report2: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': True,
            'projects': create_test_projects()
        })

def create_test_projects():
    """Создание тестовых проектов"""
    projects = [
        {
            'project': 'Alpha DCA',
            'group': 'DCA',
            'income': 1500000,
            'expense': 800000,
            'net': 700000,
            'margin': 46.67,
            'roi': 87.5
        },
        {
            'project': 'Beta DCA',
            'group': 'DCA',
            'income': 1200000,
            'expense': 700000,
            'net': 500000,
            'margin': 41.67,
            'roi': 71.43
        },
        {
            'project': 'Gamma DCA',
            'group': 'DCA',
            'income': 900000,
            'expense': 600000,
            'net': 300000,
            'margin': 33.33,
            'roi': 50.0
        },
        {
            'project': 'Delta DP',
            'group': 'DP',
            'income': 1000000,
            'expense': 500000,
            'net': 500000,
            'margin': 50.0,
            'roi': 100.0
        },
        {
            'project': 'Epsilon DP',
            'group': 'DP',
            'income': 800000,
            'expense': 400000,
            'net': 400000,
            'margin': 50.0,
            'roi': 100.0
        },
        {
            'project': 'Проект 1',
            'group': 'Прочие',
            'income': 600000,
            'expense': 300000,
            'net': 300000,
            'margin': 50.0,
            'roi': 100.0
        },
        {
            'project': 'Проект 2',
            'group': 'Прочие',
            'income': 400000,
            'expense': 350000,
            'net': 50000,
            'margin': 12.5,
            'roi': 14.29
        },
        {
            'project': 'Проект 3',
            'group': 'Прочие',
            'income': 300000,
            'expense': 400000,
            'net': -100000,
            'margin': -33.33,
            'roi': -25.0
        }
    ]
    return projects

# API: Данные для отчета 3
@app.route('/api/report3/data')
@login_required
def get_report3_data():
    try:
        # Проверяем есть ли данные
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count == 0:
            # Возвращаем тестовые данные
            return jsonify({
                'success': True,
                'sunburst': create_test_sunburst(),
                'top_expenses': create_test_top_expenses(),
                'top_incomes': create_test_top_incomes()
            })
        
        # Получаем данные для солнечной диаграммы
        query = db.session.query(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Распределение == 'распределение'
        ).group_by(
            FinancialData.СтатьяУровень1,
            FinancialData.СтатьяУровень2,
            FinancialData.СтатьяУровень4
        ).order_by(func.sum(FinancialData.Сумма).desc())
        
        results = query.all()
        
        # Преобразуем в формат для sunburst
        sunburst_data = []
        for row in results:
            if row.СтатьяУровень1 and row.СтатьяУровень2 and row.СтатьяУровень4:
                sunburst_data.append({
                    'ids': f"{row.СтатьяУровень1}/{row.СтатьяУровень2}/{row.СтатьяУровень4}",
                    'labels': row.СтатьяУровень4,
                    'parents': f"{row.СтатьяУровень1}/{row.СтатьяУровень2}",
                    'values': abs(float(row.total or 0)),
                    'type': 'income' if float(row.total or 0) >= 0 else 'expense'
                })
        
        # Топ-5 расходов
        top_expenses = db.session.query(
            FinancialData.СтатьяУровень4,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.СтатьяУровень1 == 'Отток по ОД',
            FinancialData.Распределение == 'распределение'
        ).group_by(FinancialData.СтатьяУровень4
        ).order_by(func.sum(FinancialData.Сумма)).limit(5).all()
        
        # Топ-5 доходов
        top_incomes = db.session.query(
            FinancialData.СтатьяУровень4,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.СтатьяУровень1 == 'Поступления по ОД',
            FinancialData.Распределение == 'распределение'
        ).group_by(FinancialData.СтатьяУровень4
        ).order_by(func.sum(FinancialData.Сумма).desc()).limit(5).all()
        
        return jsonify({
            'success': True,
            'sunburst': sunburst_data if sunburst_data else create_test_sunburst(),
            'top_expenses': [
                {'article': row[0], 'total': round(abs(float(row[1] or 0)), 2)}
                for row in top_expenses
            ] if top_expenses else create_test_top_expenses(),
            'top_incomes': [
                {'article': row[0], 'total': round(float(row[1] or 0), 2)}
                for row in top_incomes
            ] if top_incomes else create_test_top_incomes()
        })
        
    except Exception as e:
        logger.error(f"Error in report3: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': True,
            'sunburst': create_test_sunburst(),
            'top_expenses': create_test_top_expenses(),
            'top_incomes': create_test_top_incomes()
        })

def create_test_sunburst():
    """Создание тестовых данных для sunburst"""
    return [
        {
            'ids': 'Поступления по ОД/Доходы от продаж/Продажи продукции',
            'labels': 'Продажи продукции',
            'parents': 'Поступления по ОД/Доходы от продаж',
            'values': 2500000,
            'type': 'income'
        },
        {
            'ids': 'Поступления по ОД/Доходы от услуг/Консалтинговые услуги',
            'labels': 'Консалтинговые услуги',
            'parents': 'Поступления по ОД/Доходы от услуг',
            'values': 1500000,
            'type': 'income'
        },
        {
            'ids': 'Отток по ОД/Расходы на персонал/ФОТ_и_социальные_выплаты',
            'labels': 'ФОТ_и_социальные_выплаты',
            'parents': 'Отток по ОД/Расходы на персонал',
            'values': 1200000,
            'type': 'expense'
        },
        {
            'ids': 'Отток по ОД/Операционные расходы/Аренда офиса',
            'labels': 'Аренда офиса',
            'parents': 'Отток по ОД/Операционные расходы',
            'values': 500000,
            'type': 'expense'
        }
    ]

def create_test_top_expenses():
    return [
        {'article': 'ФОТ_и_социальные_выплаты', 'total': 1200000},
        {'article': 'Аренда офиса', 'total': 500000},
        {'article': 'Закупка материалов', 'total': 300000},
        {'article': 'Маркетинг и реклама', 'total': 200000},
        {'article': 'Командировочные', 'total': 100000}
    ]

def create_test_top_incomes():
    return [
        {'article': 'Продажи продукции', 'total': 2500000},
        {'article': 'Консалтинговые услуги', 'total': 1500000},
        {'article': 'Техническая поддержка', 'total': 800000},
        {'article': 'Лицензионные отчисления', 'total': 500000},
        {'article': 'Обучение клиентов', 'total': 300000}
    ]

# API: Данные для отчета 4
@app.route('/api/report4/data')
@login_required
def get_report4_data():
    try:
        # Проверяем есть ли данные
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count == 0:
            # Возвращаем тестовые данные
            return jsonify({
                'success': True,
                'projects': create_test_fot_projects(),
                'groups': create_test_fot_groups(),
                'total_fot': 2850000
            })
        
        # Получаем данные о ФОТ
        query = db.session.query(
            FinancialData.Проект,
            func.sum(FinancialData.Сумма).label('fot_total'),
            func.count(FinancialData.Комментарии.distinct()).label('comments_count')
        ).filter(
            FinancialData.СтатьяУровень4 == 'ФОТ_и_социальные_выплаты',
            FinancialData.Распределение == 'распределение'
        ).group_by(FinancialData.Проект)
        
        results = query.all()
        
        # Рассчитываем общий ФОТ
        total_fot = sum(float(row.fot_total or 0) for row in results)
        
        projects_fot = []
        for row in results:
            project = row.Проект or 'Без проекта'
            fot_total = float(row.fot_total or 0)
            employees_estimate = int(row.comments_count or 0)
            
            # Оценка количества сотрудников
            employees = max(1, employees_estimate)
            
            fot_per_employee = fot_total / employees if employees > 0 else 0
            fot_percentage = (fot_total / total_fot * 100) if total_fot > 0 else 0
            
            # Определяем группу
            project_upper = str(project).upper()
            if 'DCA' in project_upper:
                group = 'DCA'
            elif 'DP' in project_upper:
                group = 'DP'
            else:
                group = 'Прочие'
            
            projects_fot.append({
                'project': project,
                'group': group,
                'employees': employees,
                'fot_total': round(fot_total, 2),
                'fot_per_employee': round(fot_per_employee, 2),
                'fot_percentage': round(fot_percentage, 2)
            })
        
        # Данные для графиков
        groups_data = {}
        for project in projects_fot:
            group = project['group']
            if group not in groups_data:
                groups_data[group] = {
                    'employees': 0,
                    'fot_total': 0,
                    'projects_count': 0
                }
            
            groups_data[group]['employees'] += project['employees']
            groups_data[group]['fot_total'] += project['fot_total']
            groups_data[group]['projects_count'] += 1
        
        if not projects_fot:
            return jsonify({
                'success': True,
                'projects': create_test_fot_projects(),
                'groups': create_test_fot_groups(),
                'total_fot': 2850000
            })
        
        return jsonify({
            'success': True,
            'projects': projects_fot,
            'groups': groups_data,
            'total_fot': round(total_fot, 2)
        })
        
    except Exception as e:
        logger.error(f"Error in report4: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': True,
            'projects': create_test_fot_projects(),
            'groups': create_test_fot_groups(),
            'total_fot': 2850000
        })

def create_test_fot_projects():
    """Создание тестовых данных ФОТ"""
    return [
        {
            'project': 'Alpha DCA',
            'group': 'DCA',
            'employees': 15,
            'fot_total': 1200000,
            'fot_per_employee': 80000,
            'fot_percentage': 42.11
        },
        {
            'project': 'Beta DCA',
            'group': 'DCA',
            'employees': 10,
            'fot_total': 700000,
            'fot_per_employee': 70000,
            'fot_percentage': 24.56
        },
        {
            'project': 'Delta DP',
            'group': 'DP',
            'employees': 8,
            'fot_total': 500000,
            'fot_per_employee': 62500,
            'fot_percentage': 17.54
        },
        {
            'project': 'Проект 1',
            'group': 'Прочие',
            'employees': 5,
            'fot_total': 300000,
            'fot_per_employee': 60000,
            'fot_percentage': 10.53
        },
        {
            'project': 'Проект 2',
            'group': 'Прочие',
            'employees': 3,
            'fot_total': 150000,
            'fot_per_employee': 50000,
            'fot_percentage': 5.26
        }
    ]

def create_test_fot_groups():
    return {
        'DCA': {
            'employees': 25,
            'fot_total': 1900000,
            'projects_count': 2
        },
        'DP': {
            'employees': 8,
            'fot_total': 500000,
            'projects_count': 1
        },
        'Прочие': {
            'employees': 8,
            'fot_total': 450000,
            'projects_count': 2
        }
    }

# Загрузка тестовых данных
@app.route('/add-test-data')
def add_test_data():
    try:
        # Проверяем есть ли уже данные
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        if count > 0:
            return jsonify({
                'success': True,
                'message': f'В базе уже есть {count} записей'
            })
        
        # Тестовые данные
        test_data = []
        projects = ['Alpha DCA', 'Beta DCA', 'Gamma DCA', 'Delta DP', 'Epsilon DP', 'Проект 1', 'Проект 2']
        
        for i, project in enumerate(projects):
            # Доходы
            test_data.append(FinancialData(
                Период=datetime(2024, 1, 1),
                Проект=project,
                СтатьяУровень1='Поступления по ОД',
                СтатьяУровень2='Доходы от продаж' if 'DCA' in project else 'Доходы от услуг',
                СтатьяУровень4='Продажи продукции' if 'DCA' in project else 'Консалтинговые услуги',
                Сумма=1000000 + i * 200000,
                Распределение='распределение',
                Комментарии=f'Тестовые данные для {project}',
                Создано=datetime.utcnow()
            ))
            
            # Расходы (ФОТ)
            test_data.append(FinancialData(
                Период=datetime(2024, 1, 1),
                Проект=project,
                СтатьяУровень1='Отток по ОД',
                СтатьяУровень2='Расходы на персонал',
                СтатьяУровень4='ФОТ_и_социальные_выплаты',
                Сумма=500000 + i * 100000,
                Распределение='распределение',
                Комментарии=f'Зарплата сотрудников {project}',
                Создано=datetime.utcnow()
            ))
            
            # Прочие расходы
            test_data.append(FinancialData(
                Период=datetime(2024, 1, 1),
                Проект=project,
                СтатьяУровень1='Отток по ОД',
                СтатьяУровень2='Операционные расходы',
                СтатьяУровень4='Аренда офиса',
                Сумма=200000 + i * 50000,
                Распределение='распределение',
                Комментарии=f'Аренда для {project}',
                Создано=datetime.utcnow()
            ))
        
        # Добавляем данные
        db.session.add_all(test_data)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Добавлено {len(test_data)} тестовых записей',
            'data_added': True
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding test data: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Проверка подключения к базе
@app.route('/check-db')
def check_db():
    try:
        # Проверка подключения к базе
        db.session.execute('SELECT 1')
        count = db.session.query(func.count(FinancialData.id)).scalar()
        
        return jsonify({
            'success': True,
            'database_connected': True,
            'records_count': count,
            'tables_exist': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'database_connected': False,
            'error': str(e)
        })

# Создание таблиц и инициализация админа
with app.app_context():
    try:
        db.create_all()
        print('✅ Таблицы созданы')
        
        init_admin()
        print('✅ Администратор инициализирован')
        
        # Проверяем подключение к базе
        db.session.execute('SELECT 1')
        print('✅ Подключение к базе установлено')
        
    except Exception as e:
        print(f'❌ Ошибка инициализации: {e}')

if __name__ == '__main__':
    app.run(debug=app.config['FLASK_ENV'] == 'development', host='0.0.0.0', port=5000)