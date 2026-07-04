-- Отдельная схема для отчётности: агрегаты из public.FinancialData / public.analiz_zaim,
-- обновляются автоматически из reporting_refresh.py (APScheduler), см. app.py.
-- Применяется один раз через init_reporting_schema.py.

CREATE SCHEMA IF NOT EXISTS reporting;

DROP MATERIALIZED VIEW IF EXISTS reporting.pl_monthly;
CREATE MATERIALIZED VIEW reporting.pl_monthly AS
SELECT "Период" AS period,
       "Строка отчета" AS line,
       COALESCE(NULLIF(TRIM("Проект"), ''), '(без проекта)') AS project,
       "п_ф" AS pf,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IS NOT NULL AND TRIM("Строка отчета") <> ''
GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX pl_monthly_uq ON reporting.pl_monthly (period, line, project, pf);
CREATE INDEX pl_monthly_period_idx ON reporting.pl_monthly (period);
CREATE INDEX pl_monthly_line_idx ON reporting.pl_monthly (line);
CREATE INDEX pl_monthly_project_idx ON reporting.pl_monthly (project);

-- Для подсказки при наведении (детализация до СтатьяУровень3): широкий запрос на
-- целый год по "живой" FinancialData занимает секунды (таблица не помещается в кеш
-- на этом тарифе Postgres) — поэтому тоже предвычисляем.
DROP MATERIALIZED VIEW IF EXISTS reporting.pl_monthly_stat3;
CREATE MATERIALIZED VIEW reporting.pl_monthly_stat3 AS
SELECT "Период" AS period,
       "Строка отчета" AS line,
       COALESCE(NULLIF(TRIM("СтатьяУровень3"), ''), '(без статьи)') AS stat3,
       "п_ф" AS pf,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IS NOT NULL AND TRIM("Строка отчета") <> ''
GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX pl_monthly_stat3_uq ON reporting.pl_monthly_stat3 (period, line, stat3, pf);
CREATE INDEX pl_monthly_stat3_period_idx ON reporting.pl_monthly_stat3 (period);

DROP MATERIALIZED VIEW IF EXISTS reporting.fot_monthly;
CREATE MATERIALIZED VIEW reporting.fot_monthly AS
SELECT "Период" AS period,
       COALESCE(NULLIF(TRIM("Контрагент_report"), ''), '(без подразделения)') AS dept,
       COALESCE(NULLIF(TRIM("Контрагент"), ''), '(без сотрудника)') AS employee,
       "п_ф" AS pf,
       "Строка отчета" AS line,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IN ('ФОТ переменный', 'ФОТ постоянный')
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX fot_monthly_uq ON reporting.fot_monthly (period, dept, employee, pf, line);
CREATE INDEX fot_monthly_period_idx ON reporting.fot_monthly (period);
CREATE INDEX fot_monthly_dept_idx ON reporting.fot_monthly (dept);

DROP MATERIALIZED VIEW IF EXISTS reporting.loans_monthly;
CREATE MATERIALIZED VIEW reporting.loans_monthly AS
SELECT "Период" AS period,
       COALESCE(NULLIF(TRIM("Контрагент"), ''), '(без контрагента)') AS lender,
       "СтатьяУровень3" AS line,
       "п_ф" AS pf,
       SUM("Сумма") AS amount
FROM public.analiz_zaim
WHERE "СтатьяУровень3" IS NOT NULL
GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX loans_monthly_uq ON reporting.loans_monthly (period, lender, line, pf);
CREATE INDEX loans_monthly_period_idx ON reporting.loans_monthly (period);
CREATE INDEX loans_monthly_lender_idx ON reporting.loans_monthly (lender);

-- Список контрагентов для /counterparty (DISTINCT по 434k строкам без индекса —
-- полный seq scan ~11с; предвычисляем, как и остальные тяжёлые агрегаты).
DROP MATERIALIZED VIEW IF EXISTS reporting.counterparty_list;
CREATE MATERIALIZED VIEW reporting.counterparty_list AS
SELECT DISTINCT "Контрагент" AS name
FROM public."FinancialData"
WHERE "Контрагент" IS NOT NULL AND TRIM("Контрагент") <> '';

CREATE UNIQUE INDEX counterparty_list_uq ON reporting.counterparty_list (name);

-- Под живые (не через materialized view) запросы детализации ячеек Свод1/Dashboard2 —
-- поиск по (Строка отчета, Период, п_ф) с опциональным фильтром по Проекту.
CREATE INDEX IF NOT EXISTS idx_financialdata_line_period_pf
    ON public."FinancialData" ("Строка отчета", "Период", "п_ф");

-- Справочник сотрудников для ФОТ (подразделение/должность/статус) — заполняется
-- автоматически новыми именами из reporting.fot_monthly (см. reporting_refresh.py),
-- редактируется вручную на /employees. ON CONFLICT DO NOTHING никогда не затирает
-- то, что уже поправили руками.
CREATE TABLE IF NOT EXISTS reporting.employees (
    contragent TEXT PRIMARY KEY,
    department TEXT,
    position TEXT,
    status TEXT DEFAULT 'Работает',
    updated_at TIMESTAMP DEFAULT now()
);

-- Инвестиционный анализ портфелей DP (окупаемость, собираемость): денежный поток
-- портфеля = СтатьяСвод (выручка/расходы портфельные/расходы прочие) с разбивкой по
-- Распределение (до распределения / распределение) — это и есть "с учётом и без учёта
-- распределения затрат". См. investment_report.py.
DROP MATERIALIZED VIEW IF EXISTS reporting.dp_monthly;
CREATE MATERIALIZED VIEW reporting.dp_monthly AS
SELECT "Период" AS period,
       "Проект" AS project,
       "СтатьяСвод" AS statya_svod,
       "Распределение" AS allocation,
       "п_ф" AS pf,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "СтатьяСвод" IN ('01. Выручка профильная (+)', '03. Расходы портфельные (-)',
                        '04. Расходы Прочие (-)', '06. Инвестиции (+/-)')
  AND "Проект" ILIKE '(DP)%%'
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX dp_monthly_uq ON reporting.dp_monthly (period, project, statya_svod, allocation, pf);
CREATE INDEX dp_monthly_project_idx ON reporting.dp_monthly (project);

-- Справочник купленных портфелей ДЗ (дата уступки, к-во, ОСЗ = номинал долга,
-- фактически уплаченная цена) — внешние данные, которых нет в FinancialData, заполняется
-- разово из листа "Список" эталонного Excel и правится вручную на /investment/admin.
CREATE TABLE IF NOT EXISTS reporting.dp_portfolios (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT UNIQUE NOT NULL,
    purchase_date DATE,
    units NUMERIC,
    face_value_rub NUMERIC,
    price_rub NUMERIC,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT now()
);

-- Соответствие "сырое имя Проект в FinancialData" -> канонический портфель. В
-- FinancialData один и тот же портфель встречается с вариациями (пробелы/регистр/NBSP) —
-- автоматически привязываются точные совпадения (см. investment_report.sync_aliases()),
-- расхождения донастраиваются на /investment/admin.
CREATE TABLE IF NOT EXISTS reporting.dp_portfolio_aliases (
    id SERIAL PRIMARY KEY,
    dp_portfolio_id INTEGER NOT NULL REFERENCES reporting.dp_portfolios(id) ON DELETE CASCADE,
    project_name TEXT UNIQUE NOT NULL
);

-- Аудит-лог: вход, правки классификаторов/справочников, экспорт в Excel, вопросы в чат.
-- Пишется через audit.log_action(), просматривается на /admin/log.
CREATE TABLE IF NOT EXISTS reporting.audit_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    username TEXT,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT
);
CREATE INDEX IF NOT EXISTS audit_log_created_at_idx ON reporting.audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_username_idx ON reporting.audit_log (username);
