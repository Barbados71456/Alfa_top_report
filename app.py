from flask import Flask, render_template, jsonify, request, session
from flask_login import login_required, current_user
from config import Config
from database import db
from models import FinancialData, User
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, case, and_, or_
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных
db.init_app(app)

# Регистрация blueprint
app.register_blueprint(auth_bp)

# Создание таблиц и инициализация админа
with app.app_context():
    db.create_all()
    init_admin()

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
    projects_query = db.session.query(
        FinancialData.Проект
    ).distinct().all()
    
    projects = [p[0] for p in projects_query if p[0]]
    
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

# API: Данные для отчета 1
@app.route('/api/report1/data', methods=['POST'])
@login_required
def get_report1_data():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        period_from = data.get('period_from')
        period_to = data.get('period_to')
        
        # Преобразуем даты
        try:
            date_from = datetime.strptime(period_from, '%Y-%m-%d')
            date_to = datetime.strptime(period_to, '%Y-%m-%d')
        except:
            # По умолчанию: текущий месяц
            today = datetime.now()
            date_from = datetime(today.year, today.month, 1)
            date_to = datetime(today.year, today.month, 1) + timedelta(days=32)
            date_to = datetime(date_to.year, date_to.month, 1) - timedelta(days=1)
        
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
            income = float(row.income or 0)
            expense = float(row.expense or 0)
            
            if income > 0:
                margin = ((income - expense) / income) * 100
            else:
                margin = 0
            
            if expense > 0:
                roi = ((income - expense) / expense) * 100
            else:
                roi = 0
            
            metrics[row.Проект] = {
                'margin': round(margin, 2),
                'roi': round(roi, 2),
                'income': round(income, 2),
                'expense': round(expense, 2),
                'net': round(income - expense, 2)
            }
        
        return jsonify({
            'success': True,
            'hierarchy': hierarchy,
            'metrics': metrics,
            'period': {
                'from': date_from.strftime('%Y-%m-%d'),
                'to': date_to.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        logger.error(f"Error in report1: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: ТОП-10 расходов для проекта
@app.route('/api/top_expenses/<project>')
@login_required
def get_top_expenses(project):
    try:
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
                'total': round(float(row.total or 0), 2)
            })
        
        return jsonify({'success': True, 'expenses': expenses})
        
    except Exception as e:
        logger.error(f"Error getting top expenses: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные для отчета 2
@app.route('/api/report2/data')
@login_required
def get_report2_data():
    try:
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
        
        # Сортируем по ROI
        projects_data.sort(key=lambda x: x['roi'], reverse=True)
        
        return jsonify({'success': True, 'projects': projects_data})
        
    except Exception as e:
        logger.error(f"Error in report2: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные для отчета 3
@app.route('/api/report3/data')
@login_required
def get_report3_data():
    try:
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
            'sunburst': sunburst_data,
            'top_expenses': [
                {'article': row[0], 'total': round(abs(float(row[1] or 0)), 2)}
                for row in top_expenses
            ],
            'top_incomes': [
                {'article': row[0], 'total': round(float(row[1] or 0), 2)}
                for row in top_incomes
            ]
        })
        
    except Exception as e:
        logger.error(f"Error in report3: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные для отчета 4
@app.route('/api/report4/data')
@login_required
def get_report4_data():
    try:
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
            
            # Оценка количества сотрудников (можно улучшить логику)
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
        
        return jsonify({
            'success': True,
            'projects': projects_fot,
            'groups': groups_data,
            'total_fot': round(total_fot, 2)
        })
        
    except Exception as e:
        logger.error(f"Error in report4: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=app.config['FLASK_ENV'] == 'development')