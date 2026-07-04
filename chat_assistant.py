"""Чат с Claude по данным отчётности. Модель не видит и не пишет произвольный SQL — только
вызывает фиксированный набор read-only функций-инструментов, каждая из которых — тонкая
обёртка над уже существующими отчётными функциями (pl_report/fot_report/loans_report/
investment_report). Без ANTHROPIC_API_KEY ask() возвращает понятную ошибку — включается
само, как только ключ появится в окружении."""
import json
import logging
from datetime import date, datetime
from decimal import Decimal

from config import Config
import pl_report as pr
import fot_report as fr
import loans_report as lr
import investment_report as ir

logger = logging.getLogger('chat_assistant')

MODEL = 'claude-sonnet-5'
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = (
    'Ты — финансовый ассистент компании Alfa Collection. Отвечай на вопросы по отчётности '
    'кратко и по-русски, опираясь ТОЛЬКО на данные, полученные через вызов инструментов. '
    'Суммы в П&Л-отчётах (Свод1, Обзор) — в тысячах рублей, в инвестанализе и ФОТ — в рублях, '
    'если не указано иное. Если данных для ответа не хватает — прямо скажи об этом, не '
    'придумывай цифры. Годы и месяцы уточняй у пользователя, если не указаны явно.'
)

TOOLS = [
    {
        'name': 'get_pl_summary',
        'description': 'П&Л по месяцам за год (Свод1): выручка, переменные/постоянные расходы, GM, прибыль, чистая прибыль, тыс. руб.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'year': {'type': 'integer', 'description': 'Год, например 2026'},
                'pf': {'type': 'string', 'enum': ['факт', 'план', 'прогноз'], 'description': 'По умолчанию факт'},
            },
            'required': ['year'],
        },
    },
    {
        'name': 'get_overview',
        'description': 'Обзор ключевых показателей за год против прошлого года: выручка, прибыль, GM%, топ-5 портфелей по выручке.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'year': {'type': 'integer'},
                'pf': {'type': 'string', 'enum': ['факт', 'план', 'прогноз']},
            },
            'required': ['year'],
        },
    },
    {
        'name': 'get_investment_summary',
        'description': 'Свод по всем DP-портфелям (купленным портфелям долгов): дата покупки, ОСЗ, собираемость, остаток, денежный поток и окупаемость с учётом и без учёта распределения общих расходов.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_fot_summary',
        'description': 'ФОТ по подразделениям за год: суммы, СЗП, численность (без разбивки по отдельным сотрудникам).',
        'input_schema': {
            'type': 'object',
            'properties': {
                'year': {'type': 'integer'},
                'pf': {'type': 'string', 'enum': ['факт', 'план']},
            },
            'required': ['year'],
        },
    },
    {
        'name': 'get_loans_balance',
        'description': 'Остаток долга по займам помесячно за всю историю.',
        'input_schema': {
            'type': 'object',
            'properties': {'pf': {'type': 'string', 'enum': ['факт', 'план']}},
        },
    },
]


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


def _call_tool(name, args):
    try:
        if name == 'get_pl_summary':
            data = pr.svod1(args['year'], args.get('pf', 'факт'))
            return {
                'months': data['months'], 'profit': data['profit'], 'net_profit': data['net_profit'],
                'revenue_series': data.get('revenue_series'), 'variable_series': data.get('variable_series'),
                'fixed_series': data.get('fixed_series'), 'gm_series': data.get('gm_series'),
            }
        if name == 'get_overview':
            return pr.overview_data(args['year'], args.get('pf', 'факт'))
        if name == 'get_investment_summary':
            return ir.all_dp_summary()
        if name == 'get_fot_summary':
            data = fr.fot1(args['year'], args.get('pf', 'факт'))
            rows = [r for r in data['rows'] if r['kind'] != 'line']
            return {'months': data['months'], 'rows': rows}
        if name == 'get_loans_balance':
            return lr.loans_balance_series(args.get('pf', 'факт'))
        return {'error': f'Неизвестный инструмент: {name}'}
    except Exception:
        logger.exception('Ошибка инструмента %s', name)
        return {'error': 'Не удалось получить данные для этого инструмента'}


def ask(question, history=None):
    """history: [{"role": "user"/"assistant", "content": str}, ...] — только текстовые
    реплики предыдущих ходов (без tool-use блоков, чтобы не хранить их на клиенте)."""
    if not Config.ANTHROPIC_API_KEY:
        return {'error': 'Чат не настроен: добавьте ANTHROPIC_API_KEY в переменные окружения.'}

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
                    'content': json.dumps(_json_safe(result), ensure_ascii=False),
                })
        messages.append({'role': 'user', 'content': tool_results})

    return {'error': 'Не удалось получить ответ — слишком много обращений к данным для этого вопроса.'}
