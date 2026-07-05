"""Чат-советник по покупке портфеля ДЗ: перед оценкой сделки задаёт уточняющие вопросы
(цена, ОСЗ/номинал, к-во ДО, тип долга, кредитор/источник, регионы должников), затем
сравнивает параметры со статистикой уже купленных портфелей (investment_report) и CBR
(cbr_report) и даёт рекомендацию с обоснованием цифрами.

ТОЛЬКО ЧТЕНИЕ: здесь и в подключаемых модулях используется исключительно db.query —
db.execute (запись/изменение БД) не импортируется и не может быть вызван моделью ни при
каких условиях (см. investment_report.all_dp_summary/cbr_report.overall_by_month — обе
функции только читают данные)."""
import json
import logging

from config import Config
from db import query
import investment_report as ir
import cbr_report as cr

logger = logging.getLogger('portfolio_advisor')

MODEL = 'claude-sonnet-5'
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = (
    'Ты — советник по покупке портфелей долгов (цессия/агентское обслуживание) для '
    'Alfa Collection. У тебя НЕТ и не может быть доступа на запись или удаление данных — '
    'только чтение и анализ, ты физически не можешь ничего изменить в базе. '
    'Твоя задача перед оценкой новой сделки — СНАЧАЛА задать уточняющие вопросы, если '
    'информации не хватает: цена покупки, ОСЗ (номинал долга) или основной долг, '
    'количество договоров (ДО), тип долга (цессия/агентский), текущий или предыдущий '
    'кредитор (для сравнения по CBR), регион(ы) должников, средний возраст просрочки. '
    'Только когда параметры сделки понятны, вызывай инструменты сравнения со '
    'статистикой (похожие уже купленные портфели, бенчмарк CBR по кредитору/региону) и '
    'дай рекомендацию: покупать / торговаться по цене / не покупать, с обоснованием '
    'конкретными цифрами (медианная окупаемость и собираемость похожих сделок, '
    'ожидаемый CBR). Если статистики недостаточно — прямо скажи об этом, не выдумывай '
    'цифры. Отвечай по-русски, кратко и по делу.'
)

TOOLS = [
    {
        'name': 'compare_to_similar_portfolios',
        'description': 'Похожие уже купленные DP-портфели (по цене и/или номиналу ОСЗ, в разумном диапазоне) — медианная окупаемость и собираемость для сравнения с оцениваемой сделкой.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'price_rub': {'type': 'number', 'description': 'Предполагаемая цена покупки, руб.'},
                'face_value_rub': {'type': 'number', 'description': 'ОСЗ / номинал долга, руб.'},
            },
        },
    },
    {
        'name': 'get_cbr_benchmark',
        'description': 'Средний CBR (cash back rate, месячная собираемость) от ОСЗ за последний доступный месяц — в целом, по текущему кредитору и/или по региону должников. Ориентир ожидаемой месячной собираемости для новой сделки.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'creditor': {'type': 'string', 'description': 'Текущий/предыдущий кредитор (как в CBR-отчёте), опционально'},
                'region': {'type': 'string', 'description': 'Регион должников, опционально'},
            },
        },
    },
]


def _median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def compare_to_similar_portfolios(price_rub=None, face_value_rub=None, tolerance=3.0):
    rows = ir.all_dp_summary()
    candidates = []
    for r in rows:
        if not r['price_rub'] or not r['face_value_rub']:
            continue
        if price_rub and not (price_rub / tolerance <= r['price_rub'] <= price_rub * tolerance):
            continue
        if face_value_rub and not (face_value_rub / tolerance <= r['face_value_rub'] <= face_value_rub * tolerance):
            continue
        candidates.append(r)
    used_fallback = False
    if not candidates:
        candidates = [r for r in rows if r['price_rub'] and r['face_value_rub']]
        used_fallback = True
    return {
        'count': len(candidates),
        'used_full_sample_fallback': used_fallback,
        'sample_names': [r['name'] for r in candidates[:10]],
        'median_collection_pct': _median([r['collection_pct'] for r in candidates]),
        'median_payback_months_no_alloc': _median([r['payback_no_alloc'] for r in candidates]),
        'median_payback_months_with_alloc': _median([r['payback_with_alloc'] for r in candidates]),
    }


def get_cbr_benchmark(creditor=None, region=None):
    months = cr.get_available_months()
    if not months:
        return {'error': 'Нет данных CBR'}
    latest = months[-1]
    sql = 'SELECT SUM(total_debt) AS td, SUM(payment_amount) AS pay FROM cbr.monthly WHERE month = %s'
    params = [latest]
    if creditor:
        sql += ' AND creditor = %s'
        params.append(creditor)
    if region:
        sql += ' AND region = %s'
        params.append(region)
    row = query(sql, params)[0]
    total_debt = float(row['td'] or 0)
    payment = float(row['pay'] or 0)
    return {
        'month': latest.strftime('%m.%Y'),
        'cbr_osz_pct': (payment / total_debt * 100) if total_debt else None,
        'sample_total_debt_rub': total_debt,
    }


def _call_tool(name, args):
    try:
        if name == 'compare_to_similar_portfolios':
            return compare_to_similar_portfolios(args.get('price_rub'), args.get('face_value_rub'))
        if name == 'get_cbr_benchmark':
            return get_cbr_benchmark(args.get('creditor'), args.get('region'))
        return {'error': f'Неизвестный инструмент: {name}'}
    except Exception:
        logger.exception('Ошибка инструмента %s', name)
        return {'error': 'Не удалось получить данные для этого инструмента'}


def ask(question, history=None):
    if not Config.ANTHROPIC_API_KEY:
        return {'error': 'Советник не настроен: добавьте ANTHROPIC_API_KEY в переменные окружения.'}

    import anthropic
    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    messages = [{'role': m['role'], 'content': m['content']} for m in (history or [])]
    messages.append({'role': 'user', 'content': question})

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=1500, system=SYSTEM_PROMPT,
                tools=TOOLS, messages=messages,
            )
        except Exception:
            logger.exception('Ошибка обращения к Anthropic API')
            return {'error': 'Не удалось связаться с Claude. Попробуйте позже.'}

        if resp.stop_reason != 'tool_use':
            text = ''.join(block.text for block in resp.content if block.type == 'text')
            return {'answer': text}

        messages.append({'role': 'assistant', 'content': resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == 'tool_use':
                result = _call_tool(block.name, block.input)
                tool_results.append({
                    'type': 'tool_result', 'tool_use_id': block.id,
                    'content': json.dumps(result, ensure_ascii=False),
                })
        messages.append({'role': 'user', 'content': tool_results})

    return {'error': 'Не удалось получить ответ — слишком много обращений к данным для этого вопроса.'}
