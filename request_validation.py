"""Validate public report parameters before running database queries."""
from datetime import date

PF_VALUES = {'факт', 'план', 'прогноз'}


def integer(value, name, minimum=1, maximum=9999):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: ожидается целое число') from None
    if not minimum <= result <= maximum:
        raise ValueError(f'{name}: допустимо от {minimum} до {maximum}')
    return result


def series(raw):
    if raw is None or not raw.strip():
        return None
    result = []
    for part in raw.split(','):
        pf, _, year = part.partition(':')
        if pf not in PF_VALUES:
            raise ValueError('Колонка сравнения: ожидается факт, план или прогноз')
        result.append((pf, integer(year, 'Год')))
    if len(result) > 20:
        raise ValueError('Допустимо не более 20 колонок сравнения')
    return result


def deltas(raw):
    if raw is None:
        return None
    if not raw.strip():
        return []
    result = []
    for part in raw.split(','):
        i, _, j = part.partition('-')
        result.append((integer(i, 'Колонка A', 0, 19), integer(j, 'Колонка B', 0, 19)))
    return result


def validate_report_args(args, endpoint):
    if args.get('pf') is not None and args['pf'] not in PF_VALUES:
        raise ValueError('Неизвестный показатель: ожидается факт, план или прогноз')
    if args.get('year'):
        if not (endpoint == 'wallets_detail' and args['year'] == 'all'):
            integer(args['year'], 'Год')
    if args.get('month') is not None and endpoint != 'api_cbr_cell_detail':
        integer(args['month'], 'Месяц', 1, 12)
    dates = {}
    for field in ('period', 'date_from', 'date_to'):
        if args.get(field):
            try:
                dates[field] = date.fromisoformat(args[field])
            except ValueError:
                raise ValueError(f'{field}: ожидается дата ГГГГ-ММ-ДД') from None
    if dates.get('date_from') and dates.get('date_to') and dates['date_from'] > dates['date_to']:
        raise ValueError('Начало периода не может быть позже окончания')
    for field in ('a', 'b'):
        if args.get(field):
            parts = args[field].split(':')
            if len(parts) != 3 or parts[0] not in PF_VALUES:
                raise ValueError(f'{field}: ожидается показатель:год:месяц')
            integer(parts[1], 'Год')
            integer(parts[2], 'Месяц', 1, 12)
    if args.get('mode') and args['mode'] not in ('period', 'ytd', 'month'):
        raise ValueError('Неизвестный режим расчёта')
    columns = series(args.get('series'))
    comparisons = deltas(args.get('deltas'))
    if columns and comparisons and any(max(i, j) >= len(columns) for i, j in comparisons):
        raise ValueError('Отклонение ссылается на отсутствующую колонку сравнения')
