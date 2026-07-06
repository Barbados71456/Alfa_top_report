truncate table public.base_driver;

insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер1' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" not in ('Общее','Общий')

group by "Период", "п_ф") as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f

;

insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер9' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) AB', '(DCA) ALFA MFO', '(DCA) BIB', '(DCA) Bystrobank', '(DCA) OTP', '(DCA) TB', '(DP) ALFA BIB 2',
'(DP) ALFA RB', '(DP) ALFA RFB', '(DP) Aurora', '(DP) KASM', '(DP) Rusnar', '(DP) ABR Mercedes', '(DCA) Zenith', '(DCA) ATB', '(DP) ALFA MKK(SMS)', '(DP) Aurora Mercedes', '(DCA) ATB', '(DP) Aurora BIB', '(DP) ABR AB', '(DP) Moneyman', '(DP) Aurora Mercedes', '(DP) ALFA MKK(DMM)', '(DP) ALFA MKK(SMS)', '(DCA) Mercedes', '(DCA) unicredit', '(DCA) Unicredit') 
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) AB', '(DCA) ALFA MFO', '(DCA) BIB', '(DCA) Bystrobank', '(DCA) OTP', '(DCA) TB', '(DP) ALFA BIB 2',
'(DP) ALFA RB', '(DP) ALFA RFB', '(DP) Aurora', '(DP) KASM', '(DP) Rusnar', '(DP) ABR Mercedes', '(DCA) Zenith', '(DCA) ATB', '(DP) ALFA MKK(SMS)', '(DP) Aurora Mercedes', '(DCA) ATB', '(DP) Aurora BIB', '(DP) ABR AB', '(DP) Moneyman', '(DP) Aurora Mercedes', '(DP) ALFA MKK(DMM)', '(DP) ALFA MKK(SMS)', '(DCA) Mercedes', '(DCA) unicredit', '(DCA) Unicredit') 
group by "Период", "п_ф") as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;


insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер10' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) OTP', '(DCA) BMW') 
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) OTP', '(DCA) BMW')
group by "Период", "п_ф")  as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;


insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер11' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) AB') 
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" in ('(DCA) AB')
group by "Период", "п_ф")  as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;




insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер2' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" like '%DCA%' and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" like '%DCA%' and "Проект" not in ('Общее','Общий')
group by "Период", "п_ф") as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;


insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер5' as "driver"
from (SELECT "Период", "п_ф", "Проект", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" like '%DP%' and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' and "Проект" like '%DP%' and "Проект" not in ('Общее','Общий')
group by "Период", "п_ф") as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;



insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер3' as "driver"

from (select
two."Период", two."Проект", two."п_ф", (case when two."Сумма1">0 then 1 else 0 end)::float8 as "Сумма1"

from (select
one."Период", one."Проект", one."п_ф", sum(one."Сумма") as "Сумма1"
from (SELECT "Период", "Проект", "п_ф", abs("Сумма") as "Сумма"
FROM public."FinancialData"
where СтатьяУровень2='Отток по ОД (переменные)' or СтатьяУровень2='Поступления по ОД' and "Проект" not in ('Общее','Общий')
) as one
where one."Проект" not in ('Общее','Общий')
group by one."Период", one."Проект", one."п_ф") as two)  as a

left join

(select
tri."Период", tri."п_ф", sum(tri."Сумма1") as "Сумма2"
from (select
two."Период", two."Проект",two."п_ф", case when two."Сумма1">0 then 1 else 0 end as "Сумма1"

from (select
one."Период", one."Проект", one."п_ф", sum(one."Сумма") as "Сумма1"
from (SELECT "Период", "Проект", "п_ф", abs("Сумма") as "Сумма"
FROM public."FinancialData"
where СтатьяУровень2='Отток по ОД (переменные)' or СтатьяУровень2='Поступления по ОД' and "Проект" not in ('Общее','Общий')
) as one
where one."Проект" not in ('Общее','Общий')
group by one."Период", one."Проект", one."п_ф") as two) as tri
group by tri."Период", tri."п_ф") as b

on

a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f

;

insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер6' as "driver"


from (

select
odin.*
from (sELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' or "СтатьяУровень1"='Отток по ОД' and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as odin

where odin."Сумма1">0

) as a

left join 

(

SELECT dva."Период", dva."п_ф", sum("Сумма1") as "Сумма2"
FROM (
select
odin.*
from (sELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Поступления по ОД' or "СтатьяУровень1"='Отток по ОД'  and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as odin

where odin."Сумма1">0
) as dva

group by dva."Период", "п_ф"

) as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;


insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер7' as "driver"
from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."FinancialData"
where "СтатьяУровень1"='Отток по ОД'  and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as a

left join 

(SELECT "Период", "п_ф", sum("Сумма") as "Сумма2"
FROM public."FinancialData"
where "СтатьяУровень1"='Отток по ОД' and "Проект" not in ('Общее','Общий')
group by "Период", "п_ф") as b

on
a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f


;




insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер4' as "driver"

from (select
two."Период", two."Проект", two."п_ф", two."Сумма1"

from (select
one."Период", one."Проект", one."п_ф", sum(one."Сумма") as "Сумма1"
from (SELECT "Период", "Проект", "п_ф", abs("Сумма") as "Сумма"
FROM public."FinancialData"
where СтатьяУровень2='Отток по ОД (переменные)' or СтатьяУровень3='госпошлина' and "Проект" not in ('Общее','Общий')
) as one
where one."Проект" not in ('Общее','Общий')
group by one."Период", one."Проект", one."п_ф") as two)  as a

left join

(select
tri."Период", tri."п_ф", sum(tri."Сумма1") as "Сумма2"
from (select
two."Период", two."Проект", two."п_ф", two."Сумма1"

from (select
one."Период", one."Проект", one."п_ф", sum(one."Сумма") as "Сумма1"
from (SELECT "Период", "Проект", "п_ф", abs("Сумма") as "Сумма"
FROM public."FinancialData"
where СтатьяУровень2='Отток по ОД (переменные)' or СтатьяУровень3='госпошлина' and "Проект" not in ('Общее','Общий')
) as one
where one."Проект" not in ('Общее','Общий')
group by one."Период", one."Проект", one."п_ф") as two) as tri
group by tri."Период", tri."п_ф") as b

on

a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f

;






insert into public.base_driver
("Период", "Проект", п_ф, "Сумма1", "Сумма2", base_расп, driver)

select
f."Период", f."Проект", f.п_ф, f."Сумма1", f."Сумма2", f.base_расп, f.driver

from
(select 
a.*, b."Сумма2", (a."Сумма1"/b."Сумма2") as "base_расп", 'Драйвер8' as "driver"

from (SELECT "Период", "Проект", "п_ф", sum("Сумма") as "Сумма1"
FROM public."rasp_FOT"
where тип_расп='+' and "Проект" not in ('Общее','Общий')
group by "Период", "Проект", "п_ф") as a


left join

(SELECT "Период", "п_ф",  sum("Сумма") as "Сумма2"
FROM public."rasp_FOT"
where тип_расп='+' and "Проект" not in ('Общее','Общий')
group by "Период", "п_ф") as b

on

a."Период"=b."Период" and
a."п_ф"=b."п_ф") as f

;