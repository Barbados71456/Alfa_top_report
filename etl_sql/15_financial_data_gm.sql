truncate table public."FinancialData_GM";

insert into public."FinancialData_GM"
("Распределение", "Сумма", "Период", "Проект", "Контрагент", "Дата", "СтатьяСвод", п_ф, "Контрагент_report")

SELECT "Распределение", sum("Сумма") as "Сумма", "Период", "Проект", "Контрагент", "Дата", '11. Полный денежный поток' as "СтатьяСвод", п_ф, "Контрагент_report"
FROM public."FinancialData"
group by "Распределение", "Период", "Проект", "Контрагент", "Дата", п_ф, "Контрагент_report"
;

 
insert into public."FinancialData_GM"
("Распределение", "Сумма", "Период", "Проект", "Контрагент", "Дата", "СтатьяСвод", п_ф, "Контрагент_report")
SELECT "Распределение", sum("Сумма") as "Сумма", "Период", "Проект", "Контрагент", "Дата", '06. Прибыль компании' as "СтатьяСвод", п_ф, "Контрагент_report"
FROM public."FinancialData"
where "СтатьяСвод" like '01%' or "СтатьяСвод" like '02%' or "СтатьяСвод" like '03%' or "СтатьяСвод" like '04%' or "СтатьяСвод" like '05%' or "СтатьяСвод" like '06%'
or "СтатьяСвод" like '09%'
group by "Распределение", "Период", "Проект", "Контрагент", "Дата", п_ф, "Контрагент_report"
;

insert into public."FinancialData_GM"
("Распределение", "Сумма", "Период", "Проект", "Контрагент", "Дата", "СтатьяСвод", п_ф, "Контрагент_report")

SELECT "Распределение", sum("Сумма") as "Сумма", "Период", "Проект", "Контрагент", "Дата", '05. OIBDA' as "СтатьяСвод", п_ф, "Контрагент_report"
FROM public."FinancialData"
where "СтатьяСвод" like '01%' or "СтатьяСвод" like '02%' or "СтатьяСвод" like '03%' or "СтатьяСвод" like '04%' or "СтатьяСвод" like '09%'
group by "Распределение", "Период", "Проект", "Контрагент", "Дата", п_ф, "Контрагент_report"
;

insert into public."FinancialData_GM"
("Распределение", "Сумма", "Период", "Проект", "Контрагент", "Дата", "СтатьяСвод", п_ф, "Контрагент_report")

SELECT "Распределение", sum("Сумма") as "Сумма", "Период", "Проект", "Контрагент", "Дата", '04. GM' as "СтатьяСвод", п_ф, "Контрагент_report"
FROM public."FinancialData"
where "СтатьяСвод" like '01%' or "СтатьяСвод" like '02%' or "СтатьяСвод" like '03%'
group by "Распределение", "Период", "Проект", "Контрагент", "Дата", п_ф, "Контрагент_report"

;

update public."FinancialData" set "Строка отчета"='ФОТ постоянный' where "Контрагент" ilike '%зудин%' and "Статья" ilike '%зп%';

update public."FinancialData" set "Проект"='(DCA) OTP'      where "Проект" ilike '%(DCA) OTP%';
update public."FinancialData" set "Проект"='(DP) Aurora'    where "Проект" ilike '%(DP) Aurora%' and "Проект" not ilike '%bib%';
update public."FinancialData" set "Проект"='(DCA) ALFA MBA' where "Проект" ilike '%alfa%' and "Проект" ilike '%mba%';
update public."FinancialData" set "Проект"='Общее'          where "Проект" ilike '%процент%' ;




