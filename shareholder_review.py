"""Shareholder commentary for the two Svod1 windows. Money stays server-calculated."""
import hashlib
import json
import logging
import re
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

import httpx

from chat_assistant import BASE_URL
from config import Config

log = logging.getLogger(__name__)
CACHE = (Path('/data') if Path('/data').is_dir() else Path(tempfile.gettempdir())) / 'svod1-commentary.sqlite3'
LEASE = 270
BASES = ('прогноза', 'прошлого года')


def money(value, signed=False):
    millions = abs(value) >= 1000
    number = abs(value / 1000) if millions else abs(value)
    sign = '−' if value < -.05 else '+' if signed and value >= .05 else ''
    formatted = (f'{number:,.2f}' if millions else f'{number:,.1f}').replace(',', ' ').replace('.', ',')
    return f"{sign}{formatted} {'млн' if millions else 'тыс.'} ₽"


def article_text(article):
    return f'«{article["name"]}» ({money(article["delta"], signed=True)})'


def driver_text(leaders, delta):
    if not leaders:
        return ''
    clauses = []
    for sign in ((-1, 1) if delta < 0 else (1, -1)):
        names = [article_text(a) for a in leaders if a['delta'] * sign > 0]
        if names:
            if abs(delta) < .05:
                phrase = 'Результат поддержали изменения' if sign > 0 else 'Этот эффект компенсировали изменения'
            elif sign > 0:
                phrase = 'Часть отставания компенсировали изменения' if delta < 0 else 'Прирост во многом связан с изменениями'
            else:
                phrase = 'На отставание сильнее всего повлияли изменения' if delta < 0 else 'Прирост частично сдержали изменения'
            clauses.append(f'{phrase} по {"статье" if len(names) == 1 else "статьям"} {" и ".join(names)}.')
    return ' '.join(clauses)


def prepare(review, allocation):
    """Create a readable local version and a bounded set of facts for the editor."""
    cards, cases = [], {}
    for w, window in enumerate(review.get('windows', [])):
        actual = window['metrics'][-1]['values'][0]
        card = {'label': window['label'], 'title': window['title'], 'comparisons': [],
                'headline': ('Фактических данных за период пока нет.' if actual is None else
                             f'Чистая прибыль / кэш флоу составила {money(actual)}.')}
        cards.append(card)
        for i, comp in enumerate(window['comparisons']):
            key = ('month', 'ytd')[w] + ('_forecast', '_prior')[i]
            item = {'id': key, 'detail': ''}
            card['comparisons'].append(item)
            gap = comp['net_delta']
            if gap is None:
                item['finding'] = ('Для сравнения с прогнозом недостаточно данных.' if i == 0 else
                                   'Для сравнения с прошлым годом недостаточно данных.')
                continue
            delta = gap['value']
            if abs(delta) < .05:
                item['finding'] = f'Результат на уровне {BASES[i]}.'
            else:
                item['finding'] = f'Результат {"выше" if delta > 0 else "ниже"} {BASES[i]} на {money(abs(delta))}.'
            leaders = comp['drivers']['leaders']
            item['detail'] = driver_text(leaders, delta)
            if leaders:
                cases[key] = {'period': window['label'], 'comparison': comp['title'],
                              'finding': item['finding'], 'actual': money(actual),
                              'articles': {chr(65 + n): {'name': a['name'], 'delta': round(a['delta'], 4)}
                                           for n, a in enumerate(leaders)}}
    facts = {'partial': bool(review.get('partial')), 'allocation': allocation, 'cases': cases}
    digest = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return cards, facts, digest


PROMPT = """Ты редактор финансового отчёта для акционеров. Напиши на русском по одному короткому
абзацу для каждого переданного ключа cases. Это пояснения к готовым фразам о сумме и направлении
отклонения к прогнозу или прошлому году: не повторяй эти фразы. Расскажи обычными словами, за
счёт каких статей получился результат и что компенсировало снижение или ограничило рост.
delta — вклад статьи в отклонение кэш флоу в тысячах рублей. Плюс улучшает результат, минус ухудшает.
Для отрицательного общего отклонения положительные вклады его сократили, для положительного
отрицательные его сдержали. Инвестиции и погашение займов — денежные потоки.
Опирайся только на предоставленные факты. Никаких гипотез, управленческих советов или других периодов.
Вместо названия и суммы статьи обязательно ставь её маркер [A], [B], [C] или [D].
В готовом тексте он будет заменён на «Название статьи» (вклад в рублях с единицей измерения).
Не дублируй название рядом с маркером. Суммы, числа и проценты самостоятельно не пиши.
Упомяни главную статью [A] и хотя бы один вклад каждого имеющегося знака. Например:
Основную часть отставания объясняют расходы по статье [A]. Положительный вклад [B] частично сократил разрыв.
Выведи только JSON-объект с теми же ключами, что в cases, и строками без разметки в качестве значений."""


def generate(facts):
    from openai import OpenAI, NotFoundError, PermissionDeniedError
    messages = [{'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': json.dumps(facts, ensure_ascii=False)}]
    timeout = httpx.Timeout(195, connect=8, write=15, pool=5)
    with OpenAI(base_url=BASE_URL, api_key=Config.POLZA_AI_API_KEY, timeout=timeout, max_retries=0) as client:
        try:
            response = client.chat.completions.create(
                model=Config.POLZA_AI_REVIEW_MODEL, max_tokens=1800, messages=messages)
        except (NotFoundError, PermissionDeniedError):
            if Config.POLZA_AI_REVIEW_MODEL == Config.POLZA_AI_MODEL:
                raise
            response = client.chat.completions.create(
                model=Config.POLZA_AI_MODEL, max_tokens=2500, messages=messages)
    raw = (response.choices[0].message.content or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^\`\`\`(?:json)?\s*|\s*\`\`\`$', '', raw, flags=re.I)
    return render_copy(json.loads(raw), facts['cases'])


def render_copy(copy, cases):
    if not isinstance(copy, dict) or copy.keys() != cases.keys():
        raise ValueError('Unexpected commentary periods')
    result = {}
    for key, case in cases.items():
        phrase = copy[key]
        if not isinstance(phrase, str) or not 8 <= len(phrase) <= 800:
            raise ValueError('Invalid commentary length')
        articles = case['articles']
        markers = re.findall(r'\[([A-D])\]', phrase)
        plain = re.sub(r'\[[A-D]\]', '', phrase)
        if ('A' not in markers or set(markers) - articles.keys() or
                re.search(r'[\d<>\[\]{}#*]', plain)):
            raise ValueError('Unexpected article or unverified number')
        signs = {article['delta'] > 0 for article in articles.values()}
        if {articles[m]['delta'] > 0 for m in markers} != signs:
            raise ValueError('Missing offsetting contribution')
        result[key] = re.sub(r'\[([A-D])\]', lambda m: article_text(articles[m[1]]), phrase).strip()
    return result


def connection():
    db = sqlite3.connect(CACHE, timeout=4)
    db.execute('''CREATE TABLE IF NOT EXISTS commentary
                  (digest TEXT PRIMARY KEY, token TEXT, state TEXT, started REAL, body TEXT)''')
    return db


def snapshot(digest):
    if not CACHE.exists():
        return {'state': 'local', 'texts': {}}
    try:
        with closing(connection()) as db:
            row = db.execute('SELECT state, started, body FROM commentary WHERE digest=?', (digest,)).fetchone()
    except sqlite3.Error:
        log.warning('Cannot read shareholder commentary cache')
        row = None
    if not row:
        return {'state': 'local', 'texts': {}}
    state, started, body = row
    if state == 'pending' and time.time() - started >= LEASE:
        state = 'failed'
    return {'state': state, 'texts': json.loads(body) if body else {}}


def status_message(status):
    state = status['state']
    if state == 'pending':
        return 'Polza готовит пояснения по свежим данным…'
    if state == 'ready':
        return 'Пояснения подготовлены через Polza по данным этого отчёта.'
    errors = {
        'connect_timeout': 'Сервер отчёта не смог установить соединение с Polza за отведённое время.',
        'read_timeout': 'Сервер отчёта не дождался ответа Polza.',
        'failed': 'Polza не обновила пояснения.',
    }
    if state in errors:
        source = 'Показана предыдущая версия для тех же цифр.' if status['texts'] else 'Показаны выводы по расчёту.'
        return f'{errors[state]} {source} Можно повторить обновление.'
    return ''


def _worker(digest, token, facts):
    try:
        texts = json.dumps(generate(facts), ensure_ascii=False)
        state = 'ready'
    except Exception as exc:
        cause = exc.__cause__
        log.warning('Polza shareholder commentary failed (%s, cause=%s, status=%s)', type(exc).__name__,
                    type(cause).__name__, getattr(exc, 'status_code', None))
        state = {httpx.ConnectTimeout: 'connect_timeout', httpx.ReadTimeout: 'read_timeout'}.get(type(cause), 'failed')
        texts = None
    with closing(connection()) as db, db:
        db.execute('UPDATE commentary SET state=?, body=COALESCE(?,body) WHERE digest=? AND token=?',
                   (state, texts, digest, token))


def start(digest, facts):
    if not facts['cases']:
        return 'empty'
    if not Config.POLZA_AI_API_KEY:
        return 'unconfigured'
    token, now = uuid.uuid4().hex, time.time()
    try:
        with closing(connection()) as db, db:
            claimed = db.execute('''INSERT INTO commentary (digest,token,state,started) VALUES (?,?,'pending',?)
                       ON CONFLICT(digest) DO UPDATE SET token=excluded.token,state='pending',started=excluded.started
                       WHERE commentary.state!='pending' OR commentary.started<=?''', (digest, token, now, now - LEASE))
            launch = claimed.rowcount == 1
        if launch:
            threading.Thread(target=_worker, args=(digest, token, facts), daemon=True).start()
    except (sqlite3.Error, RuntimeError):
        log.exception('Cannot start shareholder commentary')
        return 'failed'
    return 'pending'
