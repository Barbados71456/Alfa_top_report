
truncate table public."rasp_Ostatki";

insert into public."rasp_Ostatki"
select

one."Распределение", one."Статья",  one."Период", one."Признак", one."Категория", case when public.base_driver."Проект" is null then 'Общее' else public.base_driver."Проект" end as "Проект", one."Контрагент", one."Тип Кошелька", one."Кошелек", one."Комментарии", one."Поток", 
one."P&L", one."UE", one."СтатьяУровень0", one."СтатьяУровень1", one."СтатьяУровень2", one."СтатьяУровень3", one."СтатьяУровень4", 
one."Дата", one."СтатьяСвод", one.п_ф, one."Контрагент_report", one."Драйвер", case when public.base_driver."Проект" is null then "Сумма" else public.base_driver.base_расп*one."Сумма" end as "Сумма"
, '+' as тип_расп, one."Строка отчета"


from (SELECT 
public."FinancialData"."Распределение", public."FinancialData"."Статья", public."FinancialData"."Сумма", public."FinancialData"."Период", public."FinancialData"."Признак", 
public."FinancialData"."Категория", public."FinancialData"."Проект", public."FinancialData"."Контрагент", public."FinancialData"."Тип Кошелька", public."FinancialData"."Кошелек", public."FinancialData"."Комментарии", 
public."FinancialData"."Поток", public."FinancialData"."P&L", public."FinancialData"."UE", public."FinancialData"."СтатьяУровень0", public."FinancialData"."СтатьяУровень1", public."FinancialData"."СтатьяУровень2", public."FinancialData"."СтатьяУровень3", 
public."FinancialData"."СтатьяУровень4", public."FinancialData"."Дата", public."FinancialData"."СтатьяСвод", public."FinancialData".п_ф, public."FinancialData"."Контрагент_report",
public."dim_ОД_расп"."Драйвер", public."FinancialData"."Строка отчета"
FROM public."FinancialData"

left join public."dim_ОД_расп" on

public."dim_ОД_расп"."СтатьяУровень2"=public."FinancialData"."СтатьяУровень2" and 
public."dim_ОД_расп"."СтатьяУровень3"=public."FinancialData"."СтатьяУровень3" and 
public."dim_ОД_расп"."Проект"=public."FinancialData"."Проект" 

where public."dim_ОД_расп"."Драйвер" is not null) as one 

left join public.base_driver on 
public.base_driver."Период"=one."Период" and
public.base_driver.driver=one."Драйвер" and
public.base_driver.п_ф=one.п_ф 

;




insert into public."rasp_Ostatki"
select
one."Распределение", one."Статья",  one."Период", one."Признак", one."Категория", one."Проект", one."Контрагент", one."Тип Кошелька", one."Кошелек", one."Комментарии", one."Поток", 
one."P&L", one."UE", one."СтатьяУровень0", one."СтатьяУровень1", one."СтатьяУровень2", one."СтатьяУровень3", one."СтатьяУровень4", one."Дата", one."СтатьяСвод", one.п_ф, one."Контрагент_report"

, one."Драйвер", -"Сумма" as "Сумма", '-' as тип_расп, one."Строка отчета"

from (SELECT 
public."FinancialData"."Распределение", public."FinancialData"."Статья", public."FinancialData"."Сумма", public."FinancialData"."Период", public."FinancialData"."Признак", 
public."FinancialData"."Категория", public."FinancialData"."Проект", public."FinancialData"."Контрагент", public."FinancialData"."Тип Кошелька", public."FinancialData"."Кошелек", public."FinancialData"."Комментарии", 
public."FinancialData"."Поток", public."FinancialData"."P&L", public."FinancialData"."UE", public."FinancialData"."СтатьяУровень0", public."FinancialData"."СтатьяУровень1", public."FinancialData"."СтатьяУровень2", public."FinancialData"."СтатьяУровень3", 
public."FinancialData"."СтатьяУровень4", public."FinancialData"."Дата", public."FinancialData"."СтатьяСвод", public."FinancialData".п_ф, public."FinancialData"."Контрагент_report",
public."dim_ОД_расп"."Драйвер", public."FinancialData"."Строка отчета"
FROM public."FinancialData"
left join public."dim_ОД_расп" on

public."dim_ОД_расп"."СтатьяУровень2"=public."FinancialData"."СтатьяУровень2" and 
public."dim_ОД_расп"."СтатьяУровень3"=public."FinancialData"."СтатьяУровень3" and 
public."dim_ОД_расп"."Проект"=public."FinancialData"."Проект" 

where public."dim_ОД_расп"."Драйвер" is not null) as one 


;

update public."rasp_Ostatki" set "Сумма"=0 where "СтатьяУровень3"='Налоги' and Период='2020-11-01';
