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
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import httpx

from chat_assistant import BASE_URL
from config import Config
from pl_report import REVENUE_LINES, VARIABLE_LINES, COMPARISON_FIXED_LINES, INVESTMENT_LINE

log = logging.getLogger(__name__)
CACHE = (Path('/data') if Path('/data').is_dir() else Path(tempfile.gettempdir())) / 'svod1-commentary.sqlite3'
LEASE = 270
BASES = ('прогноза', 'прошлого года')
SALARY_LINES = ('ФОТ постоянный', 'ФОТ переменный')


def money(value, signed=False):
    if abs(value) < .05:
        return '0 ₽'
    millions = abs(value) >= 1000
    number = abs(value / 1000) if millions else abs(value)
    sign = '−' if value < -.05 else '+' if signed and value >= .05 else ''
    formatted = (f'{number:,.2f}' if millions else f'{number:,.1f}').replace(',', ' ').replace('.', ',')
    return f"{sign}{formatted} {'млн' if millions else 'тыс.'} ₽"


def article_text(article):
    return f'«{article["name"]}» ({money(article["delta"], signed=True)})'


def grouped(detail, lines, kind='project', by_line=False, sign=1):
    totals = defaultdict(float)
    for (dimension, line, name), value in detail.items():
        if dimension == kind and line in lines:
            # The ETL classifies (DP) TB as (DP) Tbank. Forecast history still uses both names.
            name = '(DP) Tbank' if dimension == 'project' and name == '(DP) TB' else name
            totals[line if by_line else name] += sign * value
    return dict(totals)


def movements(actual, baseline, limit=3):
    """Keep the largest changes, including the strongest offset when one exists."""
    changes = [(name, actual.get(name, 0) - baseline.get(name, 0)) for name in actual.keys() | baseline.keys()]
    ranked = sorted((item for item in changes if abs(item[1]) >= .05), key=lambda item: (-abs(item[1]), item[0]))
    picked = ranked[:limit]
    if limit > 1 and picked and all(v * picked[0][1] > 0 for _, v in picked):
        offset = next((item for item in ranked[limit:] if item[1] * picked[0][1] < 0), None)
        if offset:
            picked[-1] = offset
    return picked


def metric_sentence(metric, index):
    change = metric['deltas'][index]
    if change is None:
        return 'Для сравнения недостаточно данных.'
    base = metric['values'][index + 1]
    delta = change['value']
    if abs(delta) < .05:
        return f'На уровне {BASES[index]} ({money(base)}).'
    return f'{"Выше" if delta > 0 else "Ниже"} {BASES[index]} на {money(abs(delta))} ({"прогноз" if index == 0 else "годом ранее"} — {money(base)}).'


def operating_bridge(net_change, operating_change):
    if operating_change is None:
        return ''
    operating = operating_change['value']
    if abs(operating) < .05:
        return 'Операционная прибыль почти не изменилась.'
    text = f'Операционная прибыль {"выше" if operating > 0 else "ниже"} на {money(abs(operating))}.'
    if net_change * operating < 0:
        after = net_change - operating
        text += (f' С учётом бонусов, инвестиций, финансирования и входящего остатка отклонение изменилось '
                 f'ещё на {money(after, True)}, поэтому итог оказался {"выше" if net_change > 0 else "ниже"}.')
    return text


def payroll_tax_comparison(actual, baseline, index):
    """A payroll-tax forecast can be booked under state duties. Compare like payments."""
    item = 'Налоги Зп'
    def split(details):
        return {line: -value for (kind, line, name), value in details.items()
                if kind == 'subitem' and name == item and line in VARIABLE_LINES + COMPARISON_FIXED_LINES}
    a, b = split(actual), split(baseline)
    duty = 'Гос. пошлина (ВПК)'
    if not (a and b and max(abs(a.get(duty, 0)), abs(b.get(duty, 0))) >= .05):
        return ''
    if (a.get(duty, 0) - b.get(duty, 0)) * (a.get(item, 0) - b.get(item, 0)) >= 0:
        return ''
    for line in a.keys() | b.keys():
        for detail in (actual, baseline):
            if abs(sum(grouped(detail, [line], 'subitem').values()) - sum(grouped(detail, [line]).values())) >= .05:
                return ''
    base_label = 'В прогнозе' if index == 0 else 'Годом ранее'
    return (f'{base_label} в строке госпошлины учтено {money(b.get(duty, 0))} налогов на зарплату, '
            f'в факте — {money(a.get(duty, 0))}. Если собрать подстатью «{item}» по всем операционным расходам, '
            f'получается {money(sum(a.values()))} против {money(sum(b.values()))}.')


def cost_driver(line, delta, actual, baseline):
    text = f'По статье «{line}» затраты {"выше" if delta > 0 else "ниже"} на {money(abs(delta))}'
    for kind in (('dept', 'subitem') if line in SALARY_LINES else ('subitem', 'project')):
        a, b = [grouped(source, [line], kind, sign=-1) for source in (actual, baseline)]
        # Independent materialized views may briefly be on different refreshes.
        if any(abs(sum(part.values()) - sum(grouped(src, [line], sign=-1).values())) >= .05
               for part, src in ((a, actual), (b, baseline))):
            continue
        leader = next(((n, v) for n, v in movements(a, b) if v * delta > 0), None)
        if not leader:
            continue
        name, amount = leader
        if (name.casefold() in {line.casefold(), 'налоги', 'общее', 'прочие', 'общие', 'прогноз', 'факт'}
                or name.startswith('(без ') or abs(amount) < .05):
            continue
        if kind == 'project':
            text += f'. На проект «{name}» в отчёте отнесено на {money(abs(amount))} {"больше" if amount > 0 else "меньше"}'
            break
        prefix = {'dept': 'в подразделении', 'subitem': 'по подстатье'}[kind]
        text += f', в том числе {prefix} «{name}» — на {money(abs(amount))} {"больше" if amount > 0 else "меньше"}'
        break
    return text + '.'


def department_section(window):
    departments = []
    for source in window['details']:
        payroll = grouped(source, SALARY_LINES, sign=-1)
        depts = grouped(source, SALARY_LINES, 'dept', sign=-1)
        departments.append(depts if depts and abs(sum(depts.values()) - sum(payroll.values())) < .05 else None)
    actual = departments[0]
    if actual is None:
        return None
    title = 'ФОТ по подразделениям'
    intro = f'Постоянная и переменная части ФОТ вместе составили {money(sum(actual.values()))}.'
    paragraphs = []
    for i, baseline in enumerate(departments[1:]):
        if baseline is None or window['metrics'][1]['deltas'][i] is None:
            paragraphs.append({'label': window['comparisons'][i]['title'], 'text': 'Для сравнения по подразделениям недостаточно данных.'})
            continue
        delta = sum(actual.values()) - sum(baseline.values())
        net = (f'Общий ФОТ {"выше" if delta > 0 else "ниже"} на {money(abs(delta))}.' if abs(delta) >= .05
               else 'Общий ФОТ почти не изменился.')
        changes = []
        for name, amount in movements(actual, baseline, limit=2):
            changes.append(f'По подразделению «{name}» учтено {money(actual.get(name, 0))} против '
                           f'{money(baseline.get(name, 0))}, на {money(abs(amount))} {"больше" if amount > 0 else "меньше"}.')
        text = ' '.join([net, *changes])
        paragraphs.append({'label': window['comparisons'][i]['title'], 'text': text})
    return {'title': title, 'intro': intro, 'paragraphs': paragraphs}


def business_sections(window):
    if not window['has_actual'] or 'details' not in window:
        return []
    actual, *baselines = window['details']
    revenue, costs = window['metrics'][:2]
    sections = []
    for metric, title, lines in [(revenue, 'Выручка по проектам', REVENUE_LINES),
                                 (costs, 'Операционные затраты по статьям', VARIABLE_LINES + COMPARISON_FIXED_LINES)]:
        if metric['values'][0] is None:
            continue
        is_revenue = metric is revenue
        intro = f'{"Выручка составила" if is_revenue else "Операционные затраты составили"} {money(metric["values"][0])}.'
        if is_revenue:
            channels = grouped(actual, lines, by_line=True)
            channel_names = {'Выручка DCA (агентская)': 'агентское вознаграждение', 'Выручка DP (цессия)': 'поступления по купленным портфелям'}
            parts = [f'{money(v)} — {channel_names.get(name, name.lower())}' for name, v in
                     sorted(channels.items(), key=lambda pair: -abs(pair[1])) if abs(v) >= .05]
            if parts:
                intro += ' Из них ' + ', '.join(parts) + '.'
        section = {'title': title, 'intro': intro, 'paragraphs': []}
        for i, base in enumerate(baselines):
            sentences = [metric_sentence(metric, i)]
            if metric['deltas'][i] is not None:
                if is_revenue:
                    a, b = [grouped(s, lines) for s in (actual, base)]
                    for name, delta in movements(a, b):
                        comparison_period = 'в прогнозе' if i == 0 else 'годом ранее'
                        project = f'По проекту «{name}»' if name != '(без проекта)' else 'Без привязки к проекту'
                        if abs(b.get(name, 0)) < .05:
                            sentences.append(f'{project} отражено {money(a[name])}, {comparison_period} выручка по нему не учтена.')
                        elif abs(a.get(name, 0)) < .05:
                            sentences.append(f'{project} выручка в факте нулевая против {money(b[name])} {comparison_period}.')
                        else:
                            sentences.append(f'{project} получено {money(a[name])} против {money(b[name])}, '
                                             f'на {money(abs(delta))} {"больше" if delta > 0 else "меньше"}.')
                else:
                    a, b = [grouped(s, lines, by_line=True, sign=-1) for s in (actual, base)]
                    sentences.extend(cost_driver(n, v, actual, base) for n, v in movements(a, b))
                    tax_note = payroll_tax_comparison(actual, base, i)
                    if tax_note:
                        sentences.append(tax_note)
            section['paragraphs'].append({'label': window['comparisons'][i]['title'], 'text': ' '.join(sentences)})
        sections.append(section)
    dept = department_section(window)
    if dept:
        sections.append(dept)
    return sections


def driver_text(leaders, delta):
    sentences = []
    for item in sorted(leaders, key=lambda a: a['delta'] * delta < 0):
        name, change = item['name'], item['delta']
        amount = money(abs(change))
        if name == INVESTMENT_LINE:
            phrase = f'На покупку портфелей направили на {amount} {"меньше" if change > 0 else "больше"}'
        elif name in REVENUE_LINES:
            label = {'Выручка DCA (агентская)': 'Агентское вознаграждение', 'Выручка DP (цессия)': 'Выручка по купленным портфелям'}.get(name, name)
            phrase = f'{label} — на {amount} {"выше" if change > 0 else "ниже"}'
        elif name in VARIABLE_LINES + COMPARISON_FIXED_LINES and name != 'Прочие Доходы':
            phrase = f'По статье «{name}» расходы оказались на {amount} {"ниже" if change > 0 else "выше"}'
        else:
            phrase = f'По строке «{name}» вклад в отклонение составил {money(change, True)}'
        sentences.append(phrase + '.')
    return ' '.join(sentences)


def prepare(review, allocation):
    """Create a readable local version and a bounded set of facts for the editor."""
    cards, cases = [], {}
    for w, window in enumerate(review.get('windows', [])):
        actual = window['metrics'][-1]['values'][0]
        card = {'label': window['label'], 'title': window['title'], 'comparisons': [],
                'sections': business_sections(window),
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
            item['bridge'] = operating_bridge(delta, comp['profit_delta'])
            if 'details' in window and any(a['name'] == INVESTMENT_LINE for a in leaders):
                sources = (window['details'][0], window['details'][i + 1])
                purchases = [grouped(source, [INVESTMENT_LINE], sign=-1) for source in sources]
                movers = movements(*purchases, limit=1)
                if movers and movers[0][0] not in ('(без проекта)', 'Общее'):
                    portfolio, amount = movers[0]
                    item['investment'] = (f'Крупнейшее изменение в покупке портфелей приходится на «{portfolio}». '
                                          f'На покупку направлено на {money(abs(amount))} {"больше" if amount > 0 else "меньше"}.')
            if leaders:
                cases[key] = {'period': window['label'], 'comparison': comp['title'],
                              'finding': item['finding'], 'actual': money(actual),
                              'articles': {chr(65 + n): {'name': a['name'], 'delta': round(a['delta'], 4)}
                                           for n, a in enumerate(leaders)}}
    facts = {'edition': 2, 'partial': bool(review.get('partial')), 'allocation': allocation, 'cases': cases}
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
