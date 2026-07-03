"""Займы — портфель заёмного финансирования по кредиторам (аналог вкладки
«Займы» в Power BI: public.analiz_zaim).

"Тело займа" в analiz_zaim — это уже готовый остаток долга, проведённый в том
периоде, в котором он актуален (не поток), поэтому:
  Займ-на-конец-периода = SUM("Тело займа") за период
  Займ-на-начало-периода = тот же остаток за предыдущий период
Источник — reporting.loans_monthly (period, lender, line, pf, amount).
"""
import calendar
from datetime import date

from db import query

MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']


def get_available_periods():
    rows = query('SELECT DISTINCT period FROM reporting.loans_monthly ORDER BY 1')
    return [r['period'] for r in rows]


def _prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def loans(year, month, pf='факт', top_n=40):
    prev_year, prev_month = _prev_month(year, month)

    balance_rows = query(
        '''SELECT extract(year FROM period)::int AS y, extract(month FROM period)::int AS m,
                  lender, SUM(amount) AS val
           FROM reporting.loans_monthly
           WHERE line = 'Тело займа' AND pf = %s
             AND ((extract(year FROM period) = %s AND extract(month FROM period) = %s)
               OR (extract(year FROM period) = %s AND extract(month FROM period) = %s))
           GROUP BY 1, 2, 3''',
        (pf, year, month, prev_year, prev_month)
    )
    closing = {}
    opening = {}
    for r in balance_rows:
        val = float(r['val'] or 0)
        if r['y'] == year and r['m'] == month:
            closing[r['lender']] = val
        else:
            opening[r['lender']] = val

    flow_rows = query(
        '''SELECT lender, line, SUM(amount) AS val
           FROM reporting.loans_monthly
           WHERE pf = %s AND extract(year FROM period) = %s AND extract(month FROM period) = %s
             AND line IN ('Привлечение Займов', 'Возврат Займов', 'Проценты По Займам')
           GROUP BY 1, 2''',
        (pf, year, month)
    )
    draw = {}
    repay = {}
    interest = {}
    for r in flow_rows:
        val = float(r['val'] or 0)
        {'Привлечение Займов': draw, 'Возврат Займов': repay, 'Проценты По Займам': interest}[r['line']][r['lender']] = val

    lenders = set(closing) | set(opening) | set(draw) | set(repay) | set(interest)
    rows = []
    for lender in lenders:
        op = opening.get(lender, 0.0)
        cl = closing.get(lender, opening.get(lender, 0.0) + draw.get(lender, 0.0) + repay.get(lender, 0.0))
        dr = draw.get(lender, 0.0)
        rp = repay.get(lender, 0.0)
        ic = interest.get(lender, 0.0)
        rate = (-ic * 12 / op * 100) if op else None
        rows.append({
            'lender': lender, 'opening': op, 'draw': dr, 'repay': rp,
            'closing': cl, 'interest': ic, 'rate_pct': rate,
        })
    rows.sort(key=lambda r: -abs(r['closing']))
    rows = rows[:top_n]

    total = {
        'opening': sum(r['opening'] for r in rows),
        'draw': sum(r['draw'] for r in rows),
        'repay': sum(r['repay'] for r in rows),
        'closing': sum(r['closing'] for r in rows),
        'interest': sum(r['interest'] for r in rows),
    }
    return {'rows': rows, 'total': total, 'year': year, 'month': month, 'month_name': MONTHS_RU[month - 1]}


def loans_balance_series(pf='факт'):
    """Суммарный остаток долга по месяцам — для графика."""
    rows = query(
        '''SELECT period, SUM(amount) AS val FROM reporting.loans_monthly
           WHERE line = 'Тело займа' AND pf = %s GROUP BY 1 ORDER BY 1''',
        (pf,)
    )
    return {'periods': [r['period'].strftime('%Y-%m') for r in rows], 'vals': [float(r['val'] or 0) for r in rows]}
