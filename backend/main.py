from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case, and_, or_
from typing import List, Optional
from datetime import datetime, date
import models
from database import get_db, engine
from auth import get_current_user, get_current_admin, get_password_hash
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаем таблицы при старте
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Finance Analytics API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Аутентификация ===
@app.post("/api/register")
async def register_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: models.User = Depends(get_current_admin)
):
    # Проверяем существование пользователя
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Создаем пользователя
    user = models.User(
        username=username,
        password_hash=get_password_hash(password),
        email=email,
        role="user"
    )
    db.add(user)
    await db.commit()
    return {"message": "User created successfully"}

@app.post("/api/login")
async def login(
    username: str,
    password: str,
    db: AsyncSession = Depends(get_db)
):
    from auth import verify_password, create_access_token
    
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "role": user.role
        }
    }

# === ОТЧЕТ 1: Эффективность выбранных проектов ===
@app.post("/api/report1/projects")
async def get_projects_with_groups(
    db: AsyncSession = Depends(get_db)
):
    """Получить список проектов с группировкой"""
    result = await db.execute(
        select(models.FinanceData.проект).distinct()
    )
    projects = [row[0] for row in result.all() if row[0]]
    
    # Группируем проекты
    grouped = {
        "DCA": [],
        "DP": [],
        "Прочие": []
    }
    
    for project in projects:
        if "DCA" in project.upper():
            grouped["DCA"].append(project)
        elif "DP" in project.upper():
            grouped["DP"].append(project)
        else:
            grouped["Прочие"].append(project)
    
    return grouped

@app.post("/api/report1/tree")
async def get_project_tree(
    project_names: List[str],
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Получить дерево данных для проектов"""
    # Получаем данные для выбранных проектов
    result = await db.execute(
        select(
            models.FinanceData.проект,
            models.FinanceData.статьяуровень1,
            models.FinanceData.статьяуровень2,
            models.FinanceData.статьяуровень4,
            func.sum(models.FinanceData.сумма).label("сумма"),
            func.count(models.FinanceData.комментарии.distinct()).label("комментарии_кол")
        )
        .where(
            and_(
                models.FinanceData.проект.in_(project_names),
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение"
            )
        )
        .group_by(
            models.FinanceData.проект,
            models.FinanceData.статьяуровень1,
            models.FinanceData.статьяуровень2,
            models.FinanceData.статьяуровень4
        )
        .order_by(
            models.FinanceData.проект,
            models.FinanceData.статьяуровень1,
            models.FinanceData.статьяуровень2,
            models.FinanceData.статьяуровень4
        )
    )
    
    rows = result.all()
    
    # Строим дерево
    tree = {}
    for row in rows:
        project = row.проект
        level1 = row.статьяуровень1 or "Без категории"
        level2 = row.статьяуровень2 or "Без подкатегории"
        level4 = row.статьяуровень4 or "Без статьи"
        
        if project not in tree:
            tree[project] = {}
        
        if level1 not in tree[project]:
            tree[project][level1] = {}
        
        if level2 not in tree[project][level1]:
            tree[project][level1][level2] = []
        
        tree[project][level1][level2].append({
            "article": level4,
            "amount": row.сумма,
            "comments_count": row.комментарии_кол
        })
    
    return tree

@app.post("/api/report1/metrics")
async def calculate_project_metrics(
    project_names: List[str],
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Рассчитать ROI и маржинальность для проектов"""
    # Рассчитываем поступления и отток по ОД
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Поступления по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("поступления"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("отток")
        )
        .where(
            and_(
                models.FinanceData.проект.in_(project_names),
                models.FinanceData.период.between(start_date, end_date)
            )
        )
        .group_by(models.FinanceData.проект)
    )
    
    metrics = []
    for row in result.all():
        поступления = row.поступления or 0
        отток = row.отток or 0
        результат_од = поступления - отток
        
        roi = (результат_од / отток * 100) if отток != 0 else 0
        маржинальность = (результат_од / поступления * 100) if поступления != 0 else 0
        
        # Определяем группу проекта
        if "DCA" in row.проект.upper():
            группа = "DCA"
        elif "DP" in row.проект.upper():
            группа = "DP"
        else:
            группа = "Прочие"
        
        metrics.append({
            "проект": row.проект,
            "группа": группа,
            "roi": round(roi, 2),
            "маржинальность": round(маржинальность, 2),
            "поступления": поступления,
            "отток": отток,
            "результат_од": результат_од,
            "отрицательный": результат_од < 0
        })
    
    return metrics

@app.get("/api/report1/top-expenses")
async def get_top_expenses(
    project: str,
    start_date: date,
    end_date: date,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Получить ТОП-10 расходных статей для проекта"""
    result = await db.execute(
        select(
            models.FinanceData.статьяуровень4,
            models.FinanceData.статьяуровень2,
            func.sum(models.FinanceData.сумма).label("сумма"),
            func.string_agg(models.FinanceData.комментарии.distinct(), ', ').label("комментарии")
        )
        .where(
            and_(
                models.FinanceData.проект == project,
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.статьяуровень1 == "Отток по ОД",
                models.FinanceData.распределение == "распределение"
            )
        )
        .group_by(
            models.FinanceData.статьяуровень4,
            models.FinanceData.статьяуровень2
        )
        .order_by(func.sum(models.FinanceData.сумма).desc())
        .limit(limit)
    )
    
    expenses = []
    for row in result.all():
        expenses.append({
            "статья": row.статьяуровень4 or "Без названия",
            "категория": row.статьяуровень2 or "Без категории",
            "сумма": row.сумма,
            "комментарии": row.комментарии[:100] if row.комментарии else ""
        })
    
    return expenses

# === ОТЧЕТ 2: Сводная таблица всех проектов ===
@app.get("/api/report2/summary")
async def get_all_projects_summary(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Сводная информация по всем проектам"""
    # Основные метрики по проектам
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1.in_(["Поступления по ОД", "Результат по ИД", "Финансы"]),
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), -models.FinanceData.сумма),
                    else_=0
                )
            ).label("чистый_результат"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Поступления по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("поступления"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("отток"),
            func.count(models.FinanceData.комментарии.distinct()).label("комментарии_кол")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.проект.isnot(None)
            )
        )
        .group_by(models.FinanceData.проект)
        .order_by(
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1.in_(["Поступления по ОД", "Результат по ИД", "Финансы"]),
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), -models.FinanceData.сумма),
                    else_=0
                )
            ).desc()
        )
    )
    
    projects = []
    for row in result.all():
        поступления = row.поступления or 0
        отток = row.отток or 0
        чистый = row.чистый_результат or 0
        
        roi = ((поступления - отток) / отток * 100) if отток != 0 else 0
        маржинальность = ((поступления - отток) / поступления * 100) if поступления != 0 else 0
        
        # Определяем группу
        if "DCA" in row.проект.upper():
            группа = "DCA"
        elif "DP" in row.проект.upper():
            группа = "DP"
        else:
            группа = "Прочие"
        
        projects.append({
            "проект": row.проект,
            "группа": группа,
            "roi": round(roi, 2),
            "маржинальность": round(маржинальность, 2),
            "поступления": поступления,
            "отток": отток,
            "чистый_результат": чистый,
            "комментарии_кол": row.комментарии_кол
        })
    
    # Общая статистика
    total_metrics = {
        "total_projects": len(projects),
        "total_revenue": sum(p["поступления"] for p in projects),
        "total_expenses": sum(p["отток"] for p in projects),
        "total_net": sum(p["чистый_результат"] for p in projects),
        "avg_roi": round(sum(p["roi"] for p in projects) / len(projects) if projects else 0, 2),
        "avg_margin": round(sum(p["маржинальность"] for p in projects) / len(projects) if projects else 0, 2)
    }
    
    # Распределение по группам
    groups_distribution = {}
    for project in projects:
        group = project["группа"]
        if group not in groups_distribution:
            groups_distribution[group] = {"count": 0, "revenue": 0, "profit": 0}
        groups_distribution[group]["count"] += 1
        groups_distribution[group]["revenue"] += project["поступления"]
        groups_distribution[group]["profit"] += project["чистый_результат"]
    
    return {
        "projects": projects,
        "total_metrics": total_metrics,
        "groups_distribution": groups_distribution
    }

@app.get("/api/report2/monthly-trend")
async def get_monthly_trend(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Динамика по месяцам"""
    result = await db.execute(
        select(
            func.date_trunc('month', models.FinanceData.период).label("месяц"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Поступления по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("поступления"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("отток")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.проект.isnot(None)
            )
        )
        .group_by(func.date_trunc('month', models.FinanceData.период))
        .order_by(func.date_trunc('month', models.FinanceData.период))
    )
    
    trend = []
    for row in result.all():
        поступления = row.поступления or 0
        отток = row.отток or 0
        чистый = поступления - отток
        маржинальность = (чистый / поступления * 100) if поступления != 0 else 0
        
        trend.append({
            "месяц": row.месяц.strftime("%Y-%m"),
            "поступления": поступления,
            "отток": отток,
            "чистый": чистый,
            "маржинальность": round(маржинальность, 2)
        })
    
    return trend

# === ОТЧЕТ 3: Анализ статей расходов/доходов ===
@app.get("/api/report3/articles-analysis")
async def analyze_articles(
    start_date: date,
    end_date: date,
    article_type: Optional[str] = None,  # "доходы" или "расходы"
    db: AsyncSession = Depends(get_db)
):
    """Анализ статей расходов и доходов"""
    
    # Определяем условия для типа статей
    if article_type == "доходы":
        level1_filter = "Поступления по ОД"
    elif article_type == "расходы":
        level1_filter = "Отток по ОД"
    else:
        level1_filter = None
    
    where_conditions = [
        models.FinanceData.период.between(start_date, end_date),
        models.FinanceData.распределение == "распределение"
    ]
    
    if level1_filter:
        where_conditions.append(models.FinanceData.статьяуровень1 == level1_filter)
    
    # Получаем данные по статьям
    result = await db.execute(
        select(
            models.FinanceData.статьяуровень1,
            models.FinanceData.статьяуровень2,
            models.FinanceData.статьяуровень4,
            func.sum(models.FinanceData.сумма).label("сумма"),
            func.count().label("количество_записей")
        )
        .where(and_(*where_conditions))
        .group_by(
            models.FinanceData.статьяуровень1,
            models.FinanceData.статьяуровень2,
            models.FinanceData.статьяуровень4
        )
        .order_by(func.sum(models.FinanceData.сумма).desc())
    )
    
    articles = []
    for row in result.all():
        articles.append({
            "уровень1": row.статьяуровень1 or "Без уровня",
            "уровень2": row.статьяуровень2 or "Без подкатегории",
            "уровень4": row.статьяуровень4 or "Без статьи",
            "сумма": row.сумма,
            "количество": row.количество_записей
        })
    
    # Топ-5 статей по доходам
    top_income_result = await db.execute(
        select(
            models.FinanceData.статьяуровень4,
            func.sum(models.FinanceData.сумма).label("сумма")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.статьяуровень1 == "Поступления по ОД"
            )
        )
        .group_by(models.FinanceData.статьяуровень4)
        .order_by(func.sum(models.FinanceData.сумма).desc())
        .limit(5)
    )
    
    top_income = [{"статья": r[0] or "Без статьи", "сумма": r[1]} for r in top_income_result.all()]
    
    # Топ-5 статей по расходам
    top_expense_result = await db.execute(
        select(
            models.FinanceData.статьяуровень4,
            func.sum(models.FinanceData.сумма).label("сумма")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.статьяуровень1 == "Отток по ОД"
            )
        )
        .group_by(models.FinanceData.статьяуровень4)
        .order_by(func.sum(models.FinanceData.сумма).desc())
        .limit(5)
    )
    
    top_expense = [{"статья": r[0] or "Без статьи", "сумма": r[1]} for r in top_expense_result.all()]
    
    return {
        "all_articles": articles,
        "top_income": top_income,
        "top_expense": top_expense,
        "total_income": sum(item["сумма"] for item in top_income),
        "total_expense": sum(item["сумма"] for item in top_expense)
    }

# === ОТЧЕТ 4: Анализ ФОТ и сотрудников ===
@app.get("/api/report4/fot-analysis")
async def analyze_fot(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Анализ ФОТ и сотрудников по проектам"""
    
    # Получаем данные по ФОТ
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(models.FinanceData.сумма).label("фот_сумма"),
            func.count(models.FinanceData.комментарии.distinct()).label("сотрудники_кол")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.статьяуровень4 == "ФОТ_и_социальные_выплаты"
            )
        )
        .group_by(models.FinanceData.проект)
        .order_by(func.sum(models.FinanceData.сумма).desc())
    )
    
    fot_data = []
    total_fot = 0
    total_employees = 0
    
    for row in result.all():
        if row.проект:
            фот_сумма = row.фот_сумма or 0
            сотрудники_кол = row.сотрудники_кол or 1  # минимум 1 сотрудник
            фот_на_сотрудника = фот_сумма / сотрудники_кол
            
            # Определяем группу проекта
            if "DCA" in row.проект.upper():
                группа = "DCA"
            elif "DP" in row.проект.upper():
                группа = "DP"
            else:
                группа = "Прочие"
            
            fot_data.append({
                "проект": row.проект,
                "группа": группа,
                "фот_сумма": фот_сумма,
                "сотрудники_кол": сотрудники_кол,
                "фот_на_сотрудника": round(фот_на_сотрудника, 2)
            })
            
            total_fot += фот_сумма
            total_employees += сотрудники_кол
    
    # Рассчитываем проценты
    for item in fot_data:
        item["процент_от_общего"] = round((item["фот_сумма"] / total_fot * 100) if total_fot > 0 else 0, 2)
    
    # Получаем общие результаты по проектам для расчета эффективности ФОТ
    projects_result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1.in_(["Поступления по ОД", "Результат по ИД", "Финансы"]),
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), -models.FinanceData.сумма),
                    else_=0
                )
            ).label("чистый_результат")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.проект.isnot(None)
            )
        )
        .group_by(models.FinanceData.проект)
    )
    
    projects_profit = {row.проект: row.чистый_результат or 0 for row in projects_result.all()}
    
    # Объединяем данные ФОТ с результатами
    for item in fot_data:
        проект = item["проект"]
        фот_сумма = item["фот_сумма"]
        прибыль = projects_profit.get(проект, 0)
        
        item["результат"] = прибыль
        item["фот_к_результату"] = round((прибыль / фот_сумма * 100) if фот_сумма != 0 else 0, 2)
    
    # Динамика ФОТ по месяцам
    monthly_fot_result = await db.execute(
        select(
            func.date_trunc('month', models.FinanceData.период).label("месяц"),
            func.sum(models.FinanceData.сумма).label("фот_сумма")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.статьяуровень4 == "ФОТ_и_социальные_выплаты"
            )
        )
        .group_by(func.date_trunc('month', models.FinanceData.период))
        .order_by(func.date_trunc('month', models.FinanceData.период))
    )
    
    monthly_fot = []
    for row in monthly_fot_result.all():
        monthly_fot.append({
            "месяц": row.месяц.strftime("%Y-%m"),
            "фот_сумма": row.фот_сумма or 0
        })
    
    return {
        "fot_data": fot_data,
        "monthly_fot": monthly_fot,
        "total_metrics": {
            "total_fot": total_fot,
            "total_employees": total_employees,
            "avg_fot_per_employee": round(total_fot / total_employees if total_employees > 0 else 0, 2),
            "total_projects_with_fot": len(fot_data)
        }
    }

@app.get("/api/report4/employee-distribution")
async def get_employee_distribution(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Распределение сотрудников по проектам"""
    # Извлекаем имена сотрудников из комментариев
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.string_agg(models.FinanceData.комментарии.distinct(), ', ').label("комментарии")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.распределение == "распределение",
                models.FinanceData.комментарии.isnot(None),
                models.FinanceData.комментарии != ''
            )
        )
        .group_by(models.FinanceData.проект)
    )
    
    distribution = []
    for row in result.all():
        if row.проект and row.комментарии:
            # Простая эвристика для подсчета сотрудников
            # Предполагаем, что комментарии содержат имена сотрудников
            comments = row.комментарии.split(', ')
            unique_names = set()
            
            for comment in comments:
                # Извлекаем возможное имя из комментария
                parts = comment.split(':')
                if parts and parts[0].strip():
                    name = parts[0].strip()
                    if len(name) > 2 and name[0].isupper():
                        unique_names.add(name)
            
            if unique_names:
                # Определяем группу проекта
                if "DCA" in row.проект.upper():
                    группа = "DCA"
                elif "DP" in row.проект.upper():
                    группа = "DP"
                else:
                    группа = "Прочие"
                
                distribution.append({
                    "проект": row.проект,
                    "группа": группа,
                    "сотрудники": list(unique_names),
                    "сотрудники_кол": len(unique_names)
                })
    
    # Сортируем по количеству сотрудников
    distribution.sort(key=lambda x: x["сотрудники_кол"], reverse=True)
    
    return distribution

# === Графики и дополнительные данные ===
@app.get("/api/charts/roi-distribution")
async def get_roi_distribution(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Распределение ROI по проектам"""
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Поступления по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("поступления"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("отток")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.проект.isnot(None)
            )
        )
        .group_by(models.FinanceData.проект)
    )
    
    roi_data = []
    for row in result.all():
        поступления = row.поступления or 0
        отток = row.отток or 0
        if отток != 0:
            roi = ((поступления - отток) / отток * 100)
            
            # Определяем категорию ROI
            if roi >= 100:
                category = "> 100%"
            elif roi >= 50:
                category = "50-100%"
            elif roi >= 20:
                category = "20-50%"
            elif roi >= 0:
                category = "0-20%"
            elif roi >= -20:
                category = "-20-0%"
            else:
                category = "< -20%"
            
            if row.проект:
                roi_data.append({
                    "проект": row.проект,
                    "roi": round(roi, 2),
                    "category": category
                })
    
    return roi_data

@app.get("/api/charts/group-comparison")
async def get_group_comparison(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db)
):
    """Сравнение групп DCA, DP, Прочие"""
    result = await db.execute(
        select(
            models.FinanceData.проект,
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1.in_(["Поступления по ОД", "Результат по ИД", "Финансы"]),
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), -models.FinanceData.сумма),
                    else_=0
                )
            ).label("чистый_результат"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Поступления по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("поступления"),
            func.sum(
                case(
                    (and_(
                        models.FinanceData.статьяуровень1 == "Отток по ОД",
                        models.FinanceData.распределение == "распределение"
                    ), models.FinanceData.сумма),
                    else_=0
                )
            ).label("отток")
        )
        .where(
            and_(
                models.FinanceData.период.between(start_date, end_date),
                models.FinanceData.проект.isnot(None)
            )
        )
        .group_by(models.FinanceData.проект)
    )
    
    groups = {
        "DCA": {"проекты": 0, "поступления": 0, "отток": 0, "чистый": 0},
        "DP": {"проекты": 0, "поступления": 0, "отток": 0, "чистый": 0},
        "Прочие": {"проекты": 0, "поступления": 0, "отток": 0, "чистый": 0}
    }
    
    for row in result.all():
        if row.проект:
            if "DCA" in row.проект.upper():
                group = "DCA"
            elif "DP" in row.проект.upper():
                group = "DP"
            else:
                group = "Прочие"
            
            groups[group]["проекты"] += 1
            groups[group]["поступления"] += row.поступления or 0
            groups[group]["отток"] += row.отток or 0
            groups[group]["чистый"] += row.чистый_результат or 0
    
    # Рассчитываем дополнительные метрики
    for group in groups:
        data = groups[group]
        поступления = data["поступления"]
        отток = data["отток"]
        чистый = data["чистый"]
        
        data["roi"] = round((чистый / отток * 100) if отток != 0 else 0, 2)
        data["маржинальность"] = round((чистый / поступления * 100) if поступления != 0 else 0, 2)
        data["доля_от_общего"] = round((чистый / sum(g[1]["чистый"] for g in groups.items()) * 100) if any(g[1]["чистый"] != 0 for g in groups.items()) else 0, 2)
    
    return groups

# === Инициализация админа при первом запуске ===
@app.on_event("startup")
async def startup_event():
    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли админ
        result = await session.execute(
            select(models.User).where(models.User.username == "admin")
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            # Создаем админа
            from auth import get_password_hash
            admin_user = models.User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            print("Admin user created: username=admin, password=admin123")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)