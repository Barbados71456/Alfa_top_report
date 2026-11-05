from datetime import date
from unittest.mock import Mock

import pytest

import pl_report as pl
import shareholder_review as sr


def review(monkeypatch):
    rows = [dict(period=date(year, 1, 1), pf=pf, line=line, value=amount)
            for year, pf, sales, rent in [(2025, 'факт', 3000, -1500), (2025, 'прогноз', 1000, -1000),
                                           (2024, 'факт', 5000, -2000)]
            for line, amount in [(pl.REVENUE_LINES[0], sales), ('Аренда', rent)]]
    monkeypatch.setattr(pl, 'query', lambda *args: rows)
    return pl.svod1_month_review(2025, 1)


def test_two_windows_have_readable_counterfactuals_without_polza(monkeypatch):
    cards, facts, digest = sr.prepare(review(monkeypatch), 'all')
    assert len(cards) == 2 and len(facts['cases']) == 4
    assert cards[0]['headline'].endswith('1,50 млн ₽.')
    forecast, prior = cards[0]['comparisons']
    assert 'выше прогноза на 1,50 млн ₽' in forecast['finding']
    assert 'ниже прошлого года' in prior['finding']
    assert 'Аренда' in forecast['detail']
    assert sr.prepare(review(monkeypatch), 'no_alloc')[2] != digest


def test_generated_paragraphs_bind_signed_amounts_to_correct_case(monkeypatch):
    _, facts, _ = sr.prepare(review(monkeypatch), 'all')
    cases = facts['cases']
    result = sr.render_copy({k: 'На результат повлияли статьи [A] и [B].' for k in cases}, cases)
    assert '«Аренда» (−500,0 тыс. ₽)' in result['month_forecast']
    assert '«Аренда» (+500,0 тыс. ₽)' in result['month_prior']
    for invalid in ['Сумма 33 млн по [A] и [B].', 'Главный фактор [A].', 'Факторы [A], [B] и [D].']:
        with pytest.raises(ValueError):
            sr.render_copy({k: invalid for k in cases}, cases)


def test_claim_coalesces_clicks_and_cache_rejects_stale_jobs(monkeypatch, tmp_path):
    monkeypatch.setattr(sr, 'CACHE', tmp_path / 'review.sqlite')
    monkeypatch.setattr(sr.Config, 'POLZA_AI_API_KEY', 'test')
    thread = Mock()
    monkeypatch.setattr(sr.threading, 'Thread', thread)
    _, facts, digest = sr.prepare(review(monkeypatch), 'all')
    assert sr.start(digest, facts) == sr.start(digest, facts) == 'pending'
    thread.assert_called_once()
    worker = thread.call_args.kwargs
    monkeypatch.setattr(sr, 'generate', lambda payload: {'month_forecast': 'Проверено'})
    sr._worker(*worker['args'])
    assert sr.snapshot(digest) == {'state': 'ready', 'texts': {'month_forecast': 'Проверено'}}
    sr.start(digest, facts)
    sr._worker(*worker['args'])
    assert sr.snapshot(digest)['state'] == 'pending'
    monkeypatch.setattr(sr, 'generate', Mock(side_effect=ValueError('rejected')))
    sr._worker(*thread.call_args.kwargs['args'])
    assert sr.snapshot(digest) == {'state': 'failed', 'texts': {'month_forecast': 'Проверено'}}


def test_projects_cost_detail_and_ytd_are_compared_at_their_own_grain(monkeypatch):
    rows = []
    sales = pl.REVENUE_LINES[0]
    for m, pf, project, rev, cost in [
            (1, 'факт', '(DP) Tbank', 60, -45), (1, 'прогноз', '(DP) TB', 100, -40),
            (2, 'факт', '(DP) Tbank', 90, -20), (2, 'прогноз', '(DP) TB', 100, -30)]:
        for kind, line, name, value in [('project', sales, project, rev), ('subitem', sales, 'Поступления', rev),
                                        ('project', 'ФОТ постоянный', project, cost),
                                        ('dept', 'ФОТ постоянный', 'Департамент взыскания', cost)]:
            rows.append(dict(period=date(2025, m, 1), pf=pf, line=line, kind=kind, name=name, value=value))
    monkeypatch.setattr(pl, 'query', lambda *args: rows)
    review = pl.svod1_month_review(2025, 2)
    cards, facts, _ = sr.prepare(review, 'all')
    month, ytd = cards
    assert month['sections'][0]['intro'].startswith('Выручка составила 90,0 тыс.')
    assert 'на 10,0 тыс. ₽ меньше' in month['sections'][0]['paragraphs'][0]['text']
    assert 'на 50,0 тыс. ₽ меньше' in ytd['sections'][0]['paragraphs'][0]['text']
    assert '«Департамент взыскания» — на 10,0 тыс. ₽ меньше' in month['sections'][1]['paragraphs'][0]['text']
    assert 'недостаточно данных' in month['sections'][0]['paragraphs'][1]['text']
    assert '(DP) TB' not in str(facts) and 'Департамент взыскания' not in str(facts)


def test_tax_classification_note_only_when_subitems_tie_to_their_lines():
    tax, duty = 'Налоги Зп', 'Гос. пошлина (ВПК)'
    a = {('project', tax, 'A'): -24, ('subitem', tax, tax): -24}
    b = {('project', tax, 'A'): -6, ('subitem', tax, tax): -6,
         ('project', duty, 'A'): -15, ('subitem', duty, tax): -15}
    assert '24,0 тыс. ₽ против 21,0 тыс. ₽' in sr.payroll_tax_comparison(a, b, 0)
    b['project', duty, 'A'] = -10
    assert sr.payroll_tax_comparison(a, b, 0) == ''
