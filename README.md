# Alfa_top_report

Веб-дэшборд для топ-менеджмента: точная копия отчётных листов Свод1, Свод2, Dashboard1,
Dashboard2, UNIT+PL, ФОТ v1, ФОТ v2 из `02_Отчетность_..._fin.xlsx` + вкладка «Займы»
(как в Power BI `АльфаBI.pbix`), на основе БД `alfa_collection` (Render Postgres).

## Архитектура

Формулы Excel сводятся к `GROUP BY`/`SUM` над уже готовыми колонками
`public."FinancialData".("Строка отчета", "п_ф", "Проект", "Контрагент_report", "Контрагент")`
и `public.analiz_zaim` (займы) — см. разбор в `pl_report.py`/`fot_report.py`/`loans_report.py`.

Чтобы не грузить общую таблицу `FinancialData` (к ней же обращаются Excel/Power BI) при
каждом открытии страницы, все агрегаты один раз посчитаны в отдельную схему `reporting`
(`schema.sql`, материализованные представления `pl_monthly`/`fot_monthly`/`loans_monthly`).
Эта схема **обновляется сама** — `reporting_refresh.py` запускается в фоне при старте
приложения и затем каждые 10 минут (APScheduler, см. `app.py`), никаких ручных действий
не требуется.

## Локальный запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить DB_PASSWORD и остальные переменные
python init_reporting_schema.py   # один раз — создать схему reporting
python set_password.py <username> <password>   # задать пароль одному из существующих пользователей
python app.py
```

Приложение поднимется на `http://localhost:5001`.

## Страницы

- `/svod1` — Свод1: П&Л по месяцам одного года (~30 строк, факт/план/прогноз).
- `/svod2` — Свод2: то же, но каждая строка разбита по портфелям DCA/DP.
- `/dashboard1` — Dashboard1: Свод2 за один месяц, годы в столбцах + накопительно.
- `/dashboard2` — Dashboard2: Свод1 за один месяц, тот же годовой формат.
- `/unitpl` — UNIT+PL: непрерывный ряд факт+план по всей истории.
- `/fot1`, `/fot2` — ФОТ v1/v2: то же самое, но по подразделениям/сотрудникам.
- `/loans` — Займы: остаток долга/привлечение/возврат/проценты по кредиторам.
- `/classifier` — справочник классификации статей (`dim_level_report`), только для admin.

## Деплой на Render

Web Service из этого репозитория, переменные окружения — `DATABASE_URL` (или раздельные
`DB_*`, см. `.env.example`) + `SECRET_KEY`, старт-команда `gunicorn app:app --timeout 120`
(см. `render.yaml`). После первого деплоя один раз выполнить `python init_reporting_schema.py`
(например, через Render Shell) — дальше `reporting.*` обновляется сама.
