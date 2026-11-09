"""Kommunprofil (caia.kommun): a new municipality switches profile, not code.

The claim these guard is the one another kommun will rely on: run CAIA with another
profile and nothing about Karlstad reaches a model or the page. It is tested
where it matters, on what actually goes over the wire. Every model call is
stubbed and recorded, the whole pipeline is driven through the web endpoints,
and the recorded system prompts are searched for Karlstad.

A search that finds nothing proves nothing on its own (the capture could be
looking at unrendered templates, or at nothing). So every leak test has a
control that runs the same capture on the Karlstad profile and requires the
name to be there.

Run:  cd next && . .venv/bin/activate && python -m pytest tests/test_kommunprofil.py -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from test_evidens_split import HISTORY, merge_text, part_text  # noqa: E402
from caia import api_client, kommun  # noqa: E402
from caia.agents import (  # noqa: E402
    baslinje_bau,
    cove_qa,
    emap,
    evidens,
    evidens_split,
    intake,
    kalkyl,
    kalkyl_extract,
    rapport,
)
from caia.data import parameters as P  # noqa: E402
from caia.web import app as A  # noqa: E402

LEAK = re.compile(r'karlstad|värmland', re.IGNORECASE)
AGENT_MODULES = (intake, emap, baslinje_bau, evidens, evidens_split, kalkyl,
                 kalkyl_extract, cove_qa, rapport)
REPLACEMENT = '\ufffd'

# A calc model the stubbed extraction returns, so /api/kalkyl takes the
# deterministic path the way it does in production.
CALC_JSON = json.dumps({
    'action_name': 'Lövblåsare',
    'target_year': 2030,
    'drivers': [{
        'name': 'Bensin i lövblåsare', 'baseline_year': 2025,
        'a0': 1275, 'a0_unit': 'l/år', 'ef0': 2.3, 'ef0_unit': 'kg CO2e/l',
        'delta_a': {'min': -0.5, 'med': -0.8, 'max': -1.0},
        'terr': 1.0, 'cons': 1.0, 'overlap': 1.0,
        'ramp': {'start_year': 2025, 'full_effect_year': 2026},
    }],
})


@pytest.fixture
def use_kommun():
    """Switch the active profile for one test and put the old one back."""
    before = kommun._active

    def use(profile):
        kommun.set_active(kommun.bundled(profile) if isinstance(profile, str) else profile)
        return kommun.active()

    yield use
    kommun.set_active(before)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    return A.app.test_client()


def _stub_models(monkeypatch) -> list[dict]:
    """Replace complete() in every agent module; record what would be sent."""
    calls: list[dict] = []

    def fake(step, system, messages, max_output, mode=None, timeout_s=None):
        # The real complete() refuses an unrendered prompt. The stub must too:
        # a template full of @@ORT@@ contains no "Karlstad" either, and would
        # pass the leak test for the wrong reason.
        assert not kommun.UNRENDERED.search(system), (step, 'unrendered prompt')
        calls.append({'step': step, 'system': system, 'messages': messages})
        if step == 'evidens_part':
            m = re.search(r'ansvarar ENBART för:\s*\n\s*Drivare (\d+): (.+)', system)
            return part_text(int(m.group(1)), m.group(2).strip())
        if step == 'evidens_merge':
            return merge_text()
        if step == 'kalkyl_extract':
            # First extraction parses; the second does not, so the LLM-math
            # fallback (step 'kalkyl') runs too and its prompt is checked.
            first = sum(c['step'] == 'kalkyl_extract' for c in calls) == 1
            return CALC_JSON if first else 'ingen modell här'
        if step == 'intake':
            return 'ÅTGÄRDSPROFIL\n*Namn:* Lövblåsare\n*Sektor:* transport\nSTATUS: KLAR'
        return f'Svar från {step}.'

    for mod in AGENT_MODULES:
        monkeypatch.setattr(mod, 'complete', fake)
    return calls


def _run_pipeline(client, mode: str | None = None) -> None:
    """Every model-calling endpoint, in pipeline order, as the web client runs it.
    mode None sends no mode at all, as clients from before the follow-up mode did."""
    extra = {} if mode is None else {'mode': mode}
    first = [HISTORY[0]]
    for path, history in (('/api/intake', first), ('/api/emap', first),
                          ('/api/baslinje', HISTORY[:3]), ('/api/evidens', HISTORY)):
        assert client.post(path, json={'history': history, **extra}).status_code == 200, path

    drivers = client.post('/api/evidens/plan', json={'history': HISTORY, **extra}).get_json()['drivers']
    assert drivers
    parts = []
    for d in drivers:
        r = client.post('/api/evidens/part', json={'history': HISTORY, 'driver': d['number'], **extra})
        assert r.status_code == 200, r.get_json()
        parts.append({'number': d['number'], 'text': r.get_json()['text']})
    r = client.post('/api/evidens/merge', json={'history': HISTORY, 'parts': parts, **extra})
    assert r.status_code == 200, r.get_json()

    later = HISTORY + [{'role': 'assistant', 'content': r.get_json()['output']},
                       {'role': 'user', 'content': 'Fortsätt med kalkyl och tidsprofil.'}]
    r = client.post('/api/kalkyl', json={'history': later, **extra})
    assert r.get_json()['deterministic'] is True, r.get_json()
    r = client.post('/api/kalkyl', json={'history': later, **extra})
    assert r.get_json()['deterministic'] is False, r.get_json()
    for path in ('/api/qa', '/api/rapport'):
        assert client.post(path, json={'history': later, **extra}).status_code == 200, path


def _sent(calls: list[dict]) -> dict[str, str]:
    """step -> everything that step sent: system prompt and message texts."""
    out: dict[str, str] = {}
    for c in calls:
        text = c['system'] + '\n' + '\n'.join(str(m.get('content', '')) for m in c['messages'])
        out[c['step']] = out.get(c['step'], '') + text
    return out


# ---------- what reaches a model ----------

def test_exempel_pipeline_never_sends_karlstad_to_a_model(client, monkeypatch, use_kommun):
    use_kommun('exempel')
    calls = _stub_models(monkeypatch)
    _run_pipeline(client)
    sent = _sent(calls)
    # Every configured model step was exercised, so a step added later cannot
    # sit outside this test by accident.
    assert set(sent) == set(api_client.AGENT_MODELS), set(api_client.AGENT_MODELS) ^ set(sent)
    for step, text in sent.items():
        hit = LEAK.search(text)
        assert hit is None, (step, text[max(0, hit.start() - 80):hit.end() + 80])
    assert 'Exempelkommun' in sent['intake']
    assert 'Exempelkommunens klimatplan' in sent['evidens_part']


@pytest.mark.karlstad
def test_control_the_same_capture_finds_karlstad_on_the_karlstad_profile(
        client, monkeypatch, use_kommun):
    use_kommun('karlstad')
    calls = _stub_models(monkeypatch)
    _run_pipeline(client)
    sent = _sent(calls)
    rendered = {s for s, text in sent.items() if 'Karlstads kommun' in text or
                'Karlstads energi- och klimatplan' in text}
    # Every step whose prompt names the municipality renders it. emap and the
    # extraction never did.
    assert rendered == set(api_client.AGENT_MODELS) - {'emap', 'kalkyl_extract'}, rendered
    assert '## Territoriella växthusgasutsläpp Karlstad' in sent['baslinje']


@pytest.mark.karlstad
def test_no_placeholder_survives_rendering_on_either_profile(use_kommun):
    for slug in ('karlstad', 'exempel'):
        k = use_kommun(slug)
        for mod in (intake, emap, baslinje_bau, evidens, kalkyl, kalkyl_extract, cove_qa, rapport):
            out = k.render(mod.SYSTEM_PROMPT)
            assert not kommun.UNRENDERED.search(out), (slug, mod.__name__)
            assert '@@' not in out, (slug, mod.__name__)


def test_complete_refuses_an_unrendered_prompt(monkeypatch):
    def no_network():
        raise AssertionError('the guard must fire before any client is built')
    monkeypatch.setattr(api_client, 'get_client', no_network)
    with pytest.raises(RuntimeError, match='@@ORT@@'):
        api_client.complete('evidens', 'Värden för @@ORT@@.', [{'role': 'user', 'content': 'x'}], 10)


def test_a_user_typing_a_placeholder_is_not_refused(monkeypatch):
    """The guard reads the system prompt only. Chat text is the user's."""
    class Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                class Block:
                    type = 'text'
                    text = 'ok'

                class Resp:
                    stop_reason = 'end_turn'
                    content = [Block()]
                return Resp()
    monkeypatch.setattr(api_client, 'get_client', lambda: Client())
    assert api_client.complete('emap', 'system', [{'role': 'user', 'content': '@@ORT@@'}], 10) == 'ok'


# ---------- what reaches the page ----------

def _page(has_supabase: bool) -> str:
    from flask import render_template_string
    with A.app.test_request_context('/'):
        return render_template_string(
            A.HTML_TEMPLATE, has_supabase=has_supabase, supabase_url='https://x.supabase.co',
            supabase_anon_key='anon', **A._page_context())


def _without_origin(html: str) -> str:
    """Remove the one line that is allowed to name Karlstad, in every form the
    template writes it (HTML text and the JSON string in the script)."""
    with A.app.test_request_context('/'):
        as_json = A.app.jinja_env.from_string('{{ o|tojson }}').render(o=A.ORIGIN)
    return html.replace(as_json, '').replace(A.ORIGIN, '')


@pytest.mark.parametrize('has_supabase', [True, False])
def test_exempel_page_names_no_karlstad_outside_the_origin_line(use_kommun, has_supabase):
    use_kommun('exempel')
    html = _without_origin(_page(has_supabase))
    hit = LEAK.search(html)
    assert hit is None, html[max(0, hit.start() - 120):hit.end() + 80]
    assert 'Exempelkommunens klimatplan' in html
    assert 'Exempelstad-parametrar' in html


@pytest.mark.karlstad
def test_control_karlstad_page_still_names_karlstad_after_the_origin_is_removed(use_kommun):
    use_kommun('karlstad')
    html = _without_origin(_page(True))
    assert 'klimatnytta av &#xE5;tg&#xE4;rder i Karlstads energi- och klimatplan' in html
    assert 'Karlstad-parametrar' in html


def test_exempel_login_page_names_no_karlstad(use_kommun):
    from flask import render_template_string
    use_kommun('exempel')
    with A.app.test_request_context('/login'):
        html = render_template_string(A.LOGIN_TEMPLATE, error=None, **A._page_context())
    assert not LEAK.search(html)


@pytest.mark.karlstad
@pytest.mark.parametrize('has_supabase', [True, False])
def test_the_login_box_carries_the_name_and_no_plan_line(use_kommun, has_supabase):
    """2026-10-13: the box says CAIA and what the letters stand for. The
    line naming the municipality's plan is gone from both login boxes."""
    from flask import render_template_string
    use_kommun('karlstad')
    with A.app.test_request_context('/login'):
        login = render_template_string(A.LOGIN_TEMPLATE, error=None, **A._page_context())
    for html in (login, _page(has_supabase)):
        assert 'Klimatanalys av' not in html
    assert '<p>Climate Action Impact Analysis</p>' in login
    assert ('<p>Climate Action Impact Analysis</p>' in _page(has_supabase)) is has_supabase


def test_exempel_parameter_view_names_no_karlstad(client, use_kommun):
    use_kommun('exempel')
    r = client.get('/api/parameters')
    assert r.status_code == 200
    assert not LEAK.search(r.get_data(as_text=True))
    body = r.get_json()
    # The template is all national defaults until a municipality fills it in.
    assert body['counts'] == {'lokal': 0, 'datafil': 0, 'schablon': body['total']}
    assert body['total'] > 50


# ---------- the data layer follows the profile ----------

def test_exempel_has_no_local_data_and_says_nothing_about_it(use_kommun):
    use_kommun('exempel')
    assert P.get_data_context() == ''
    # An empty heading would tell the agents there is consumption data.
    assert P.load_consumption_data() == ''


def test_data_files_are_found_through_the_register(tmp_path, use_kommun):
    """A new municipality names its files in section 12, and its own column in
    the consumption export is the one named like its `ort`."""
    root = tmp_path / 'goteborg'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    toml = (root / 'kommun.toml').read_text(encoding='utf-8')
    toml = toml.replace('ort = "Exempelstad"', 'ort = "Göteborg"')
    (root / 'kommun.toml').write_text(toml, encoding='utf-8')
    (root / 'data' / 'fotavtryck-per-konsumtionskategori.json').write_text(json.dumps([
        {'coicop': '07.D', 'label': 'fordon', 'per100sek': 9.2, 'Göteborg': 512.5,
         'Sverige': 658.6}]), encoding='utf-8')
    (root / 'data' / 'energianvandning_bostader.csv').write_text(
        'Kategori,MWh\nSmåhus,1000\n', encoding='utf-8')
    (root / 'data' / 'kommunrapport_vaxthusgaser_totalt.csv').write_text(
        'Rapportnamn:;x\nEmissioner;\nEnhet: ton/år;\nCO2-ekv;\n;\n'
        ';;;;2022;2023\n'
        'Huvudsektor;Undersektor;Län;Kommun;CO2;CO2\n'
        'Alla;Alla;Västra Götalands län;Göteborg;1000,5;900,25\n', encoding='utf-8')
    (root / 'data' / 'medborgarundersokning_2024.csv').write_text(
        'Question,Response_Option,Percentage\nMeat_Frequency,Varje dag,12.0\n', encoding='utf-8')
    use_kommun(kommun.load(root))
    ctx = P.get_data_context()
    # All four loaders ran, each on a file found through the register.
    assert '- fordon: 512.5 kg CO2e/pers/ar' in ctx
    assert '## Energianvandning bostader Göteborg (MWh)' in ctx
    assert '## Konsumtionsbaserade utslapp Göteborg' in ctx
    assert '## Territoriella växthusgasutsläpp Göteborg (ton/år)' in ctx
    assert '- Alla sektorer (totalt): 2022: 1 000, 2023: 900' in ctx
    assert '## Medborgarundersokning Göteborg 2024' in ctx
    assert not LEAK.search(ctx)


def test_a_register_entry_cannot_read_outside_the_data_folder(tmp_path, use_kommun):
    root = tmp_path / 'k'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    lib = root / 'parameters_library.md'
    text = lib.read_text(encoding='utf-8').replace(
        '`energianvandning_bostader.csv`', '`../kommun.toml`')
    lib.write_text(text, encoding='utf-8')
    use_kommun(kommun.load(root))
    reg = P.parse_file_register()
    assert reg['DATA_ENERGY_RESIDENTIAL']['filename'] == '../kommun.toml'
    assert (root / 'data' / '../kommun.toml').exists()  # the file is really there
    assert reg['DATA_ENERGY_RESIDENTIAL']['exists'] is False
    assert P.load_energy_data() == ''


@pytest.mark.karlstad
def test_county_label_is_repaired_from_the_profile(tmp_path, use_kommun):
    use_kommun('karlstad')
    assert P.repair_label('V' + REPLACEMENT + 'rmlands l' + REPLACEMENT + 'n') == 'Värmlands län'
    root = tmp_path / 'g'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    toml = (root / 'kommun.toml').read_text(encoding='utf-8')
    (root / 'kommun.toml').write_text(
        toml.replace('lan = "Exempels län"', 'lan = "Västra Götalands län"'), encoding='utf-8')
    use_kommun(kommun.load(root))
    assert P.repair_label('V' + REPLACEMENT + 'stra G' + REPLACEMENT + 'talands l'
                          + REPLACEMENT + 'n') == 'Västra Götalands län'
    # Karlstad's county is not a label another profile repairs into.
    mangled = 'V' + REPLACEMENT + 'rmlands l' + REPLACEMENT + 'n'
    assert P.repair_label(mangled) == mangled


# ---------- selecting and validating a profile ----------

@pytest.mark.karlstad
def test_no_profile_chosen_is_an_error_that_says_what_to_set(monkeypatch):
    # F17: this used to fall back to Karlstad, so an install that forgot the
    # variable answered with Karlstad's data and plan and never said so.
    monkeypatch.delenv('CAIA_KOMMUN', raising=False)
    monkeypatch.delenv('CAIA_KOMMUN_DIR', raising=False)
    with pytest.raises(kommun.KommunProfilError, match=r'CAIA_KOMMUN.*exempel, karlstad.*CAIA_KOMMUN_DIR'):
        kommun.from_env()
    monkeypatch.setenv('CAIA_KOMMUN', '  ')
    with pytest.raises(kommun.KommunProfilError):
        kommun.from_env()


@pytest.mark.karlstad
def test_env_selects_the_profile(monkeypatch):
    monkeypatch.delenv('CAIA_KOMMUN_DIR', raising=False)
    monkeypatch.setenv('CAIA_KOMMUN', 'exempel')
    assert kommun.from_env().namn == 'Exempelkommun'
    monkeypatch.setenv('CAIA_KOMMUN', 'karlstad')
    assert kommun.from_env().slug == 'karlstad'


def test_profile_dir_outside_the_repo_wins(tmp_path, monkeypatch):
    root = tmp_path / 'var' / 'caia-profil'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    monkeypatch.setenv('CAIA_KOMMUN', 'karlstad')
    monkeypatch.setenv('CAIA_KOMMUN_DIR', str(root))
    k = kommun.from_env()
    assert k.root == root and k.namn == 'Exempelkommun'


@pytest.mark.parametrize('slug', ['../karlstad', 'Karlstad', 'a/b', ''])
def test_bad_slug_is_refused(slug):
    with pytest.raises(kommun.KommunProfilError):
        kommun.bundled(slug)


@pytest.mark.karlstad
def test_missing_profile_names_the_ones_that_exist():
    with pytest.raises(kommun.KommunProfilError, match='exempel, karlstad'):
        kommun.bundled('goteborg')


def test_missing_field_is_named(tmp_path):
    root = tmp_path / 'k'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    toml = (root / 'kommun.toml').read_text(encoding='utf-8')
    (root / 'kommun.toml').write_text(toml.replace('lan = "Exempels län"', ''), encoding='utf-8')
    with pytest.raises(kommun.KommunProfilError, match='saknar lan'):
        kommun.load(root)


def test_missing_library_is_refused(tmp_path):
    root = tmp_path / 'k'
    shutil.copytree(kommun.BUNDLED_DIR / 'exempel', root)
    (root / 'parameters_library.md').unlink()
    with pytest.raises(kommun.KommunProfilError, match='parameters_library.md'):
        kommun.load(root)


@pytest.mark.karlstad
def test_every_bundled_profile_loads():
    slugs = sorted(p.name for p in kommun.BUNDLED_DIR.iterdir() if p.is_dir())
    assert slugs == ['exempel', 'karlstad']
    for slug in slugs:
        k = kommun.bundled(slug)
        assert k.slug == slug and k.lokal_kontext and k.parameters_file.is_file()
