"""Сверка остатков по кошелькам: обороты считаются автоматически из
reporting.wallet_monthly (материализованное представление поверх
public."FinancialData"."Кошелек", только "п_ф"='факт'), а точки сверки (проверенный
факт-остаток на дату) пользователь вводит вручную и хранит в reporting.wallet_balances.
Между двумя точками сверки расчётный остаток = последняя точка + накопленные обороты;
на самой точке сверки видно расхождение (введено - расчёт).

Справочник кошельков (группа Счета/Касса/Спецсчета/Учредители/Прочее) — внешние
данные из эталонного Excel (лист "Карманы", 01_Сверка_счета.xlsx), которых нет в
FinancialData; хранится в reporting.wallets. Сопоставление "сырое имя Кошелек ->
канонический кошелёк" — в reporting.wallet_aliases, тот же паттерн, что
investment_report.py для DP-портфелей (пробелы/регистр/NBSP-вариации одного кошелька).
"""
from collections import defaultdict
from datetime import date

from db import execute, query, query_one

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

GROUP_ORDER = ['Счета', 'Касса', 'Спецсчета', 'Учредители', 'Прочее']

# Разовая коррекция знака: обороты по "ЗудинДЗ" за янв-апр 2026 в источнике
# (FinancialData) записаны с обратным знаком — подтверждено бухгалтерией.
_SIGN_FLIP_BY_NAME = {
    'ЗудинДЗ': {date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)},
}


def _apply_sign_flip(canonical_name, turnover):
    periods = _SIGN_FLIP_BY_NAME.get(canonical_name)
    if not periods:
        return turnover
    return {p: (-v if p in periods else v) for p, v in turnover.items()}

# Разово вытащено и сверено из листа "Карманы" эталонного Excel (01_Сверка_счета.xlsx):
# контрольные точки на 01.01 каждого года — столбцы "ОСТАТОК" на границах год-блоков.
# ВАЖНО: лист "Карманы" хранит суммы в ТЫСЯЧАХ РУБЛЕЙ (проверено: строка "АБ-АК", ячейка
# оборота за январь 2023 = 4887.968, что ровно в 1000 раз меньше суммы за тот же месяц
# в reporting.wallet_monthly, посчитанной из FinancialData."Сумма" в полных рублях) —
# поэтому все значения ниже умножены на 1000, чтобы быть в тех же единицах, что и
# автоматически считаемые обороты. "КИА" встречается как два разных кошелька (касса и
# учредительский заём) под одним и тем же сырым именем в FinancialData — раздвоено на
# "КИА (касса)"/"КИА (учредители)"; у второго нет живых оборотов, только исторические
# точки сверки. Для кошельков без точки на 2026 (появились только в этом году) взято
# последнее известное расчётное значение как приближение — уточняется обычной сверкой.
SEED_WALLETS = [
    ('Счета', 'АБ-АК', {'2023-01-01': 3546240.27, '2024-01-01': 7662313.44, '2025-01-01': 1027522.72, '2026-01-01': -4401477.11}),
    ('Счета', 'тф-ак', {'2023-01-01': 5647.77, '2024-01-01': 297568.13, '2025-01-01': 1015644.25, '2026-01-01': 47.0}),
    ('Счета', 'СБ-АК', {'2023-01-01': 48114.66, '2024-01-01': 130432.87, '2025-01-01': -22346.33, '2026-01-01': 157268.7}),
    ('Счета', 'ГНБ-АК', {'2023-01-01': 557844.64, '2024-01-01': 82898.0, '2025-01-01': 6148.94, '2026-01-01': 9.99}),
    ('Счета', 'ГНБ-АК(ЗС)', {'2024-01-01': 1216408.92, '2025-01-01': -1265312.57, '2026-01-01': 407191.72}),
    ('Счета', 'АБ-Аврора', {'2023-01-01': 6911.92, '2024-01-01': 681038.49, '2025-01-01': 696678.48, '2026-01-01': 74188.76}),
    ('Счета', 'СБ-Аврора', {'2023-01-01': 52713.98, '2024-01-01': 86066.98, '2025-01-01': 24787.78, '2026-01-01': 36596.82}),
    # Без seed-точки: реальные обороты (депозит открыт и почти полностью закрыт в
    # 2025, новый депозит собран в мае-июне 2026) сами дают ~12 330 000 к июню 2026 —
    # ровно то, что было в Excel; готовая точка сверки задваивала бы её.
    ('Счета', 'ГНБ-АК(депозит)', {}),
    ('Счета', 'АБ-АК(депозит)', {'2026-01-01': 1000000.0}),
    ('Счета', 'АБ-КАСМ', {'2023-01-01': 1235551.87, '2024-01-01': 588832.48, '2025-01-01': 46555.21, '2026-01-01': 6186.49}),
    ('Счета', 'АБ-АБР', {'2024-01-01': 1473504.82, '2025-01-01': 6866.66, '2026-01-01': 668705.08}),
    ('Касса', 'ТКВ', {'2023-01-01': -321301.27, '2024-01-01': -1010121.88, '2025-01-01': -2286124.44, '2026-01-01': -1514646.37}),
    ('Касса', 'КИА (касса)', {'2026-01-01': -5105188.28}),
    ('Касса', 'Алия', {'2026-01-01': 294870.93}),
    ('Касса', 'Расчет', {'2026-01-01': -319123.23}),
    ('Касса', 'Зудин', {'2023-01-01': 544737.76, '2024-01-01': 1226062.32, '2025-01-01': 1517479.48, '2026-01-01': 765404.72}),
    ('Спецсчета', 'СпецДивСчет', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Спецсчета', 'Спец счёт КЗ', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Спецсчета', 'Залог (сберлизинг)', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Спецсчета', 'СпецНалСчет', {'2023-01-01': 0.0, '2024-01-01': 200000.0, '2025-01-01': 200000.0, '2026-01-01': 200000.0}),
    ('Учредители', 'КАМ', {'2023-01-01': 138837.84, '2024-01-01': 208137.84, '2025-01-01': 208137.84, '2026-01-01': 0.0}),
    ('Учредители', 'БМ', {'2023-01-01': -128.48, '2024-01-01': -128.48, '2025-01-01': -128.48, '2026-01-01': 0.0}),
    ('Учредители', 'КИА (учредители)', {'2023-01-01': 57300.0, '2024-01-01': 57300.0, '2025-01-01': 57300.0, '2026-01-01': 0.0}),
    ('Прочее', 'КИА_займ', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Прочее', 'Абуталиев', {'2023-01-01': 79737.52, '2025-01-01': 0.0, '2026-01-01': 10000000.0}),
    ('Прочее', 'шемякин', {'2023-01-01': 79737.52, '2024-01-01': -59130.82, '2025-01-01': -5756.69, '2026-01-01': -5756.69}),
    ('Прочее', 'Дима', {'2023-01-01': 0.0, '2024-01-01': 33035.85, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Прочее', 'рома', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Прочее', 'зюзина', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Прочее', 'ДЗ Гомес', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
    ('Прочее', 'баланс', {'2023-01-01': 515000.0, '2024-01-01': 515000.0, '2025-01-01': 515000.0, '2026-01-01': 515000.0}),
    ('Прочее', 'ЗудинДЗ', {'2023-01-01': 0.0, '2024-01-01': 2000000.0, '2025-01-01': 2000000.0, '2026-01-01': 1400000.0}),
    ('Прочее', 'ДЗ эксАврора', {'2023-01-01': 464952.45, '2024-01-01': 464952.45, '2025-01-01': 464952.45, '2026-01-01': 464952.45}),
    ('Прочее', 'ДЗ юрт', {'2023-01-01': 82000.0, '2024-01-01': 82000.0, '2025-01-01': 82000.0, '2026-01-01': 82000.0}),
    ('Прочее', 'гсм', {'2023-01-01': -248.85, '2024-01-01': -248.85, '2025-01-01': -248.85, '2026-01-01': -248.85}),
    ('Прочее', 'Лисов', {'2023-01-01': 0.0, '2024-01-01': 0.0, '2025-01-01': 0.0, '2026-01-01': 0.0}),
]


def seed_wallets():
    """Разовое заполнение справочника кошельков и точек сверки из SEED_WALLETS. Не
    перезаписывает уже существующие (в т.ч. поправленные вручную) строки."""
    for group, name, balances in SEED_WALLETS:
        execute(
            'INSERT INTO reporting.wallets (canonical_name, group_name) VALUES (%s, %s) ON CONFLICT (canonical_name) DO NOTHING',
            (name, group)
        )
        wallet = query_one('SELECT id FROM reporting.wallets WHERE canonical_name = %s', (name,))
        for period, balance in balances.items():
            execute(
                '''INSERT INTO reporting.wallet_balances (wallet_id, period, balance, created_by)
                   VALUES (%s, %s, %s, 'seed') ON CONFLICT (wallet_id, period) DO NOTHING''',
                (wallet['id'], period, balance)
            )
    sync_aliases()


def sync_aliases():
    """Автопривязка новых "Кошелек" из reporting.wallet_monthly к каноническим
    кошелькам по точному совпадению имени без учёта пробелов/регистра/NBSP. Для
    всего, что не совпало, — новый канонический кошелёк группы "Прочее" (донастраивается
    на /wallets/admin) — ни один реальный кошелёк не остаётся без карточки. Новая
    карточка заводится один раз НА НОРМАЛИЗОВАННУЮ группу имён (а не на каждую сырую
    строку отдельно), иначе регистровые варианты одного нового кошелька (например
    "АБ2"/"аб2") расползались бы по разным карточкам."""
    execute('''
        INSERT INTO reporting.wallet_aliases (wallet_id, raw_name)
        SELECT DISTINCT w.id, m.wallet_raw
        FROM reporting.wallet_monthly m
        JOIN reporting.wallets w
          ON lower(trim(replace(m.wallet_raw, chr(160), ' '))) = lower(trim(w.canonical_name))
        ON CONFLICT (raw_name) DO NOTHING
    ''')
    execute('''
        INSERT INTO reporting.wallets (canonical_name)
        SELECT DISTINCT ON (lower(trim(replace(m.wallet_raw, chr(160), ' ')))) m.wallet_raw
        FROM reporting.wallet_monthly m
        WHERE NOT EXISTS (SELECT 1 FROM reporting.wallet_aliases a WHERE a.raw_name = m.wallet_raw)
        ORDER BY lower(trim(replace(m.wallet_raw, chr(160), ' '))), m.wallet_raw
        ON CONFLICT (canonical_name) DO NOTHING
    ''')
    execute('''
        INSERT INTO reporting.wallet_aliases (wallet_id, raw_name)
        SELECT w.id, m.wallet_raw
        FROM reporting.wallet_monthly m
        JOIN reporting.wallets w
          ON lower(trim(replace(m.wallet_raw, chr(160), ' '))) = lower(trim(replace(w.canonical_name, chr(160), ' ')))
        WHERE NOT EXISTS (SELECT 1 FROM reporting.wallet_aliases a WHERE a.raw_name = m.wallet_raw)
        ON CONFLICT (raw_name) DO NOTHING
    ''')


def get_wallets():
    order_case = 'CASE group_name ' + ' '.join(f"WHEN '{g}' THEN {i}" for i, g in enumerate(GROUP_ORDER)) + f' ELSE {len(GROUP_ORDER)} END'
    return query(f'SELECT * FROM reporting.wallets ORDER BY {order_case}, group_name, canonical_name')


def get_wallet_aliases(wallet_id):
    rows = query('SELECT raw_name FROM reporting.wallet_aliases WHERE wallet_id = %s ORDER BY raw_name', (wallet_id,))
    return [r['raw_name'] for r in rows]


def get_unmatched_wallets():
    """"Кошелек" значения из wallet_monthly без привязки к карточке кошелька."""
    rows = query('''
        SELECT DISTINCT m.wallet_raw
        FROM reporting.wallet_monthly m
        WHERE NOT EXISTS (SELECT 1 FROM reporting.wallet_aliases a WHERE a.raw_name = m.wallet_raw)
        ORDER BY 1
    ''')
    return [r['wallet_raw'] for r in rows]


def _wallet_by_name(canonical_name):
    wallet = query_one('SELECT * FROM reporting.wallets WHERE canonical_name = %s', (canonical_name,))
    if not wallet:
        return None, []
    return wallet, get_wallet_aliases(wallet['id'])


def _turnover_for_raw_names(raw_names):
    """{period: amount} — суммарный оборот по списку сырых имён "Кошелек"."""
    if not raw_names:
        return {}
    rows = query(
        'SELECT period, SUM(amount) AS amount FROM reporting.wallet_monthly WHERE wallet_raw = ANY(%s) GROUP BY 1',
        (raw_names,)
    )
    return {r['period']: float(r['amount'] or 0) for r in rows}


def _all_wallets_turnover():
    """{wallet_id: {period: amount}} — один проход по wallet_monthly для всех
    кошельков сразу (без N+1 запросов на свод)."""
    rows = query('''
        SELECT a.wallet_id AS wid, m.period, SUM(m.amount) AS amount
        FROM reporting.wallet_monthly m
        JOIN reporting.wallet_aliases a ON a.raw_name = m.wallet_raw
        GROUP BY 1, 2
    ''')
    by_wallet = defaultdict(dict)
    for r in rows:
        by_wallet[r['wid']][r['period']] = float(r['amount'] or 0)
    return by_wallet


def _all_wallets_checkpoints():
    """{wallet_id: {period: balance}} — все точки сверки одним проходом."""
    rows = query('SELECT wallet_id, period, balance FROM reporting.wallet_balances')
    by_wallet = defaultdict(dict)
    for r in rows:
        by_wallet[r['wallet_id']][r['period']] = float(r['balance'])
    return by_wallet


def _month_range(start, end):
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def _build_wallet_rows(turnover, checkpoints, until=None):
    """turnover: {period: amount}, checkpoints: {period: balance} — точка сверки
    считается остатком на НАЧАЛО этого месяца (до его оборота), как в исходном Excel
    (столбец "ОСТАТОК" на начало года -> обороты за год -> следующий "ОСТАТОК").
    Между точками остаток накапливается автоматически; на самой точке сверки
    расхождение = введено - расчёт (то, что накопилось бы без сверки). until —
    расширить диапазон минимум до этого периода, даже если у кошелька давно нет
    оборотов/точек сверки (иначе остаток "застревает" на последней реальной записи
    и не переносится вперёд на текущий год)."""
    periods = set(turnover.keys()) | set(checkpoints.keys())
    if until is not None:
        periods.add(until)
    if not periods:
        return []
    all_periods = _month_range(min(periods), max(periods))

    rows = []
    running = None
    for p in all_periods:
        amt = turnover.get(p, 0.0)
        entered = checkpoints.get(p)
        if entered is not None:
            discrepancy = (entered - running) if running is not None else None
            opening = entered
        else:
            discrepancy = None
            opening = running
        opening = opening or 0.0
        closing = opening + amt
        running = closing
        rows.append({
            'period': p, 'label': f'{MONTHS_RU[p.month - 1]} {p.year}',
            'opening': opening, 'turnover': amt, 'entered': entered, 'discrepancy': discrepancy,
            'balance': closing,
        })
    return rows


def wallet_detail(canonical_name, year=None):
    """Карточка кошелька за один год (пользователь листает года по одному, не
    сплошной таблицей с 2021-го). "Текущий расчётный остаток" и "последняя точка
    сверки" считаются от ПОЛНОЙ истории (не зависят от просматриваемого года —
    это факты "на сейчас"). year='all' — вся история без нарезки (для экспорта)."""
    wallet, aliases = _wallet_by_name(canonical_name)
    if wallet is None:
        return None
    turnover = _apply_sign_flip(canonical_name, _turnover_for_raw_names(aliases))
    checkpoints = {r['period']: float(r['balance']) for r in query(
        'SELECT period, balance FROM reporting.wallet_balances WHERE wallet_id = %s', (wallet['id'],)
    )}
    rows = _build_wallet_rows(turnover, checkpoints)
    last_checkpoint_row = next((r for r in reversed(rows) if r['entered'] is not None), None)

    available_years = sorted({r['period'].year for r in rows})
    if year == 'all':
        year_rows = rows
    else:
        if not available_years:
            year = None
        elif year not in available_years:
            year = available_years[-1]
        year_rows = [r for r in rows if r['period'].year == year]

    return {
        'wallet': wallet, 'aliases': aliases, 'rows': year_rows,
        'all_years': available_years, 'year': year,
        'current_balance': rows[-1]['balance'] if rows else None,
        'last_checkpoint': last_checkpoint_row,
    }


def all_wallets_reconciliation():
    """Свод-сверка на текущий месяц: обороты помесячно за календарный год (для
    контекста динамики) + расчётный остаток на сейчас + место для ручного ввода
    факта за текущий месяц прямо в своде (без захода в карточку кошелька) —
    расхождение (введено - расчёт до этой точки) сразу видно зелёной/красной
    отметкой. Кошельки без входящего остатка И без оборотов за этот год
    скрываются (и группа целиком, если после этого в ней не осталось строк) —
    кошелёк с висящим входящим остатком (например, старая ДЗ), но без оборотов
    в этом году, всё равно показывается.
    "Остаток на сейчас" считается напрямую как входящий остаток + сумма 12
    месяцев из этой же строки (а не отдельным накопительным расчётом), чтобы
    правка входящего остатка сразу отражалась в этой колонке."""
    today = date.today()
    year = today.year
    period = today.replace(day=1)
    months = [date(year, m, 1) for m in range(1, 13)]
    until = date(year, 12, 1)

    wallets = get_wallets()
    turnover_by_wallet = _all_wallets_turnover()
    checkpoints_by_wallet = _all_wallets_checkpoints()
    jan_period = date(year, 1, 1)

    by_group = defaultdict(list)
    for w in wallets:
        turnover = _apply_sign_flip(w['canonical_name'], turnover_by_wallet.get(w['id'], {}))
        checkpoints = checkpoints_by_wallet.get(w['id'], {})
        # until гарантирует, что остаток "докатится" до текущего года даже для
        # кошельков без активности много лет (иначе opening_year ниже был бы 0).
        rows = _build_wallet_rows(turnover, checkpoints, until=until)
        row_months = [turnover.get(m, 0.0) for m in months]
        jan_row = next((r for r in rows if r['period'] == jan_period), None)
        opening_year = jan_row['opening'] if jan_row else 0.0
        current_balance = opening_year + sum(row_months)
        # Скрываем только по-настоящему пустые строки (нет ни входящего остатка,
        # ни оборотов за год) — кошелёк с входящей ДЗ, но без оборотов в этом
        # году (например, висящая дебиторка), всё равно должен быть виден.
        if abs(opening_year) < 0.005 and all(abs(v) < 0.005 for v in row_months):
            continue
        cur_row = next((r for r in rows if r['period'] == period), None)
        entered_now = cur_row['entered'] if cur_row else None
        discrepancy_now = cur_row['discrepancy'] if cur_row else None
        match_now = abs(discrepancy_now) < 0.01 if discrepancy_now is not None else None
        by_group[w['group_name']].append({
            'id': w['id'], 'name': w['canonical_name'],
            'months': row_months,
            'opening_year': opening_year, 'current_balance': current_balance,
            'entered_now': entered_now, 'discrepancy_now': discrepancy_now, 'match_now': match_now,
        })

    ordered_groups = GROUP_ORDER + sorted(g for g in by_group if g not in GROUP_ORDER)
    out_rows = []
    totals_months = [0.0] * 12
    total_opening = 0.0
    total_balance = 0.0
    for group in ordered_groups:
        items = by_group.get(group)
        if not items:
            continue
        group_months = [sum(i['months'][idx] for i in items) for idx in range(12)]
        group_opening = sum(i['opening_year'] for i in items)
        group_balance = sum(i['current_balance'] for i in items)
        for idx in range(12):
            totals_months[idx] += group_months[idx]
        total_opening += group_opening
        total_balance += group_balance
        row_id = f'wgroup-{group}'
        out_rows.append({
            'kind': 'group', 'row_id': row_id, 'label': group, 'months': group_months,
            'opening_year': group_opening, 'current_balance': group_balance,
        })
        for i in items:
            out_rows.append({'kind': 'wallet', 'parent_id': row_id, **i})
    out_rows.append({
        'kind': 'total', 'label': 'Итого', 'months': totals_months,
        'opening_year': total_opening, 'current_balance': total_balance,
    })

    return {
        'rows': out_rows, 'months': months,
        'month_labels': [MONTHS_RU[m.month - 1] for m in months],
        'year': year, 'period': period,
        'period_label': f'{MONTHS_RU[period.month - 1]} {year}',
    }


def save_reconciliation(entries, username):
    """entries: {wallet_id: значение из формы (str)} — сохраняет точку сверки на
    текущий месяц для каждого непустого значения. Возвращает число сохранённых."""
    period = date.today().replace(day=1)
    saved = 0
    for wallet_id, raw_value in entries.items():
        raw_value = (raw_value or '').strip()
        if not raw_value:
            continue
        add_balance_entry(int(wallet_id), period, raw_value, None, username)
        saved += 1
    return saved, period


def add_balance_entry(wallet_id, period, balance, notes, username):
    execute(
        '''INSERT INTO reporting.wallet_balances (wallet_id, period, balance, notes, created_by)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (wallet_id, period) DO UPDATE SET balance = EXCLUDED.balance, notes = EXCLUDED.notes,
               created_by = EXCLUDED.created_by, created_at = now()''',
        (wallet_id, period, balance, notes or None, username)
    )


def update_wallet(wallet_id, group_name, notes):
    execute(
        'UPDATE reporting.wallets SET group_name = %s, notes = %s, updated_at = now() WHERE id = %s',
        (group_name or 'Прочее', notes or None, wallet_id)
    )


def create_wallet(canonical_name, group_name, notes):
    execute(
        'INSERT INTO reporting.wallets (canonical_name, group_name, notes) VALUES (%s, %s, %s)',
        (canonical_name, group_name or 'Прочее', notes or None)
    )


def add_alias(wallet_id, raw_name):
    execute(
        'INSERT INTO reporting.wallet_aliases (wallet_id, raw_name) VALUES (%s, %s) ON CONFLICT (raw_name) DO NOTHING',
        (wallet_id, raw_name)
    )


def remove_alias(raw_name):
    execute('DELETE FROM reporting.wallet_aliases WHERE raw_name = %s', (raw_name,))


def export_summary(data):
    headers = (['Группа / кошелёк', f'Входящий остаток на 01.01.{data["year"]}']
               + [f'{lbl} {data["year"]}' for lbl in data['month_labels']]
               + ['Остаток на сейчас', f'Введено ({data["period_label"]})', 'Сверено'])
    out = []
    for r in data['rows']:
        if r['kind'] in ('group', 'total'):
            out.append([r['label'], r['opening_year'], *r['months'], r['current_balance'], None, None])
        else:
            out.append([f"  {r['name']}", r['opening_year'], *r['months'], r['current_balance'],
                        r.get('entered_now'), r.get('match_now')])
    return [('Сверка счетов - свод', headers, out)]


def export_detail(data):
    headers = ['Остаток на начало года', 'Период', 'Оборот', 'Расчётный остаток', 'Введено при сверке', 'Расхождение']
    rows = [
        [r['opening'] if i == 0 else None, r['label'], r['turnover'], r['balance'], r['entered'], r['discrepancy']]
        for i, r in enumerate(data['rows'])
    ]
    return [(data['wallet']['canonical_name'][:31], headers, rows)]


def wallet_ledger(canonical_name, date_from=None, date_to=None):
    """Сырые проводки по кошельку из public.FinancialData (не агрегат) — для
    отчёта "Проводки": какие конкретно строки формируют оборот, за произвольный
    период. Только "факт" — план/прогноз тоже встречаются с реальным "Кошелек"
    (проверено в БД: 6.4к план + 48.2к прогноз против 155.5к факт), но это не
    настоящие проводки, а плановые данные; wallet_monthly для сверки остатков
    уже фильтрует так же. Всегда "до распределения" — строки-дубликаты,
    появляющиеся при распределении косвенных расходов по проектам, помечены
    "Распределение" = 'распределение' (и служебным "Кошелек" = 'распределение',
    см. schema.sql reporting.wallet_monthly) и не являются реальным движением
    денег по кошельку; для настоящих кошельков это не отфильтровывает ни одной
    строки (проверено в БД — все они и так 'до распределения'), но защищает от
    задвоения, если в данных когда-нибудь появится обратное."""
    wallet, aliases = _wallet_by_name(canonical_name)
    if wallet is None:
        return None
    if not aliases:
        return {'wallet': wallet, 'aliases': aliases, 'rows': [], 'date_from': date_from, 'date_to': date_to}
    sql = '''SELECT "Дата" AS date, "Период" AS period, "Кошелек" AS wallet_raw,
                    "Тип Кошелька" AS wallet_type, "Статья" AS statya,
                    "СтатьяУровень3" AS statya3, "Проект" AS project,
                    "Контрагент" AS contragent, "Сумма" AS amount,
                    "п_ф" AS pf, "Комментарии" AS comment
             FROM public."FinancialData"
             WHERE "Кошелек" = ANY(%s) AND "Распределение" = 'до распределения'
               AND "п_ф" = 'факт\''''
    params = [aliases]
    if date_from:
        sql += ' AND "Дата" >= %s'
        params.append(date_from)
    if date_to:
        sql += ' AND "Дата" <= %s'
        params.append(date_to)
    sql += ' ORDER BY "Дата"'
    rows = query(sql, params)
    return {'wallet': wallet, 'aliases': aliases, 'rows': rows, 'date_from': date_from, 'date_to': date_to}


def export_ledger(data):
    headers = ['Дата', 'Период', 'Кошелек', 'Тип Кошелька', 'Статья', 'СтатьяУровень3',
               'Проект', 'Контрагент', 'Сумма', 'п_ф', 'Комментарии']
    rows = [
        [r['date'], r['period'], r['wallet_raw'], r['wallet_type'], r['statya'], r['statya3'],
         r['project'], r['contragent'], r['amount'], r['pf'], r['comment']]
        for r in data['rows']
    ]
    return [(data['wallet']['canonical_name'][:31], headers, rows)]
