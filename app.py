from flask import Flask, render_template, jsonify, request, session
from flask_login import LoginManager, login_required, current_user
from config import Config
from database import db
from models import User, FinancialData
from auth import auth_bp, init_admin
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, case, and_, or_
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

# API: Получение проектов
@app.route('/api/projects')
@login_required
def get_projects():
    try:
        projects_query = db.session.query(
            FinancialData.Проект
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != ''
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
        
    except Exception as e:
        logger.error(f"Error in get_projects: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API: Данные для отчета 1 (Эффективность проектов)
@app.route('/api/report1/data', methods=['POST'])
@login_required
def get_report1_data():
    try:
        data = request.get_json()
        projects = data.get('projects', [])
        period_from = data.get('period_from')
        period_to = data.get('period_to')
        
        if not projects:
            return jsonify({'success': False, 'error': 'Не выбраны проекты'}), 400
        
        # Преобразуем даты
        try:
            date_from = datetime.strptime(period_from, '%Y-%m-%d')
            date_to = datetime.strptime(period_to, '%Y-%m-%d')
        except:
            today = datetime.now()
            date_from = datetime(today.year, today.month, 1)
            date_to = datetime(today.year, today.month, 1) + timedelta(days=32)
            date_to = datetime(date_to.year, date_to.month, 1) - timedelta(days=1)
        
        # Сохраняем период в сессии для других запросов
        session['report1_period_from'] = period_from
        session['report1_period_to'] = period_to
        
        # Запрос данных по иерархии статей
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
            
            hierarchy[level1][level2][level4][row.Проект] = float(row.total or 0)
        
        # Рассчитываем метрики ROI и маржинальность
        # Для вашей структуры используем поле "Поток" для определения доходов/расходов
        metrics_query = db.session.query(
            FinancialData.Проект,
            func.sum(
                case(
                    (FinancialData.Поток == 'Поступления', FinancialData.Сумма),
                    else_=0
                )
            ).label('income'),
            func.sum(
                case(
                    (FinancialData.Поток == 'Отток', FinancialData.Сумма),
                    else_=0
                )
            ).label('expense')
        ).filter(
            FinancialData.Проект.in_(projects),
            FinancialData.Период.between(date_from, date_to),
            FinancialData.Распределение == 'распределение'
        ).group_by(FinancialData.Проект)
        
        metrics_results = metrics_query.all()
        
        metrics = {}
        for row in metrics_results:
            income = float(row.income or 0)
            expense = float(row.expense or 0)
            net = income - expense
            
            margin = ((income - expense) / income * 100) if income > 0 else 0
            roi = ((income - expense) / expense * 100) if expense > 0 else 0
            
            metrics[row.Проект] = {
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
            'hierarchy': hierarchy,
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"Error in report1: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: ТОП-10 расходов для проекта
@app.route('/api/top_expenses/<project>')
@login_required
def get_top_expenses(project):
    try:
        # Получаем период из сессии
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
            FinancialData.Поток == 'Отток',  # Только оттоки (расходы)
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
        
        return jsonify({'success': True, 'expenses': expenses})
        
    except Exception as e:
        logger.error(f"Error getting top expenses: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Данные для отчета 2 (Сводная таблица)
@app.route('/api/report2/data')
@login_required
def get_report2_data():
    try:
        # Рассчитываем метрики для всех проектов
        query = db.session.query(
            FinancialData.Проект,
            func.sum(
                case(
                    (FinancialData.Поток == 'Поступления', FinancialData.Сумма),
                    else_=0
                )
            ).label('income'),
            func.sum(
                case(
                    (FinancialData.Поток == 'Отток', FinancialData.Сумма),
                    else_=0
                )
            ).label('expense')
        ).filter(
            FinancialData.Проект.isnot(None),
            FinancialData.Проект != '',
            FinancialData.Распределение == 'распределение'
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

# API: Данные для отчета 3 (Анализ статей)
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
        )
        
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
            FinancialData.Поток == 'Отток',
            FinancialData.Распределение == 'распределение'
        ).group_by(FinancialData.СтатьяУровень4
        ).order_by(func.sum(FinancialData.Сумма).desc()).limit(5).all()
        
        # Топ-5 доходов
        top_incomes = db.session.query(
            FinancialData.СтатьяУровень4,
            func.sum(FinancialData.Сумма).label('total')
        ).filter(
            FinancialData.Поток == 'Поступления',
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

# API: Данные для отчета 4 (Анализ ФОТ)
@app.route('/api/report4/data')
@login_required
def get_report4_data():
    try:
        # Получаем данные о ФОТ (ищем статьи связанные с ФОТ)
        query = db.session.query(
            FinancialData.Проект,
            func.sum(FinancialData.Сумма).label('fot_total')
        ).filter(
            or_(
                FinancialData.СтатьяУровень4.ilike('%ФОТ%'),
                FinancialData.СтатьяУровень4.ilike('%зарплат%'),
                FinancialData.СтатьяУровень4.ilike('%сотрудник%'),
                FinancialData.СтатьяУровень4.ilike('%персонал%')
            ),
            FinancialData.Распределение == 'распределение',
            FinancialData.Поток == 'Отток'  # ФОТ - это расход
        ).group_by(FinancialData.Проект)
        
        results = query.all()
        
        # Рассчитываем общий ФОТ
        total_fot = sum(float(row.fot_total or 0) for row in results)
        
        projects_fot = []
        for row in results:
            project = row.Проект
            fot_total = float(row.fot_total or 0)
            
            # Оценка количества сотрудников (по среднему ФОТ 70к)
            employees = max(1, int(fot_total / 70000))
            
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

# Проверка подключения и данных
@app.route('/check-db')
def check_db():
    try:
        # Проверка подключения
        db.session.execute('SELECT 1')
        
        # Получаем статистику
        total_records = db.session.query(func.count(FinancialData.id)).scalar()
        total_projects = db.session.query(FinancialData.Проект).distinct().count()
        date_range = db.session.query(
            func.min(FinancialData.Период),
            func.max(FinancialData.Период)
        ).first()
        
        return jsonify({
            'success': True,
            'database_connected': True,
            'records_count': total_records,
            'projects_count': total_projects,
            'date_range': {
                'min': date_range[0].strftime('%Y-%m-%d') if date_range[0] else None,
                'max': date_range[1].strftime('%Y-%m-%d') if date_range[1] else None
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Создание таблиц и инициализация админа
with app.app_context():
    try:
        # Создаем только таблицу users (FinancialData уже существует)
        db.create_all()
        print('✅ Таблица users создана')
        
        init_admin()
        print('✅ Администратор инициализирован')
        
        # Проверяем подключение к базе
        db.session.execute('SELECT 1')
        print('✅ Подключение к базе установлено')
        
    except Exception as e:
        print(f'❌ Ошибка инициализации: {e}')

if __name__ == '__main__':
    app.run(debug=app.config['FLASK_ENV'] == 'development', host='0.0.0.0', port=5000)