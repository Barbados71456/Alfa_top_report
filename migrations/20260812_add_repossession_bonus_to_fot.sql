-- Добавляет «Премию за изъятие авто» в единый источник ФОТ и сразу
-- синхронизирует сотрудников этой статьи со справочником.
BEGIN;

DROP MATERIALIZED VIEW IF EXISTS reporting.fot_monthly;
CREATE MATERIALIZED VIEW reporting.fot_monthly AS
SELECT "Период" AS period,
       COALESCE(NULLIF(TRIM("Контрагент_report"), ''), '(без подразделения)') AS dept,
       COALESCE(NULLIF(TRIM("Контрагент"), ''), '(без сотрудника)') AS employee,
       "п_ф" AS pf,
       "Строка отчета" AS line,
       SUM("Сумма") AS amount
FROM public."FinancialData"
WHERE "Строка отчета" IN ('ФОТ переменный', 'ФОТ постоянный', 'Премия за изъятие авто')
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX fot_monthly_uq
    ON reporting.fot_monthly (period, dept, employee, pf, line);
CREATE INDEX fot_monthly_period_idx ON reporting.fot_monthly (period);
CREATE INDEX fot_monthly_dept_idx ON reporting.fot_monthly (dept);

DELETE FROM reporting.employees WHERE contragent = '(без сотрудника)';

INSERT INTO reporting.employees (contragent, department)
SELECT employee, (array_agg(dept ORDER BY period DESC))[1]
FROM reporting.fot_monthly
WHERE employee <> '(без сотрудника)'
GROUP BY employee
ON CONFLICT (contragent) DO NOTHING;

COMMIT;
