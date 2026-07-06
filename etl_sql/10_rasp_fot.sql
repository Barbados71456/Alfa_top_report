truncate table public."rasp_FOT";

insert into public."rasp_FOT"
select
one."Распределение", one."Статья",  one."Период", one."Признак", one."Категория", public.base_driver."Проект", one."Контрагент", one."Тип Кошелька", one."Кошелек", one."Комментарии", one."Поток", 
one."P&L", one."UE", one."СтатьяУровень0", one."СтатьяУровень1", one."СтатьяУровень2", one."СтатьяУровень3", one."СтатьяУровень4", one."Дата", one."СтатьяСвод", one.п_ф, one."Контрагент_report"

, one."Драйвер", public.base_driver.base_расп*one."Сумма" as "Сумма",
'+' as тип_расп, one."Строка отчета"


from (SELECT 
public."FinancialData"."Распределение", public."FinancialData"."Статья", public."FinancialData"."Сумма", public."FinancialData"."Период", public."FinancialData"."Признак", 
public."FinancialData"."Категория", public."FinancialData"."Проект", public."FinancialData"."Контрагент", public."FinancialData"."Тип Кошелька", public."FinancialData"."Кошелек", public."FinancialData"."Комментарии", 
public."FinancialData"."Поток", public."FinancialData"."P&L", public."FinancialData"."UE", public."FinancialData"."СтатьяУровень0", public."FinancialData"."СтатьяУровень1", public."FinancialData"."СтатьяУровень2", public."FinancialData"."СтатьяУровень3", 
public."FinancialData"."СтатьяУровень4", public."FinancialData"."Дата", public."FinancialData"."СтатьяСвод", public."FinancialData".п_ф, public."FinancialData"."Контрагент_report",
public."dim_ШР"."Драйвер", public."FinancialData"."Строка отчета"
FROM public."FinancialData"

left join public."dim_ШР" on
public."dim_ШР"."Контрагент"=public."FinancialData"."Контрагент"

where ("СтатьяУровень3" = 'Зп' or
       "СтатьяУровень3" = 'Премия') and "Проект" ilike 'обще%' 

) as one
      
left join public.base_driver on 
public.base_driver."Период"=one."Период" and
public.base_driver.driver=one."Драйвер" and
public.base_driver.п_ф=one.п_ф

where one."Драйвер" is not null

;


insert into public."rasp_FOT"
select
one."Распределение", one."Статья",  one."Период", one."Признак", one."Категория", one."Проект", one."Контрагент", one."Тип Кошелька", one."Кошелек", one."Комментарии", one."Поток", 
one."P&L", one."UE", one."СтатьяУровень0", one."СтатьяУровень1", one."СтатьяУровень2", one."СтатьяУровень3", one."СтатьяУровень4", one."Дата", one."СтатьяСвод", one.п_ф, one."Контрагент_report"

, one."Драйвер", -one."Сумма" as "Сумма", '-' as тип_расп, one."Строка отчета"


from (SELECT 
public."FinancialData"."Распределение", public."FinancialData"."Статья", public."FinancialData"."Сумма", public."FinancialData"."Период", public."FinancialData"."Признак", 
public."FinancialData"."Категория", public."FinancialData"."Проект", public."FinancialData"."Контрагент", public."FinancialData"."Тип Кошелька", public."FinancialData"."Кошелек", public."FinancialData"."Комментарии", 
public."FinancialData"."Поток", public."FinancialData"."P&L", public."FinancialData"."UE", public."FinancialData"."СтатьяУровень0", public."FinancialData"."СтатьяУровень1", public."FinancialData"."СтатьяУровень2", public."FinancialData"."СтатьяУровень3", 
public."FinancialData"."СтатьяУровень4", public."FinancialData"."Дата", public."FinancialData"."СтатьяСвод", public."FinancialData".п_ф, public."FinancialData"."Контрагент_report",
public."dim_ШР"."Драйвер", public."FinancialData"."Строка отчета"


FROM public."FinancialData"

left join public."dim_ШР" on
public."dim_ШР"."Контрагент"=public."FinancialData"."Контрагент"

where ("СтатьяУровень3" = 'Зп' or
       "СтатьяУровень3" = 'Премия') and "Проект" ilike 'обще%' 
       
       
      

) as one
      

where one."Драйвер" is not null

;





