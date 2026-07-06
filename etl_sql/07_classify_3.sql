update public."FinancialData" set "Проект"='(DP) ALFA RB' where ("Период"='2020-04-01' or "Период"='2020-05-01') and "Признак"='Инвестиции';


update public."FinancialData" set "Проект"='(DP) ALFA BIB 2' where "Проект" ilike '%(DP) ABR%' and  "Проект" not like '(DP) ABR AB';

update public."FinancialData" set "Проект"='(DP) Moneyman' where ("Период"='2022-11-01') and "Признак"='Инвестиции' and Проект='MoneyMan';


update public."FinancialData" set "Проект"='(DP) ALFA MKK(SMS) 2' where "Распределение"='до распределения' and "Период"='2025-03-01'  and "Признак"='Инвестиции'  and "Проект"='(DP) ALFA MKK(SMS)';


update public."FinancialData" set "Проект"='(DP) ALFA BIB' where "Проект" ilike '%(DP) ALFA BIB-%';

update public."FinancialData" set "Проект"='(DP) Aurora' where "Проект" ilike '%(DP) Aurora-%';

update public."FinancialData" set "Проект"='(DP) Mercedes' where "Проект" ilike '%(DP) Mercedes 4%';

update public."FinancialData" set "Проект"='(DP) ABC' where "Проект" ilike '%(DP) ABK%';

update public."FinancialData" set "Проект"='(DP) Investagro' where "Проект" ilike '%(DP) individual%' and "Контрагент" like '%ООО "ССГ%';
update public."FinancialData" set "Проект"='(DP) Isakov'     where "Проект" ilike '%(DP) individual%' and "Контрагент"='ИП Исаков Ядадья Мататьяевич';

update public."FinancialData" set "Проект"='(DP) Bogatskii' where "Период"='2024-09-01' and "Контрагент" ilike '%ИП Богацкий Роман Вадимович%';
update public."FinancialData" set "СтатьяСвод"='06. Инвестиции (+/-)' where "Период"='2024-09-01' and "Контрагент" ilike '%ИП Богацкий Роман Вадимович%';

update public."FinancialData" set "Проект"='(DP) Bokova' where  "Распределение"='до распределения' and "Период"='2023-02-01' and "Контрагент"='Бокова Марина Николаевна';
update public."FinancialData" set "СтатьяСвод"='06. Инвестиции (+/-)' where  "Распределение"='до распределения' and "Период"='2023-02-01' and "Контрагент"='Бокова Марина Николаевна';
