# Аналитика эффективности проектов

Веб-приложение для мониторинга эффективности проектов с аналитикой финансовых показателей.

## 📊 Возможности

### Отчет 1: Эффективность выбранных проектов
- Выбор проектов с группировкой: DCA, DP, Прочие
- Древовидная структура с раскрытием уровней (Уровень1 → Уровень2 → Уровень4)
- Расчет ROI и маржинальности
- ТОП-10 расходных статей для проектов с отрицательным результатом

### Отчет 2: Сводные показатели
- Таблица всех проектов с ключевыми метриками
- Графики: распределение ROI, группы проектов, динамика по месяцам
- Общая статистика и тренды

### Отчет 3: Анализ статей расходов/доходов
- Солнечная диаграмма распределения по статьям
- ТОП-5 доходных и расходных статей
- Детальная таблица всех статей

### Отчет 4: Анализ ФОТ и сотрудников
- Распределение ФОТ по проектам
- Количество сотрудников на проектах
- Эффективность ФОТ относительно результатов

## 🚀 Быстрый старт

### 1. Локальная разработка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd finance-analytics

# Запустить через Docker
docker-compose up -d

# Или вручную
cd backend
pip install -r requirements.txt
python main.py

# Фронтенд (открыть в браузере)
open frontend/index.html

services:
  - type: web
    name: finance-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: finance-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true

  - type: web
    name: finance-frontend
    env: static
    buildCommand: npm run build
    staticPublishPath: ./build
    routes:
      - type: rewrite
        source: /api/*
        destination: https://finance-backend.onrender.com/api/*

databases:
  - name: finance-db
    databaseName: finance_db
    user: finance_user# Alfa_Report
# Alfa_Report