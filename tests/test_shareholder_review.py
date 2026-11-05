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
