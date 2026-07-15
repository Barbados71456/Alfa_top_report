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
       "Распределение" AS allocation,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IS NOT NULL AND TRIM("Строка отчета") <> ''
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX pl_monthly_uq ON reporting.pl_monthly (period, line, project, pf, allocation);
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
       "Распределение" AS allocation,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IS NOT NULL AND TRIM("Строка отчета") <> ''
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX pl_monthly_stat3_uq ON reporting.pl_monthly_stat3 (period, line, stat3, pf, allocation);
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

-- Под "живой" (не через materialized view) отчёт "Проводки по кошельку" —
-- SELECT ... WHERE "Кошелек" = ANY(...) по сырой таблице без индекса был бы seq scan.
CREATE INDEX IF NOT EXISTS idx_financialdata_koshelek
    ON public."FinancialData" ("Кошелек");

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

-- CBR (cash back rate) — собираемость помесячно по сотрудникам-взыскателям, регионам,
-- текущим кредиторам и типам долга. Источник — уже готовые агрегаты выгрузки из БИТ:
-- public.cbr_report_1 (остаток задолженности на конец месяца) и public.cbr_report_2
-- (платежи за месяц), см. cbr_report.py. Отдельная схема — по просьбе пользователя.
CREATE SCHEMA IF NOT EXISTS cbr;

DROP MATERIALIZED VIEW IF EXISTS cbr.monthly;
CREATE MATERIALIZED VIEW cbr.monthly AS
WITH last_snapshot AS (
    -- cbr_report_1 хранит ЕЖЕДНЕВНЫЕ срезы остатка (extracted_date) внутри каждого
    -- месяца — остаток это точка на конец периода, а не поток, поэтому суммировать
    -- строки за все дни месяца нельзя (даст ~20-кратное завышение); берём только
    -- последний срез месяца (одним проходом, без коррелированного подзапроса на
    -- 3.9М строк).
    SELECT month, MAX(extracted_date) AS last_date FROM public.cbr_report_1 GROUP BY 1
)
SELECT
    COALESCE(b.month, p.month) AS month,
    COALESCE(b.employee, p.employee) AS employee,
    COALESCE(b.region, p.region) AS region,
    COALESCE(b.creditor, p.creditor) AS creditor,
    COALESCE(b.debt_type, p.debt_type) AS debt_type,
    COALESCE(b.work_type, p.work_type) AS work_type,
    COALESCE(b.total_debt, 0) AS total_debt,
    COALESCE(b.principal_debt, 0) AS principal_debt,
    COALESCE(p.payment_amount, 0) AS payment_amount,
    COALESCE(p.do_count, 0) AS do_count,
    COALESCE(p.payment_count, 0) AS payment_count
FROM (
    SELECT r.month, r."Сотрудник" AS employee, r."Регион по прописке" AS region,
           r."Текущий кредитор" AS creditor, r."Тип долга" AS debt_type, r."Тип работы" AS work_type,
           SUM(r."Общая сумма задолженности") AS total_debt, SUM(r."Основной долг") AS principal_debt
    FROM public.cbr_report_1 r
    JOIN last_snapshot s ON s.month = r.month AND s.last_date = r.extracted_date
    GROUP BY 1, 2, 3, 4, 5, 6
) b
FULL JOIN (
    SELECT month, "Сотрудник" AS employee, "Регион по прописке" AS region,
           "Текущий кредитор" AS creditor, "Тип долга" AS debt_type, "Тип работы" AS work_type,
           SUM("Сумма платежа") AS payment_amount, SUM("Число ДО") AS do_count,
           SUM("Число платежей") AS payment_count
    FROM public.cbr_report_2
    GROUP BY 1, 2, 3, 4, 5, 6
) p
ON b.month = p.month
   AND b.employee IS NOT DISTINCT FROM p.employee
   AND b.region IS NOT DISTINCT FROM p.region
   AND b.creditor IS NOT DISTINCT FROM p.creditor
   AND b.debt_type IS NOT DISTINCT FROM p.debt_type
   AND b.work_type IS NOT DISTINCT FROM p.work_type;

CREATE INDEX IF NOT EXISTS cbr_monthly_month_idx ON cbr.monthly (month);
CREATE INDEX IF NOT EXISTS cbr_monthly_employee_idx ON cbr.monthly (employee);
CREATE INDEX IF NOT EXISTS cbr_monthly_region_idx ON cbr.monthly (region);
CREATE INDEX IF NOT EXISTS cbr_monthly_creditor_idx ON cbr.monthly (creditor);

-- Справочник сотрудников-взыскателей (отдел/регион/статус/тип занятости) — разово
-- заполняется из листа "Mapping" эталонного Excel (CBR_v4.xlsx), правится вручную
-- на /cbr/admin. Тот же паттерн, что reporting.employees для ФОТ.
CREATE TABLE IF NOT EXISTS cbr.employee_mapping (
    employee TEXT PRIMARY KEY,
    department TEXT,
    region TEXT,
    is_fired BOOLEAN,
    employment_type TEXT,
    updated_at TIMESTAMP DEFAULT now()
);

-- Справочник "Текущий кредитор" (CBR) -> "Проект" (П&Л, public.projects) — изначально
-- пустой, заполняется вручную на /cbr/admin/creditors по мере того, как сотрудник
-- сопоставляет кредиторов с портфелями. Новые кредиторы, ещё без пары, видны там же
-- как "не сопоставлено" (LEFT JOIN с cbr.monthly в cbr_report.get_creditor_project_mapping).
CREATE TABLE IF NOT EXISTS cbr.creditor_project_mapping (
    creditor TEXT PRIMARY KEY,
    project TEXT,
    updated_at TIMESTAMP DEFAULT now()
);

-- Сверка остатков по кошелькам: пользователь периодически вводит проверенный
-- (сверенный с банком/кассой) остаток по кошельку, обороты между точками сверки
-- считаются автоматически из FinancialData."Кошелек". Группировка кошельков (Счета/
-- Касса/Спецсчета/Учредители/Прочее) — по листу "Карманы" эталонного Excel
-- (01_Сверка_счета.xlsx), см. wallet_report.py.
DROP MATERIALIZED VIEW IF EXISTS reporting.wallet_monthly;
CREATE MATERIALIZED VIEW reporting.wallet_monthly AS
SELECT "Период" AS period,
       "Кошелек" AS wallet_raw,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Кошелек" IS NOT NULL AND TRIM("Кошелек") <> ''
  -- 'распределение' — служебные проводки распределения косвенных расходов по
  -- проектам, а не движение денег по кошелькам (197к строк с одним и тем же
  -- "Кошелек"='распределение') — не реальный кошелёк, исключаем.
  AND lower(trim("Кошелек")) <> 'распределение'
  AND "п_ф" = 'факт'
GROUP BY 1, 2;

CREATE UNIQUE INDEX wallet_monthly_uq ON reporting.wallet_monthly (period, wallet_raw);
CREATE INDEX wallet_monthly_wallet_idx ON reporting.wallet_monthly (wallet_raw);

CREATE TABLE IF NOT EXISTS reporting.wallets (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT UNIQUE NOT NULL,
    group_name TEXT NOT NULL DEFAULT 'Прочее',
    notes TEXT,
    updated_at TIMESTAMP DEFAULT now()
);

-- Соответствие "сырое имя Кошелек в FinancialData" -> канонический кошелёк, тот же
-- паттерн, что reporting.dp_portfolio_aliases (см. wallet_report.sync_aliases()).
CREATE TABLE IF NOT EXISTS reporting.wallet_aliases (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER NOT NULL REFERENCES reporting.wallets(id) ON DELETE CASCADE,
    raw_name TEXT UNIQUE NOT NULL
);

-- Ручные точки сверки: введённый пользователем факт-остаток на дату. Между точками
-- расчётный остаток = последняя точка + обороты по reporting.wallet_monthly с этой
-- даты; расхождение на новой точке = введено - расчёт (см. wallet_report.py).
CREATE TABLE IF NOT EXISTS reporting.wallet_balances (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER NOT NULL REFERENCES reporting.wallets(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    balance NUMERIC NOT NULL,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE (wallet_id, period)
);

-- Личный кабинет: доп. поле профиля пользователя (email уже был), см. /my/profile.
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;

-- Автозагрузка отчётности (замена ручного KNIME-процесса, см. monthly_etl.py):
-- зеркало таблиц конвейера "Excel -> FinancialData" на ОТДЕЛЬНОЙ схеме, чтобы
-- прогонять и сверять с public перед тем, как это когда-либо тронет прод.
-- Структуры взяты 1-в-1 из public через LIKE...INCLUDING ALL (не переписаны
-- руками, чтобы точно не разойтись типами колонок).
CREATE SCHEMA IF NOT EXISTS etl_load;

CREATE TABLE IF NOT EXISTS etl_load.fact_step_0 (LIKE public.fact_step_0 INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load.fact_step_1 (LIKE public.fact_step_1 INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load.base_report_park1 (LIKE public.base_report_park1 INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load.report_do_rasp (LIKE public.report_do_rasp INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."FinancialData" (LIKE public."FinancialData" INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load.base_driver (LIKE public.base_driver INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."rasp_FOT" (LIKE public."rasp_FOT" INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."rasp_Ostatki" (LIKE public."rasp_Ostatki" INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."analiz_zaim" (LIKE public."analiz_zaim" INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."analiz_кошелек" (LIKE public."analiz_кошелек" INCLUDING ALL);
CREATE TABLE IF NOT EXISTS etl_load."FinancialData_GM" (LIKE public."FinancialData_GM" INCLUDING ALL);

-- Журнал запусков автозагрузки — для админки (какие шаги прошли/упали, сколько
-- строк, когда, кто запустил).
CREATE TABLE IF NOT EXISTS etl_load.run_log (
    id SERIAL PRIMARY KEY,
    period DATE,  -- NULL для полного пересчёта истории (run_full_rebuild) — там нет одного периода
    started_at TIMESTAMP DEFAULT now(),
    started_by TEXT,
    steps JSONB,
    status TEXT
);

-- "Сверка чужие деньги" — тот же принцип, что reporting.wallet_balances (входящий
-- остаток + обороты = расчётный остаток), но для одной строки отчёта "Чужие деньги"
-- (public."FinancialData"."Строка отчета"), а не кошелька — отдельная таблица без
-- wallet_id, т.к. это не кошелёк (см. wallet_report.py foreign_money_*).
CREATE TABLE IF NOT EXISTS reporting.foreign_money_balances (
    id SERIAL PRIMARY KEY,
    period DATE NOT NULL UNIQUE,
    balance NUMERIC NOT NULL,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- "Flash"-отчёт: предварительная (неаудированная) картина текущего месяца из
-- банковских выписок, до того как бухгалтер вручную классифицирует их и они
-- попадут в public."FinancialData" обычным ежемесячным процессом. См. flash_report.py.
CREATE SCHEMA IF NOT EXISTS flash;

-- Разобранные строки выписок в нормализованном виде + разметка полями той же
-- схемы, что public."FinancialData" (Признак/Категория/Статья/Проект/...) —
-- чтобы не изобретать вторую систему классификации.
CREATE TABLE IF NOT EXISTS flash.transactions (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    bank_format TEXT NOT NULL,
    account_number TEXT,
    wallet TEXT,
    operation_date DATE NOT NULL,
    document_number TEXT,
    amount NUMERIC NOT NULL,
    counterparty_name TEXT,
    counterparty_inn TEXT,
    purpose_text TEXT,
    "Признак" TEXT,
    "Категория" TEXT,
    "Статья" TEXT,
    "Проект" TEXT,
    "Контрагент_report" TEXT,
    "Строка отчета" TEXT,
    classification_source TEXT,
    matched_financialdata_id BIGINT,
    imported_by TEXT,
    imported_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flash_transactions_period ON flash.transactions (operation_date);
-- Обычный UNIQUE(...) тут не работает как задумано: в Postgres NULL никогда
-- не равен NULL, а counterparty_inn часто NULL (должники-физлица без ИНН на
-- выписке) — при повторной загрузке того же файла (выписки грузятся
-- еженедельно/ежедневно, растущий диапазон дат, порядок строк может
-- отличаться) такие операции тихо задваивались бы. COALESCE в expression-
-- индексе нормализует NULL для сравнения, оставляя сам столбец NULL.
CREATE UNIQUE INDEX IF NOT EXISTS idx_flash_transactions_dedup ON flash.transactions (
    bank_format, account_number, document_number, operation_date, amount,
    COALESCE(counterparty_inn, ''), COALESCE(purpose_text, '')
);

-- "Выучены" из истории public."FinancialData" (см. flash_report.learn_rules) —
-- сопоставление ИНН контрагента или ключевой фразы в назначении платежа с
-- классификацией; приоритет — чем выше priority, тем раньше проверяется правило.
CREATE TABLE IF NOT EXISTS flash.classification_rules (
    id SERIAL PRIMARY KEY,
    match_type TEXT NOT NULL,
    match_value TEXT NOT NULL,
    "Признак" TEXT,
    "Категория" TEXT,
    "Статья" TEXT,
    "Проект" TEXT,
    "Контрагент_report" TEXT,
    "Строка отчета" TEXT,
    priority INTEGER DEFAULT 0,
    source TEXT,
    hits INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flash_rules_match ON flash.classification_rules (match_type, match_value);

-- Номер счёта из выписки -> канонический "Кошелек" (как в public."FinancialData"),
-- см. flash_report.learn_wallet_aliases — тоже выучено из истории, где возможно.
CREATE TABLE IF NOT EXISTS flash.wallet_aliases (
    id SERIAL PRIMARY KEY,
    account_number TEXT UNIQUE NOT NULL,
    wallet TEXT NOT NULL,
    wallet_type TEXT,
    source TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- Ручное разбиение одной банковской операции на несколько частей с разными
-- "Проект"/"Строка отчета" (например, платёж полевому агенту, распределённый
-- по проектам его загрузки — сигнала для такого распределения нет ни в ИНН,
-- ни в тексте платежа, только в отдельной таблице драйверов, которой у Flash
-- нет). Сумма всех строк должна равняться сумме исходной flash.transactions
-- (проверяется в flash_report.set_transaction_splits). Пока у операции есть
-- строки в этой таблице, сама операция помечается classification_source=
-- 'split' и в отчётах Flash заменяется этими строками (см.
-- flash_report._effective_rows_sql()).
CREATE TABLE IF NOT EXISTS flash.transaction_splits (
    id SERIAL PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES flash.transactions(id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    "Признак" TEXT,
    "Категория" TEXT,
    "Статья" TEXT,
    "Проект" TEXT,
    "Контрагент_report" TEXT,
    "Строка отчета" TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flash_splits_txn ON flash.transaction_splits (transaction_id);
