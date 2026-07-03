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
