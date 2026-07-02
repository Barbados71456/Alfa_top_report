# Alfa_top_report

Веб-дэшборд для топ-менеджмента: P&L, план/факт, портфели DCA/DP и инвестиционный анализ
на основе БД `alfa_collection` (Render Postgres). Заменяет ручные Excel-отчёты
(`Свод1/2`, `DashBoard_1-3`, инвестиционный анализ по портфелям).

## Локальный запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить DB_PASSWORD и остальные переменные
python set_password.py <username> <password>   # задать пароль одному из существующих пользователей
python app.py
```

Приложение поднимется на `http://localhost:5001`.

## Страницы

- `/svod` — сводный P&L по месяцам (факт/план), повторяет лист «Свод1/2».
- `/dashboard` — динамика по годам и портфелям, повторяет «DashBoard_1/2».
- `/portfolio` — универсальный шаблон для любого DCA/DP-портфеля (замена 29 листов
  `(DP) …` из файла инвестиционного анализа).
- `/investments` — результат инвестиционной деятельности по портфелям.
- `/classifier` — справочник классификации статей (`dim_level_report`), только для admin.

## Деплой на Render

Web Service из этого репозитория, переменные окружения — как в `.env.example`,
старт-команда `python app.py` (см. `render.yaml`).
