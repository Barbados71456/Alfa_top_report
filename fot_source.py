"""Canonical payroll source, also safe with backups predating the bonus migration.

Do not depend on a restored materialized view's historical definition. Aggregate
the same three FinancialData lines used by drill-down, without changing the DB
schema or source records. PostgreSQL can push report period filters into the CTE.
"""
FOT_LINES = ('ФОТ переменный', 'ФОТ постоянный', 'Премия за изъятие авто')

MONTHLY_CTE = '''WITH fot_source AS (
    SELECT "Период" AS period,
           COALESCE(NULLIF(TRIM("Контрагент_report"), ''), '(без подразделения)') AS dept,
           COALESCE(NULLIF(TRIM("Контрагент"), ''), '(без сотрудника)') AS employee,
           "п_ф" AS pf, "Строка отчета" AS line, SUM("Сумма") AS amount
    FROM public."FinancialData"
    WHERE "Строка отчета" IN ('ФОТ переменный', 'ФОТ постоянный', 'Премия за изъятие авто')
    GROUP BY 1, 2, 3, 4, 5
) '''
