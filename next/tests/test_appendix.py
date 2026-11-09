"""The calculation appendix is the engine's, never the rapport agent's.

The driftsmedel review (2026-09-30) found reports whose hand-written appendix
did not reach the engine's numbers and explained the gap as rounding. The
engine now writes the appendix at the end of the kalkyl text, and /api/rapport
copies it into the report and cuts any appendix the model wrote itself.

Every expected number here is worked out by hand in the comment above it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from caia.appendix import (
    FALLBACK_NOTE,
    MISSING_NOTE,
    appendix_for_report,
    strip_handwritten_appendix,
)
from caia.calc import CalcModel, compute, render_appendix, render_markdown
from caia.calc.engine import APPENDIX_HEADING, APPENDIX_STAMP, _pct, _sig
from caia.pipeline import BRIDGE
from caia.web import app as A

FIXTURES = Path(__file__).parent / 'fixtures'


def _drv(**over) -> dict:
    d = {
        'name': 'Bilresor', 'baseline_year': 2023, 'a0': 1000.0, 'ef0': 2.0, 'a0_unit': 'km/år',
        'ramp': {'start_year': 2025, 'full_effect_year': 2027, 'profile': 'linjär'},
        'g_a': 0.0, 'g_ef': 0.0,
        'delta_a': {'min': -0.1, 'med': -0.2, 'max': -0.3}, 'delta_ef': 0.0,
        'terr': 1.0, 'cons': 0.5, 'overlap': 0.5,
    }
    d.update(over)
    return d


def _model(*drivers) -> CalcModel:
    return CalcModel.from_dict({'action_name': 'x', 'target_year': 2030,
                                'drivers': list(drivers) or [_drv()]})


# ---------- the engine writes the numbers it computed ----------

# One driver, as case A in test_calc_golden:
#   E_BAU = 1000 × 2 kg = 2,00 t every year. Adoption 2025 0, 2026 0,5, 2027 on 1.
#   Medel 2026: ΔA × adoption = −0,2 × 0,5 = −10 %; E_åtgärd = 1000 × 0,9 × 2 kg = 1,80 t;
#   ΔE = 0,20; territoriell 0,20, konsumtion 0,10, överlapp min(0,10; 0,20; 0,10) = 0,10;
#   netto 0,20 + 0,10 − 0,10 = 0,20.
#   Netto medel per år: 2025 0, 2026 0,2, 2027–2030 0,4.
#   Kumulativt 2025–2030: 1,8. Medel 2026–2030: (0,2 + 4 × 0,4) / 5 = 0,36.
#   Min: 0, 0,1, 4 × 0,2 → kumulativt 0,9, medel 0,18. Max: 0, 0,3, 4 × 0,6 → 2,7 och 0,54.

def test_appendix_shows_each_step_of_the_engine():
    m = _model()
    text = render_appendix(m, compute(m))
    assert text.startswith(APPENDIX_HEADING)
    assert APPENDIX_STAMP in text
    assert '| 2026 | 1 000 | 2 | 2,00 | 50 % | -10 % | 0 % | 1,80 | 0,20 | 0,20 | 0,10 | 0,10 | 0,20 |' in text
    assert '| 2030 | 1 000 | 2 | 2,00 | 100 % | -20 % | 0 % | 1,60 | 0,40 | 0,40 | 0,20 | 0,20 | 0,40 |' in text


def test_each_scenario_table_uses_its_own_delta():
    # 2030, full adoption. Min: ΔA −10 %, E_åtgärd 1,80, ΔE 0,20, terr 0,20, cons 0,10,
    # overlap 0,10, netto 0,20. Max: ΔA −30 %, E_åtgärd 1,40, ΔE 0,60, 0,60, 0,30, 0,30, 0,60.
    m = _model()
    text = render_appendix(m, compute(m))
    min_part = text[text.index('Scenario min:'):text.index('Scenario max:')]
    max_part = text[text.index('Scenario max:'):text.index('Summering')]
    assert '| 2030 | 1 000 | 2 | 2,00 | 100 % | -10 % | 0 % | 1,80 | 0,20 | 0,20 | 0,10 | 0,10 | 0,20 |' in min_part
    assert '| 2030 | 1 000 | 2 | 2,00 | 100 % | -30 % | 0 % | 1,40 | 0,60 | 0,60 | 0,30 | 0,30 | 0,60 |' in max_part


def test_appendix_sums_are_the_headline_numbers():
    m = _model()
    text = render_appendix(m, compute(m))
    assert ('- Scenario medel, kumulativt 2025–2030: 0,00 + 0,20 + 0,40 + 0,40 + 0,40 + 0,40 '
            '= 1,80 ton CO2e.') in text
    assert ('- Scenario medel, medel effekt/år 2026–2030: (0,20 + 0,40 + 0,40 + 0,40 + 0,40) / 5 '
            '= 0,36 ton CO2e/år.') in text
    assert '- Scenario min, kumulativt 2025–2030: 0,00 + 0,10 + 0,20 + 0,20 + 0,20 + 0,20 = 0,90 ton CO2e.' in text
    assert '- Scenario max, medel effekt/år 2026–2030: (0,30 + 0,60 + 0,60 + 0,60 + 0,60) / 5 = 0,54 ton CO2e/år.' in text
    # Medel 2026–2030 per perspective: terr = net = 0,36, cons = half of basis = 0,18.
    assert 'territoriell 0,36, konsumtion 0,18, netto 0,36 ton CO2e/år' in text


# Two drivers, the second ending early and on another ramp:
#   Driver 2: E_BAU = 500 × 1 kg = 0,5 t, delta_a −0,5 (all scenarios), full effect from 2025,
#   terr 1, cons 0, overlap 0, end_year medel 2027 → netto 0,25 in 2025–2027, then 0.
#   Medel netto per year, both drivers: 2025 0,25; 2026 0,45; 2027 0,65; 2028–2030 0,40.
#   Kumulativt 0,25 + 0,45 + 0,65 + 3 × 0,40 = 2,55. Medel 2026–2030: (0,45 + 0,65 + 1,2) / 5 = 0,46.

def test_appendix_adds_drivers_and_honours_the_end_year():
    second = _drv(name='Korta', a0=500.0, ef0=1.0, delta_a=-0.5, terr=1.0, cons=0.0, overlap=0.0,
                  ramp={'start_year': 2024, 'full_effect_year': 2025, 'profile': 'linjär',
                        'end_year': {'min': 2026, 'med': 2027, 'max': 2030}})
    m = _model(_drv(), second)
    r = compute(m)
    text = render_appendix(m, r)
    assert 'Drivare 2: Korta' in text
    assert 'sista år med effekt 2026 / 2027 / 2030 (min / medel / max)' in text
    assert ('- Scenario medel, kumulativt 2024–2030: 0,00 + 0,25 + 0,45 + 0,65 + 0,40 + 0,40 + 0,40 '
            '= 2,55 ton CO2e.') in text
    assert '(0,45 + 0,65 + 0,40 + 0,40 + 0,40) / 5 = 0,46 ton CO2e/år.' in text
    assert r['med']['total']['cumulative_net'] == pytest.approx(2.55)


def test_the_inputs_show_the_trend_the_engine_uses():
    """The BAU trend is the medel in all three scenarios. A band on it was
    printed whole, '-2 % (-1 till -3)/år', as if the outer values were used."""
    m = _model(_drv(g_a={'min': -0.01, 'med': -0.02, 'max': -0.03}, g_ef=-0.015))
    r = compute(m)
    for text in (render_appendix(m, r), render_markdown(m, r)):
        assert 'BAU-trend A -2 %/år, EF -1,5 %/år; ' in text
        assert '(-1 till -3)' not in text


def test_appendix_and_kalkyl_text_state_the_same_totals():
    """Two texts from one model: the appendix may not describe other numbers
    than the kalkyl text above it."""
    m = _model(_drv(a0=123456.0, ef0=0.17, g_a=-0.01, g_ef=-0.02,
                    ramp={'start_year': 2025, 'full_effect_year': 2029, 'profile': 'S-formad'}))
    r = compute(m)
    kalkyl, appendix = render_markdown(m, r), render_appendix(m, r)
    for sc in ('min', 'med', 'max'):
        cum = r[sc]['total']['cumulative_net']
        assert f"= {_ton(cum)} ton CO2e." in appendix
    assert f"Medel effekt/år (Netto/Total): {_fmt(r['med']['total']['avg_2026_2030_net'])}" in kalkyl
    assert f"= {_ton(r['med']['total']['avg_2026_2030_net'])} ton CO2e/år." in appendix


def _ton(x):
    from caia.calc.engine import _ton as t
    return t(x)


def _fmt(x):
    from caia.calc.engine import _fmt as f
    return f(x)


# ---------- the report gets the kalkyl step's appendix, verbatim ----------

def _history(kalkyl_text: str) -> list[dict]:
    return [
        {'role': 'user', 'content': 'Åtgärd'},
        {'role': 'assistant', 'content': 'antaganden'},
        {'role': 'user', 'content': BRIDGE['evidens']},
        {'role': 'assistant', 'content': kalkyl_text},
        {'role': 'user', 'content': BRIDGE['kalkyl']},
        {'role': 'assistant', 'content': 'QA ok'},
        {'role': 'user', 'content': BRIDGE['qa']},
    ]


def test_report_appendix_is_copied_from_the_kalkyl_step():
    m = _model()
    r = compute(m)
    appendix = render_appendix(m, r)
    kalkyl = render_markdown(m, r) + '\n\n' + appendix
    assert appendix_for_report(_history(kalkyl)) == appendix


def test_llm_fallback_kalkyl_is_carried_as_written_and_labelled():
    kalkyl = 'Kalkyl & tidsprofil\n\nBeräkningssteg (transparens)\n  ΔE = 3 000 × 0,1 = 300 kg'
    out = appendix_for_report(_history(kalkyl))
    assert out.startswith(APPENDIX_HEADING)
    assert FALLBACK_NOTE in out
    assert out.endswith(kalkyl)


def test_missing_kalkyl_says_so_instead_of_inventing_one():
    out = appendix_for_report([{'role': 'user', 'content': 'Åtgärd'}])
    assert out == f'{APPENDIX_HEADING}\n\n{MISSING_NOTE}'


def test_the_latest_kalkyl_wins_after_a_rerun():
    hist = _history('gammal kalkyl') + [{'role': 'assistant', 'content': 'x'}] + _history('ny kalkyl')[3:]
    assert appendix_for_report(hist).endswith('ny kalkyl')


# ---------- a hand-written appendix is cut, prose about it is not ----------

BODY = '## Åtgärd\n\n' + 'Rapportens text om åtgärden och dess klimatnytta. ' * 6


@pytest.mark.parametrize('heading', [
    '**Teknisk bilaga: Beräkningssteg**',
    '## Teknisk bilaga',
    '10) **Teknisk bilaga: Beräkningssteg**',
    '**10) Beräkningsbilaga**',
    'Teknisk bilaga: Beräkningssteg',
    '### Bilaga: Beräkningssteg',
    '- **Teknisk bilaga: Beräkningssteg**',
    '> **Teknisk bilaga**',
    '**Bilaga 1: Beräkningssteg**',
])
def test_a_handwritten_appendix_heading_cuts_the_rest(heading):
    report = f'{BODY}\n\n{heading}\n\nNedan följer...\n  ΔE = 17 ton (avrundat)\n'
    body, cut = strip_handwritten_appendix(report)
    assert cut is True
    assert body == BODY.rstrip()


@pytest.mark.parametrize('line', [
    'Se Teknisk bilaga för hur talen räknats fram.',
    'Teknisk bilaga läggs till av programmet och visar varje beräkningssteg per år och scenario.',
    '- Beräkningarna står i den tekniska bilagan.',
    '**Källor och underlag**',
    '**Teknisk bilaga:** se sist i rapporten.',
    'Teknisk bilaga finns sist',
    '**Teknisk bilaga:** se sist, **viktigt**',
])
def test_prose_mentioning_the_appendix_is_kept(line):
    report = f'{BODY}\n\n{line}\n\nMer text.'
    body, cut = strip_handwritten_appendix(report)
    assert cut is False
    assert body == report


def test_a_table_of_contents_line_does_not_cut_the_report():
    # "10. Teknisk bilaga" near the top is a contents entry; cutting there
    # would drop every real section while the report still looked complete.
    report = ('## Titel\n\nInnehåll\n1. Sammanfattning\n10. Teknisk bilaga\n\n'
              + BODY + '\n\n## Slutsats\n\n' + 'Mer rapporttext. ' * 10)
    body, cut = strip_handwritten_appendix(report)
    assert cut is False
    assert body == report.rstrip()


def test_contents_line_and_real_appendix_cut_at_the_real_one():
    report = ('## Titel\n\n10. Teknisk bilaga\n\n' + BODY
              + '\n\n**Teknisk bilaga: Beräkningssteg**\n\nΔE = 17 ton\n')
    body, cut = strip_handwritten_appendix(report)
    assert cut is True
    assert body == ('## Titel\n\n10. Teknisk bilaga\n\n' + BODY).rstrip()


@pytest.mark.parametrize('value, digits, text', [
    (10.0 * 100, 3, '1 000'),
    (-12.0 * 100, 3, '-1 200'),
    (0.0000452, 4, '0,0000452'),
    (2.346, 4, '2,346'),
    (999.96, 4, '1 000'),
    (-0.1, 3, '-0,1'),
    (12345.6, 4, '12 346'),
])
def test_appendix_numbers_never_use_exponent_form(value, digits, text):
    assert _sig(value, digits) == text


def test_a_tenfold_effect_is_written_as_a_percentage():
    assert _pct(10.0) == '1 000 %'
    assert _pct(-0.2) == '-20 %'


def test_a_real_report_is_cut_exactly_at_its_appendix():
    """The fixture is a real rapport-agent answer with a hand-written section 10."""
    real = (FIXTURES / 'rapport.md').read_text(encoding='utf-8')
    idx = real.index('**Teknisk bilaga: Beräkningssteg**')
    body, cut = strip_handwritten_appendix(real)
    assert cut is True
    assert body == real[:idx].rstrip()
    # And the same report without its appendix passes through untouched.
    again, cut_again = strip_handwritten_appendix(body)
    assert cut_again is False and again == body


# ---------- the route: what the user saves ----------

def test_rapport_route_ends_with_the_engines_appendix_only(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    real = (FIXTURES / 'rapport.md').read_text(encoding='utf-8')
    monkeypatch.setattr(A, 'run_rapport', lambda h, **_: real)
    m = _model()
    r = compute(m)
    appendix = render_appendix(m, r)
    hist = _history(render_markdown(m, r) + '\n\n' + appendix)
    out = A.app.test_client().post('/api/rapport', json={'history': hist}).get_json()['output']
    assert out.count(APPENDIX_HEADING) == 1
    assert out.rstrip().endswith(appendix)
    assert 'Beräkningsförutsättningar (gemensamma för alla scenarier)' not in out  # the model's own
    assert out.startswith(real[:real.index('**Teknisk bilaga')].rstrip())


def test_kalkyl_route_output_ends_with_the_appendix(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    monkeypatch.setattr(A, 'get_data_context', lambda: '')
    monkeypatch.setattr(A, 'run_kalkyl_extract',
                        lambda h, **_: {'action_name': 'x', 'target_year': 2030, 'drivers': [_drv()]})
    body = A.app.test_client().post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True
    m = _model()
    assert body['output'].endswith(render_appendix(m, compute(m)))


def test_an_appendix_stamped_before_the_rename_is_still_the_engines():
    """The tool was called Zaid until October 2026. A kalkyl step that ran
    before the rename ends with the engine's appendix under the old stamp; a
    report built from it afterwards must carry that appendix, not the note
    that the language model did the calculation."""
    from caia.appendix import FALLBACK_NOTE, appendix_for_report
    from caia.pipeline import BRIDGE
    old_stamp = APPENDIX_STAMP.replace('CAIA:s kalkylmotor', 'Zaids kalkylmotor')
    assert old_stamp != APPENDIX_STAMP and 'Zaids kalkylmotor ur exakt de tal' in old_stamp
    appendix = f'{APPENDIX_HEADING}\n\n{old_stamp} Talen är avrundade.\n\n| År | ton |\n|---|---|\n| 2026 | 12 |'
    history = [{'role': 'user', 'content': 'åtgärd'},
               {'role': 'assistant', 'content': f'Kalkyl i löptext.\n\n{appendix}'},
               {'role': 'user', 'content': BRIDGE['kalkyl']}]
    got = appendix_for_report(history)
    assert got == appendix
    assert FALLBACK_NOTE not in got
    # Control: without any stamp the same text is the model's own, and says so.
    history[1]['content'] = history[1]['content'].replace(old_stamp, 'Bilagan är skriven för hand.')
    assert FALLBACK_NOTE in appendix_for_report(history)
