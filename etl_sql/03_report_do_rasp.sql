truncate table public.report_do_rasp;

insert into public.report_do_rasp
select
one.*, 
public.dim_level_report."СтатьяУровень0",
public.dim_level_report."СтатьяУровень1",
public.dim_level_report."СтатьяУровень2",
public.dim_level_report."СтатьяУровень3"

from (

SELECT 
    CASE 
        WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') ILIKE '%представительские%' 
           OR REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') = 'Представительские расходы'
           THEN 'Представительские расходы, поездки'
        WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') IN ('Почта', 'почта')
           THEN 'Почтовые расходы'
        WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') = 'прочее'
           THEN 'прочие расходы'
        WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') = 'офисные работы'
           THEN 'Офисные расходы'
        
		WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') is null
           THEN 'нет статьи'
        
        WHEN REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор') = ' ГСМ'
           THEN 'ГСМ'
        ELSE REPLACE(REPLACE(REPLACE(Статья, 'ЗП агенты', 'зп'), 
                             'эвакуация', 'эвакуатор'), 
                             'Транспотные расхлды', 'эвакуатор')
    END AS Статья,
    Сумма,
    TO_DATE(
        '01.' || 
        CASE 
            WHEN месяц IN ('январь', 'Январь') THEN '01'
            WHEN месяц IN ('февраль', 'Февраль') THEN '02'
            WHEN месяц IN ('март', 'Март') THEN '03'
            WHEN месяц IN ('апрель', 'Апрель') THEN '04'
            WHEN месяц IN ('май', 'Май') THEN '05'
            WHEN месяц IN ('июнь', 'Июнь') THEN '06'
            WHEN месяц IN ('июль', 'Июль') THEN '07'
            WHEN месяц IN ('август', 'Август') THEN '08'
            WHEN месяц IN ('сентябрь', 'Сентябрь') THEN '09'
            WHEN месяц IN ('октябрь', 'Октябрь') THEN '10'
            WHEN месяц IN ('ноябрь', 'Ноябрь') THEN '11'
            WHEN месяц IN ('декабрь', 'Декабрь') THEN '12'
            ELSE '01'
        END || '.' || Год, 
        'DD.MM.YYYY'
    ) AS Период,
    case when "Категория"='Займы' then 'финансы'  else "Признак" end as "Признак", 
     case when "Категория" is null then 'нет категории' else "Категория" end as "Категория",
     "Проект", "Контрагент", "Тип Кошелька", "Кошелек", "Комментарии", "Поток", "P&L", null as "UE", "Дата"
FROM public.base_report_park1
--where Год='2022' or Год='2023' or Год='2024'  or Год='2025' or Год='2026'
ORDER BY Период

) as one

left join public.dim_level_report on

public.dim_level_report."Признак"=one."Признак" and
public.dim_level_report."Категория"=one."Категория" and
public.dim_level_report."Статья"=one."Статья"

--where public.dim_level_report."СтатьяУровень0" is not null

;




update public.report_do_rasp set  "Проект"='Общее' where  "Проект"='общее';
update public.report_do_rasp set  "Проект"='(DP) Zenith' where  "Проект"='(DP) Zenith';
update public.report_do_rasp set  "Проект"='(DP) Zenith' where  "Проект"='(DР) Zenith';

update public.report_do_rasp set  "Проект"='(DP) Zenith' where  "Проект"='(DР) Zenith
';

UPDATE public.report_do_rasp 
SET 
    "СтатьяУровень1" = 'Отток по ОД',
    "СтатьяУровень2" = 'Отток по ОД (постоянные)'
WHERE 
    "Статья" = 'Налоги' 
    AND "СтатьяУровень1" = 'Финансы';

update public.report_do_rasp 
set "Проект"='(DP) Mercedes'
where "Проект"='(DCA) Mercedes' and "Период"='2025-04-01' and "Контрагент"='Зудин Сергей Андреевич';

update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where"Проект" like '%вакуатор%' and "Период"='2022-03-01' and "Категория"='Прочие доходы';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where"Проект" like '%вакуатор%' and "Период"='2022-03-01' and "Категория"='Прочие доходы';


update public.report_do_rasp
set "СтатьяУровень1"='Поступления по ОД'
where "Проект" like '%вакуатор%' and "Период"='2022-03-01' and "Статья"='Прочие расходы';


update public.report_do_rasp
set "СтатьяУровень2"='Эвакуатор'
where "Проект" like '%вакуатор%' and "Период"='2022-03-01' and "Статья"='Прочие расходы';

update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Категория"='Переменные расходы' and  "СтатьяУровень2"='Отток по ОД (постоянные)' ;

update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DCA) AB' and "Признак"='финансы' and  "Статья"='Банкроты';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DCA) AB' and "Признак"='финансы' and  "Статья"='Банкроты';


update public.report_do_rasp
set "СтатьяУровень0"='Не наше'
where  "Статья"='Возврат ошибочных платежей';



update public.report_do_rasp
set "СтатьяУровень1"='Не наше'
where  "Статья"='Возврат ошибочных платежей';


update public.report_do_rasp
set "СтатьяУровень2"='Не наше'
where  "Статья"='Возврат ошибочных платежей';


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DP) Aurora' and "Период"='2022-09-01' and "СтатьяУровень1"<>'Поступления по ОД';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DP) Aurora' and "Период"='2022-09-01' and "СтатьяУровень1"<>'Поступления по ОД';

update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DCA) BIB' and "Период"='2022-02-01' and "СтатьяУровень1"='Финансы';

update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DCA) BIB' and "Период"='2022-02-01' and "СтатьяУровень1"='Финансы';


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DCA) BIB' and "Период"='2022-06-01' and "СтатьяУровень1"='Финансы';

update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DCA) BIB' and "Период"='2022-06-01' and "СтатьяУровень1"='Финансы';



update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DCA) BIB' and "Период"='2022-07-01' and "Категория"='Прочие расходы';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DCA) BIB' and "Период"='2022-07-01' and "Категория"='Прочие расходы';


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Проект"='(DCA) BIB' and "Период"='2022-12-01' and "СтатьяУровень2"='Отток по ОД (постоянные)';

update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Проект"='(DCA) BIB' and "Период"='2022-12-01' and "СтатьяУровень2"='Отток по ОД (постоянные)';


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Период"='2022-02-01'   and "Контрагент"='шемякин' and "Проект"='(DCA) BIB' and "Дата"='2022-02-15';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Период"='2022-02-01'   and "Контрагент"='шемякин' and "Проект"='(DCA) BIB' and "Дата"='2022-02-15';

update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Период"='2022-06-01'   and "Проект"='(DCA) BIB' and "Контрагент"='шемякин';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Период"='2022-06-01'   and "Проект"='(DCA) BIB' and "Контрагент"='шемякин';


update public.report_do_rasp
set "СтатьяУровень0"='Прибыль Компании'
where  "Период"='2024-08-01'   and "Статья"='Прочие доходы' and "Проект"='(DCA) AB';


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Период"='2024-08-01'   and "Статья"='Прочие доходы' and "Проект"='(DCA) AB';


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (переменные)'
where  "Период"='2024-08-01'   and "Статья"='Прочие доходы' and "Проект"='(DCA) AB';

update public.report_do_rasp
set "Категория"='Не наше!'
where  "Период"='2024-08-01'   and "Статья"='Прочие доходы' and "Проект"='(DCA) AB';


update public.report_do_rasp
set "СтатьяУровень0"='Прибыль Компании'
where  "Статья" like 'Проценты по займам%' and 
"Контрагент" in ('КПК "ИЛМА"',
'КПК "ИЛМА-КРЕДИТ"',
'КПК "АПАТИТЫ-КРЕДИТ"',
'КПК "СТИМУЛ"',
'АО "Свой Банк"',
'ГНБ-АК(ЗС)',
'КПК "ВЕЛЬСКИЙ"',
'КПК "ВЫГОЗЕРСКИЙ"',
'КПК "КОНДОПОГА"',
'КУРЦЕВ ИЛЬЯ АНДРЕЕВИЧ (ИП)',
'Зудин Сергей') and "Категория"<>'Выплата %' and 
"Признак"<>'Учредители' and "Признак"<>'учредители'
;


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where  "Статья" like 'Проценты по займам%' and 
"Контрагент" in ('КПК "ИЛМА"',
'КПК "ИЛМА-КРЕДИТ"',
'КПК "АПАТИТЫ-КРЕДИТ"',
'КПК "СТИМУЛ"',
'АО "Свой Банк"',
'ГНБ-АК(ЗС)',
'КПК "ВЕЛЬСКИЙ"',
'КПК "ВЫГОЗЕРСКИЙ"',
'КПК "КОНДОПОГА"',
'КУРЦЕВ ИЛЬЯ АНДРЕЕВИЧ (ИП)',
'Зудин Сергей') and "Категория"<>'Выплата %' and 
"Признак"<>'Учредители' and "Признак"<>'учредители'
;


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where  "Статья" like 'Проценты по займам%' and 
"Контрагент" in ('КПК "ИЛМА"',
'КПК "ИЛМА-КРЕДИТ"',
'КПК "АПАТИТЫ-КРЕДИТ"',
'КПК "СТИМУЛ"',
'АО "Свой Банк"',
'ГНБ-АК(ЗС)',
'КПК "ВЕЛЬСКИЙ"',
'КПК "ВЫГОЗЕРСКИЙ"',
'КПК "КОНДОПОГА"',
'КУРЦЕВ ИЛЬЯ АНДРЕЕВИЧ (ИП)',
'Зудин Сергей') and "Категория"<>'Выплата %' and 
"Признак"<>'Учредители' and "Признак"<>'учредители'
;
;


update public.report_do_rasp
set "СтатьяУровень0"='Прибыль Компании'
where   "СтатьяУровень2"<>'Отток по ОД (переменные)' and   "СтатьяУровень1"<>'Поступления по ОД' and   "СтатьяУровень2"<>'Отток по ОД (постоянные)'  and "Статья"='займы'  and "Период"<='2024-01-01' and "Сумма"<>-2500000.0 AND "Сумма"<>120000.0;


update public.report_do_rasp
set "СтатьяУровень1"='Отток по ОД'
where   "СтатьяУровень2"<>'Отток по ОД (переменные)' and   "СтатьяУровень1"<>'Поступления по ОД' and   "СтатьяУровень2"<>'Отток по ОД (постоянные)'  and "Статья"='займы'  and "Период"<='2024-01-01'  and "Сумма"<>-2500000.0 AND  "Сумма"<>120000.0;


update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where   "СтатьяУровень2"<>'Отток по ОД (переменные)' and   "СтатьяУровень1"<>'Поступления по ОД' and   "СтатьяУровень2"<>'Отток по ОД (постоянные)'  and "Статья"='займы'  and "Период"<='2024-01-01'  and "Сумма"<>-2500000.0 AND  "Сумма"<>120000.0;




update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where   "Проект" like '%вакуатор%' and "Признак"='Операционка';

update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where   "Проект" like '%РГСБ%' and "Признак"='Операционка';



update public.report_do_rasp
set "СтатьяУровень2"='Отток по ОД (постоянные)'
where   "Проект" like '%САВД%' and "Признак"='Операционка';





update public.report_do_rasp
set "СтатьяУровень1"='Финансы'
where  "Проект"='Общее' and "Категория"='займы' and "Контрагент"='киа'; 

update public.report_do_rasp
set "СтатьяУровень2"="Статья"
where  "Проект"='Общее' and "Категория"='займы' and "Контрагент"='киа'; 

update public.report_do_rasp
set "СтатьяУровень1"='Финансы'
where  "Проект"='Общее' and "Категория"='займы' and "Контрагент"='ткв'; 

update public.report_do_rasp
set "СтатьяУровень2"="Статья"
where  "Проект"='Общее' and "Категория"='займы' and "Контрагент"='ткв'; 

update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and Категория like 'внутреннее перемещение%';


update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and Категория like 'Прочие доходы%' and "Проект" not like '%MoneyMan%';

update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and Категория like 'финансы%' and "Признак"='Операционка';

update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and Категория like 'MoneyMan%' and  "Период">'2024-05-01';


update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and "Категория" like '%оход%';


update public.report_do_rasp
set "СтатьяУровень1"='Учредители!'
where  "СтатьяУровень1"='Учредители' and "Период">='2025-01-01';


update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and "Категория"='Неразобранные расходы' and  "Период"<='2022-12-01';

update public.report_do_rasp
set "СтатьяУровень1"='Финансы1'
where  "СтатьяУровень1"='Финансы' and "Категория" like '%чредители%'  and  "Период"<='2022-12-01';


update public.report_do_rasp
set "СтатьяУровень1"='Финансы'
where  "СтатьяУровень1"='Финансы1' and Категория like 'Прочие доходы%' and "Проект" like '%MoneyMan%';

update public.report_do_rasp
set "СтатьяУровень1"='Вне плана'
where  "СтатьяУровень1"='Результат по  ИД' and Категория like '%не плана%' and "Статья"='прочие' and "Период"='2024-03-01';

update public.report_do_rasp
set "Проект"='(DP) BMW'
where  "Проект"='(DP) BMW 2026';


update public.report_do_rasp
set "Проект"='(DCA) ID collect'
where  "Проект"='(DCA) ID';


update public.report_do_rasp
set "Проект"='(DР) Zenith'
where  "Проект"='(DP) Zenith 2026';

update public.report_do_rasp
set "Проект"='(DP) ALFA MKK(SMS) 2'
where  "Проект"='(DP) ALFA MKK(SMS 2)';

update public.report_do_rasp
set "Проект"='(DCA) Bystrobank'
where  "Проект"=' (DCA) Bystrobank';

update public.report_do_rasp
set "Проект"='(DP) Zenith'
where  "Проект"='(DР) Zenith';


update public.report_do_rasp set "Проект"='(DP) Zenith'  where  "Проект"='Car';
update public.report_do_rasp set "Проект"='(DCA) AB'  where  "Проект"='(DCA) AB ';
update public.report_do_rasp set "Проект"='(DCA) Fort'  where  "Проект"='((DCA) FORT';
update public.report_do_rasp set "Проект"='(DCA) Mercedes'  where  "Проект"='(DCA) mercedes';
update public.report_do_rasp set "Проект"='(DCA) Soyuz'  where  "Проект"='(DCA) Soyuz ';
update public.report_do_rasp set "Проект"='(DCA) tinkoff MBA'  where  "Проект"='(DCA) Tinkoff MBA';
update public.report_do_rasp set "Проект"='(DCA) Unicredit'  where  "Проект"='(DCA) unicredit ';
update public.report_do_rasp set "Проект"='(DCA) Unicredit'  where  "Проект"='(DCA) Unicredit ';
update public.report_do_rasp set "Проект"='(DCA) Uralsib'  where  "Проект"='(DCA) URALSIB';
update public.report_do_rasp set "Проект"='(DCA) Volkswagen'  where  "Проект"='(DCA) volkswagen';
update public.report_do_rasp set "Проект"='(DCA) WB Finans'  where  "Проект"='(DCA) WB FINANS';
update public.report_do_rasp set "Проект"='(DCA) Zaimer'  where  "Проект"='(DCA) ZAIMER';
update public.report_do_rasp set "Проект"='(DP) ABR Mercedes'  where  "Проект"='(DP) ABR Mercedes ';
update public.report_do_rasp set "Проект"='(DP) ALFA BIB'  where  "Проект"='(DP) ALFA BIB ';
update public.report_do_rasp set "Проект"='(DP) Denisova'  where  "Проект"='((DP) denisova';
update public.report_do_rasp set "Проект"='(DP) Moneyman'  where  "Проект"='(DP) MoneyMan';
update public.report_do_rasp set "Проект"='(DP) Unicredit'  where  "Проект"='(DP) unicredit';
update public.report_do_rasp set "Проект"='(DP) Unicredit'  where  "Проект"='(DP) Unicredit ';
update public.report_do_rasp set "Проект"='MoneyMan'  where  "Проект"='Moneyman';

update public.report_do_rasp set "Проект"='Общее'  where  "Проект"='ОБЩЕЕ';
update public.report_do_rasp set "Проект"='Общее'  where  "Проект"='Общее ';


update public.report_do_rasp set "СтатьяУровень3"='Изъятие'  where  "СтатьяУровень3"='Изъятия';

update public.report_do_rasp
set "Проект"='Общее'
where  "Проект" is null;


