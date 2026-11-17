"""The fixes from the review of November 2026 (after 1.0.0 went public).

One section per finding. Every fix has a test that failed against the code
before it; the tests beside it hold what must go on working.
"""
from __future__ import annotations

import copy
import json
import secrets
import subprocess

import pytest
from caia.calc import CalcModel, compute, render_appendix, render_markdown
from caia.calc.schema import UNBOUNDED_YEAR, YEAR_MAX, YEAR_MIN
from caia.web import app as A
from test_report_row import _inline_script


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(A, 'CAIA_DEV_OPEN', True)
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    monkeypatch.setattr(A, 'CAIA_PASSWORD', '')
    return A.app.test_client()


def _driver(i: int = 0, **over) -> dict:
    d = {
        'name': f'Drivare nummer {i + 1} med ett vanligt långt namn', 'baseline_year': 2023,
        'a0': 1234567.0 + i, 'ef0': 0.123, 'a0_unit': 'fordonskm/år', 'ef0_unit': 'kg CO2e/fordonskm',
        'g_a': {'min': -0.01, 'med': 0.0, 'max': 0.01}, 'g_ef': -0.02,
        'delta_a': {'min': -0.05, 'med': -0.10, 'max': -0.20},
        'delta_ef': {'min': 0.0, 'med': -0.05, 'max': -0.1},
        'terr': 1.0, 'cons': 0.8, 'overlap': 0.8,
        'attribution': {'min': 0.3, 'med': 0.5, 'max': 0.7},
        'ramp': {'start_year': 2025, 'full_effect_year': 2028, 'profile': 'linjär'},
    }
    d.update(over)
    return d


def _model(n: int = 1, target: int = 2030, **over) -> dict:
    m = {'action_name': 'Provåtgärd', 'target_year': target, 'key_years': [2026, target],
         'drivers': [_driver(i) for i in range(n)]}
    m.update(over)
    return m


# ---------- a year outside what an analysis can be about is refused ----------
#
# The engine walks every year from the first start year to the target year
# and writes a table row for each. Nothing bounded the years: target_year
# 203 000 (2030 with a slipped digit) kept a request computing for 20 s and
# wrote 90 MB of text for one driver (measured 2026-11-10), and start_year 24
# gave a headline of 10^15 ton without a warning.

def _with(path: str, value) -> dict:
    m = _model()
    node = m
    keys = path.split('.')
    for k in keys[:-1]:
        node = node[int(k)] if k.isdigit() else node[k]
    node[keys[-1]] = value
    return m


@pytest.mark.parametrize('path, value', [
    ('target_year', 2_000_000),
    ('target_year', 10 ** 12),
    ('target_year', 203),
    ('target_year', True),
    ('drivers.0.ramp.start_year', 24),
    ('drivers.0.ramp.start_year', 0),
    ('drivers.0.ramp.start_year', -5),
    ('drivers.0.ramp.start_year', True),
    ('drivers.0.baseline_year', 23),
    ('drivers.0.baseline_year', 1_000_000),
    ('drivers.0.grant_year', 20245),
    ('drivers.0.ramp.end_year', 28),
    ('drivers.0.ramp.end_year', {'min': 2027, 'med': 28, 'max': 2030}),
    ('key_years', [2026, 20300]),
    ('followup_year', 20260),
    ('grants', [{'year': 24, 'amount': 100000}]),
])
def test_a_year_no_analysis_means_is_refused(path, value):
    with pytest.raises(ValueError):
        CalcModel.from_dict(_with(path, value))


def test_a_one_off_in_a_year_no_analysis_means_is_refused():
    m = _model()
    m['drivers'][0].update(kind='engång', year=24)
    with pytest.raises(ValueError, match='year=24'):
        CalcModel.from_dict(m)


def test_the_refusal_names_the_field_and_the_range():
    with pytest.raises(ValueError, match=f'ramp.start_year=24 ligger utanför {YEAR_MIN} till {YEAR_MAX}'):
        CalcModel.from_dict(_with('drivers.0.ramp.start_year', 24))


@pytest.mark.parametrize('path, value', [
    ('target_year', 2045),
    ('target_year', 2100),
    ('drivers.0.ramp.start_year', 1990),
    ('drivers.0.baseline_year', 1990),
    # "Full effect never comes" and "the effect never ends" are things an
    # extraction says with a year far out. The engine never walks to either.
    ('drivers.0.ramp.full_effect_year', 9999),
    ('drivers.0.ramp.end_year', UNBOUNDED_YEAR),
    ('drivers.0.ramp.end_year', 2500),
    ('drivers.0.ramp.end_year', {'med': 2028}),
    ('followup_year', 2026),
    ('key_years', [2020, 2026, 2030, 2045]),
])
def test_the_years_real_analyses_use_still_pass(path, value):
    compute(CalcModel.from_dict(_with(path, value)))


def test_the_year_check_changes_no_number_of_an_analysis_inside_the_range():
    """The same model with and without the check gives the same result: the
    check only raises."""
    m = _model(3, target=2045)
    a = compute(CalcModel.from_dict(copy.deepcopy(m)))
    assert a['headline']['net'] == pytest.approx(compute(CalcModel.from_dict(m))['headline']['net'])
    assert a['headline']['net'] != 0


def test_a_year_far_out_costs_no_computation_in_the_route(client, monkeypatch):
    """The extraction is the model's text, and the model reads the user's: a
    target year of two million reached compute(). Refused in the reading, the
    request goes to the fallback like any other form the engine cannot use."""
    walked = []
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda *a, **k: _model(target=2_000_000))
    monkeypatch.setattr(A, 'compute', lambda model: walked.append(model) or pytest.fail('computed'))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: 'LLM-FALLBACK')
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is False and not walked


# ---------- the server takes back the kalkyl text it wrote itself ----------
#
# The appendix has a row per driver, scenario and year. Twelve drivers (the
# most a step takes) to 2045 gave 112 000 characters, the page sent them back
# as a turn of the history, and /api/qa refused the turn: the analysis could
# not be finished.

def _kalkyl_text(m: dict) -> str:
    model = CalcModel.from_dict(copy.deepcopy(m))
    result = compute(model)
    return render_markdown(model, result) + '\n\n' + render_appendix(model, result)


def test_twelve_drivers_to_2045_is_longer_than_the_old_turn_cap_and_fits_the_new():
    text = _kalkyl_text(_model(A.MAX_DRIVERS, target=2045))
    assert len(text) > 100_000          # what the cap was
    assert len(text) <= A.MAX_TURN_CHARS


def test_the_next_step_takes_the_kalkyl_of_twelve_drivers_to_2045(client, monkeypatch):
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda *a, **k: _model(A.MAX_DRIVERS, target=2045))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: pytest.fail('fell back'))
    body = client.post('/api/kalkyl', json={'history': []}).get_json()
    assert body['deterministic'] is True
    seen = []
    monkeypatch.setattr(A, 'run_cove_qa', lambda history, **k: seen.append(history) or 'Status: ok')
    history = [{'role': 'user', 'content': 'Åtgärd'}, {'role': 'assistant', 'content': body['output']}]
    resp = client.post('/api/qa', json={'history': history})
    assert resp.status_code == 200, resp.get_json()
    assert seen and seen[0][1]['content'] == body['output']


def test_a_kalkyl_too_long_to_go_on_is_refused_where_it_is_made(client, monkeypatch):
    """Twelve drivers to 2100 is over the cap too. Said at the kalkyl step in
    words the user can act on, without a second model call for the fallback."""
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda *a, **k: _model(A.MAX_DRIVERS, target=2100))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: pytest.fail('started the fallback'))
    resp = client.post('/api/kalkyl', json={'history': []})
    assert resp.status_code == 422
    error = resp.get_json()['error']
    assert '12 drivare' in error and '2100' in error and 'Dela upp' in error


def test_a_kalkyl_that_makes_the_whole_history_too_long_is_refused_there_too(client, monkeypatch):
    """112 000 characters fit a turn, but not after 300 000 of history: the
    next step would refuse the analysis as too long, without saying why."""
    monkeypatch.setattr(A, 'run_kalkyl_extract', lambda *a, **k: _model(A.MAX_DRIVERS, target=2045))
    monkeypatch.setattr(A, 'run_kalkyl', lambda *a, **k: pytest.fail('started the fallback'))
    long = [{'role': 'user', 'content': 'x' * 150_000}, {'role': 'assistant', 'content': 'y' * 150_000}]
    resp = client.post('/api/kalkyl', json={'history': long})
    assert resp.status_code == 422 and 'Dela upp' in resp.get_json()['error']
    short = [{'role': 'user', 'content': 'x' * 100_000}, {'role': 'assistant', 'content': 'y' * 100_000}]
    assert client.post('/api/kalkyl', json={'history': short}).status_code == 200


def test_the_total_still_bounds_what_a_call_can_carry(client, monkeypatch):
    """The turn cap went up; the total, which is what bounds the tokens, did not."""
    assert A.MAX_HISTORY_CHARS == 400_000
    monkeypatch.setattr(A, 'run_cove_qa', lambda *a, **k: pytest.fail('reached the model'))
    history = [{'role': 'user', 'content': 'x' * A.MAX_TURN_CHARS}] * 3
    assert client.post('/api/qa', json={'history': history}).status_code == 400


def test_the_evidens_parts_keep_their_own_cap(client, monkeypatch):
    assert A.MAX_PARTS_CHARS == 100_000
    monkeypatch.setattr(A, 'split_part', lambda driver, text: None)
    monkeypatch.setattr(A, 'run_merge', lambda *a, **k: pytest.fail('reached the model'))
    history = [{'role': 'user', 'content': 'Åtgärd'},
               {'role': 'assistant', 'content': 'Drivare 1: a\nDrivare 2: b\n'}]
    resp = client.post('/api/evidens/merge', json={'history': history, 'parts': [
        {'number': 1, 'text': 'x'}, {'number': 2, 'text': 'x' * (A.MAX_PARTS_CHARS + 1)}]})
    assert resp.status_code == 400


# ---------- a number too large for a float is a refused request, not a 500 ----------

@pytest.mark.parametrize('value', [10 ** 400, -(10 ** 400)])
def test_a_key_metric_too_large_for_a_float_is_refused(value):
    with pytest.raises(A.RequestError, match='key_metric.net ska vara ett tal'):
        A._client_key_metric({'net': value})


def test_ordinary_key_metrics_still_pass():
    assert A._client_key_metric({'net': 12.5, 'terr': 3, 'cons': None, 'year': 2030}) is not None
    assert A._client_key_metric({'net': 10 ** 12}) is not None
    with pytest.raises(A.RequestError):
        A._client_key_metric({'net': True})
    with pytest.raises(A.RequestError):
        A._client_key_metric({'net': float('inf')})


# ====================================================================
# The page: a number or a report from one analysis shown with another
# ====================================================================
#
# These run the page's own script in Node.js, cut out between two of its
# comments, against a page of stubs (as test_client_ui.py does).

node = pytest.mark.node


def _between(js: str, start: str, end: str) -> str:
    i = js.index(start)
    return js[i:js.index(end, i)]


def _node(program: str) -> dict:
    """What the program printed as JSON. It goes to node on stdin."""
    out = subprocess.run(['node', '-'], input=program, check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


# Elements by id, each with a style: what the page's functions read and write.
_DOM = """
const els = {};
const el = (id) => (els[id] = els[id] || {id, style: {display: ''}, innerHTML: '', textContent: '',
                                          scrollTo() {}, children: [], classList: {remove() {}}});
const document = {getElementById: el};
"""


# ---------- opening a saved report ----------

def _open_saved_program(body: str) -> str:
    js = _inline_script()
    return _DOM + """
let runToken = 0, heroChartData = {years: [2026]};
let state = {history: [], phase: 'idle', reportMarkdown: null};
const reportOpen = new Set();
const shown = [], said = [];
let resets = 0;
function resetAll() { resets++; runToken++; state = {history: [], phase: 'idle', reportMarkdown: null}; }
function confirmDiscard() { return true; }
function addSystem(text) { said.push(text); }
function setHeroInterpretation(t) { el('heroInterp').innerHTML = t; }
function setHeroLabel() {} function updateProgress() {}
// As the page's showReport: the card comes up only for a row that has a number.
function showReport(md, km) {
  if (km) el('heroCard').style.display = '';
  shown.push({md, heroCard: el('heroCard').style.display});
}
const ROWS = {
  utan: {formatted_report: 'RAPPORT UTAN TAL', key_metric: null, action_name: 'A'},
  med: {formatted_report: 'RAPPORT MED TAL', key_metric: {net: 12}, action_name: 'B'},
};
// Each fetch answers when the test says so.
const answer = {};
function authFetch(url) {
  const id = decodeURIComponent(url.split('/').pop());
  return new Promise(resolve => { answer[id] = () => resolve({ok: true, jsonSafe: async () => ROWS[id]}); });
}
""" + _between(js, 'function analysisInProgress()', 'window.addEventListener') \
        + _between(js, '// Take the number down', '// Park the user at a gate') \
        + _between(js, 'let openSavedSeq = 0;', '/* ---------- chat helpers') + """
(async () => {
""" + body + """
  console.log(JSON.stringify({shown, said, resets, report: state.reportMarkdown,
    heroCard: el('heroCard').style.display, heroWarn: el('heroWarn').style.display,
    feed: el('analysisFeed').style.display}));
})();
"""


@node
def test_a_saved_report_without_a_number_does_not_stand_under_the_last_ones():
    """A finished analysis leaves its number on screen. A saved row whose calc
    fell back to the model has none (key_metric null), and was shown under the
    number of the analysis before it."""
    out = _node(_open_saved_program("""
  el('heroCard').style.display = '';       // the last analysis' number is up
  state = {history: [1, 2], phase: 'done', reportMarkdown: 'DEN FÖRRA'};
  const p = openSaved('utan'); answer.utan(); await p;
"""))
    assert out['report'] == 'RAPPORT UTAN TAL'
    assert out['shown'] == [{'md': 'RAPPORT UTAN TAL', 'heroCard': 'none'}]
    assert out['heroCard'] == 'none' and out['heroWarn'] == 'none'


@node
def test_a_saved_report_with_a_number_shows_its_own():
    out = _node(_open_saved_program("""
  el('heroCard').style.display = '';
  const p = openSaved('med'); answer.med(); await p;
"""))
    assert out['shown'] == [{'md': 'RAPPORT MED TAL', 'heroCard': ''}]


@node
def test_two_clicks_show_the_report_clicked_last_whichever_answers_last():
    out = _node(_open_saved_program("""
  const a = openSaved('utan'), b = openSaved('med');
  answer.med(); await b;      // the second click answers first
  answer.utan(); await a;     // the first click answers last
"""))
    assert out['report'] == 'RAPPORT MED TAL'
    assert [s['md'] for s in out['shown']] == ['RAPPORT MED TAL']


@node
def test_a_report_on_its_way_does_not_replace_an_analysis_begun_meanwhile():
    """Nobody was asked: the page was idle when the report was clicked."""
    out = _node(_open_saved_program("""
  const p = openSaved('med');
  state.history.push({role: 'user', content: 'Ny åtgärd'}); state.phase = 'running';
  answer.med(); await p;
"""))
    assert out['shown'] == [] and out['report'] is None and out['resets'] == 0
    assert out['feed'] == ''          # the feed the steps draw into is not hidden


@node
def test_a_report_on_its_way_is_dropped_after_ny_analys():
    out = _node(_open_saved_program("""
  const p = openSaved('med');
  resetAll();
  answer.med(); await p;
"""))
    assert out['shown'] == [] and out['report'] is None


@node
def test_an_analysis_in_progress_is_still_replaced_once_the_user_said_so():
    """The question was asked and answered yes before the fetch: the analysis
    goes when the report has arrived, as before."""
    out = _node(_open_saved_program("""
  state = {history: [1, 2, 3], phase: 'emap', reportMarkdown: null};
  const p = openSaved('med'); answer.med(); await p;
"""))
    assert out['resets'] == 1 and out['report'] == 'RAPPORT MED TAL'


# ---------- a new analysis with a saved report on screen ----------

def _first_message_program(state: str) -> str:
    js = _inline_script()
    return """
let runToken = 0;
const order = [];
let state = STATE;
const input = {value: 'Gratis kollektivtrafik för unga', style: {}};
const document = {getElementById: (id) => id === 'chatInput' ? input : {}};
function resetAll() { order.push('reset'); runToken++;
                      state = {history: [], running: false, phase: 'idle', mode: 'potential', reportMarkdown: null}; }
function addUser() { order.push('user'); }
function addSystem() { order.push('system'); }
function lockMode() {} function addSpinner() {} function removeSpinner() {}
function setInputEnabled() {} function showApprove() {} function updateProgress() {}
function addVoice() {} function renderProfiles() {} function panelSection() { return null; }
async function authFetch() { order.push('intake'); return {ok: false, status: 502, jsonSafe: async () => ({error: 'x'})}; }
""".replace('STATE', state) \
        + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') \
        + _between(js, '// Park the user at a gate', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline') + """
sendMessage().then(() => console.log(JSON.stringify({order})));
"""


@node
def test_a_first_message_with_a_saved_report_on_screen_clears_the_panel_first():
    """openSaved hides the feed the steps draw into. A new analysis typed
    under a saved report ran behind it, unseen, gates included."""
    out = _node(_first_message_program(
        "{history: [], running: false, phase: 'idle', mode: 'potential', reportMarkdown: 'SPARAD RAPPORT'}"))
    assert out['order'][:3] == ['reset', 'user', 'intake']


@node
@pytest.mark.parametrize('state, order', [
    # Nothing on screen: nothing to clear.
    ("{history: [], running: false, phase: 'idle', mode: 'potential', reportMarkdown: null}",
     ['user', 'intake', 'system']),
    # A finished analysis: the message is answered, not run, and its report stays.
    ("{history: [1, 2], running: false, phase: 'done', mode: 'potential', reportMarkdown: 'KLAR RAPPORT'}",
     ['user', 'system']),
])
def test_a_message_clears_nothing_but_a_saved_report_on_an_idle_page(state, order):
    assert _node(_first_message_program(state))['order'] == order


# ---------- a kalkyl the model computed takes the old number down ----------

def _kalkyl_step_program(data: str) -> str:
    js = _inline_script()
    return _DOM + """
let heroChartData = {years: [2026]};
const state = {};
const drawn = [];
function stepParts(step, output) { return {panel: output}; }
function keyPointsHtml() { return ''; } function kalkylKeyPoints() { return []; }
function panelStepDone() {} function withKallmarkering(md) { return md; }
function setHeroInterpretation(t) { el('heroInterp').innerHTML = t; }
function renderKalkylHero(h) { drawn.push(h); el('heroCard').style.display = ''; }
""" + _between(js, '// Draw one step', '// Park the user at a gate') + """
// The first kalkyl of the run was the engine's: its number is up.
renderStepOutput('kalkyl', {output: 'KALKYL 1', headline: {net: 216}, span: {}, warnings: ['Varning']});
el('heroScenario').style.display = ''; el('heroWarn').style.display = '';
renderStepOutput('kalkyl', DATA);
console.log(JSON.stringify({drawn, heroCard: el('heroCard').style.display,
  scenario: el('heroScenario').style.display, warn: el('heroWarn').style.display, chart: heroChartData}));
""".replace('DATA', data)


@node
def test_a_rerun_kalkyl_without_a_number_takes_the_first_ones_number_down():
    """A retry after a failed QA runs the kalkyl again. When the engine could
    not read that one, the first one's number, range and warnings stayed above
    a report whose numbers were the language model's."""
    out = _node(_kalkyl_step_program("{output: 'KALKYL 2 (språkmodellen)', headline: null}"))
    assert out['heroCard'] == 'none' and out['scenario'] == 'none' and out['warn'] == 'none'
    assert out['chart'] is None and len(out['drawn']) == 1


@node
def test_a_rerun_kalkyl_with_a_number_shows_the_new_one():
    out = _node(_kalkyl_step_program("{output: 'KALKYL 2', headline: {net: 180}, span: {}, warnings: []}"))
    assert out['heroCard'] == '' and [h['net'] for h in out['drawn']] == [216, 180]


# ---------- the save's answer belongs to the run that asked ----------

_FOLLOW_UP = ("{history: [{content: 'x'}], profiles: [], mode: 'uppfoljning', headline: {net: 40}, "
              "lastKalkyl: {span: {mode: 'uppfoljning', window: [2023, 2030]}}}")


def _finish_report_program(before_answer: str, state: str = _FOLLOW_UP, answer: str = 'answer') -> str:
    js = _inline_script()
    return (_DOM + """
// "Sparat" is cleared after 2,5 s: not waited out here.
const later = setTimeout;
globalThis.setTimeout = (fn, ms) => ms > 100 ? 0 : later(fn, ms);
let runToken = 0, heroChartData = null;
let state = STATE;
const HAS_SUPABASE = true, currentUser = {id: 'u1'};
const heroes = [], labels = [];
let lists = 0;
const said = [];
function addSystem(text, isErr) { said.push([text, !!isErr]); }
function showReport() {} function drawHeroChart() {} function loadSavedList() { lists++; }
function updateHero(km) { heroes.push(km); labels.push(['updateHero', null]); }
function setHeroLabel(mode, win, year) { labels.push([mode, win || null, year || null]); }
let answer, fail;
function authFetch() { return new Promise((resolve, reject) => {
  answer = () => resolve({ok: true, jsonSafe: async () => ({id: 'r1', key_metric: {net: 40, source: 'calc'}})});
  fail = () => reject(new TypeError('Failed to fetch')); }); }
""".replace('STATE', state) + _between(js, 'async function finishReport(markdown)', "// The report's short interpretation") + """
(async () => {
  const p = finishReport('RAPPORT');
  """ + before_answer + """
  ANSWER(); await p;
  console.log(JSON.stringify({heroes, labels, lists, said, ind: el('saveIndicator').textContent}));
})();
""").replace('ANSWER', answer)


@node
def test_a_save_answered_after_ny_analys_draws_no_number_on_the_new_page():
    out = _node(_finish_report_program('runToken++;   // what resetAll does'))
    assert out['heroes'] == [] and out['labels'] == []
    assert out['lists'] == 1 and out['ind'] == ''     # the row is saved, and listed


@node
def test_a_follow_up_keeps_the_years_in_its_label_when_the_report_is_saved():
    """updateHero writes the label without the years: "medel per år 2023–2030"
    became "medel per år" the moment the report was saved."""
    out = _node(_finish_report_program(''))
    assert out['heroes'] == [{'net': 40, 'source': 'calc'}]
    assert out['labels'][-1] == ['uppfoljning', [2023, 2030], None]
    assert out['ind'] == 'Sparat'


@node
def test_a_number_read_from_the_report_text_keeps_the_label_updatehero_gave_it():
    """No headline from the engine: the saved number is the report's own, and
    the kalkyl's years are not its years."""
    out = _node(_finish_report_program('', state="{history: [{content: 'x'}], profiles: [], mode: 'potential', "
                                                 "headline: null, lastKalkyl: {span: {mode: 'potential', window: [2026, 2030]}}}"))
    assert out['labels'] == [['updateHero', None]]


@node
def test_a_save_that_fails_after_ny_analys_is_said_in_the_chat_not_beside_the_new_analysis():
    """The indicator's "ladda ner den" pointed at a report no longer on screen."""
    out = _node(_finish_report_program('runToken++;', answer='fail'))
    assert out['ind'] == ''
    assert out['said'] == [['Rapporten från den förra analysen kunde inte sparas (Failed to fetch).', True]]


@node
def test_a_save_that_fails_with_the_report_on_screen_stays_beside_it():
    out = _node(_finish_report_program('', answer='fail'))
    assert out['ind'].startswith('Sparfel - rapporten är inte sparad.') and out['said'] == []


# ---------- the portfolio says when the server cannot be reached ----------

@node
def test_a_dropped_connection_in_the_portfolio_is_said_and_the_list_comes_back():
    """postJson rejects when the connection drops. The button stayed disabled
    and nothing was said. renderPortfolioPick draws the list again, with its
    button, and the message above it."""
    js = _inline_script()
    out = _node(_DOM + """
const portfolio = {};
const messages = [];
document.querySelectorAll = () => [{value: 'a'}, {value: 'b'}];
function renderPortfolioPick(message) { messages.push(message); }
function renderPortfolioParts() { messages.push('PARTS'); }
async function postJson() { throw new TypeError('Failed to fetch'); }
""" + _between(js, 'async function portfolioParts()', 'function renderPortfolioParts()') + """
portfolioParts().then(() => console.log(JSON.stringify({messages})),
                      (e) => console.log(JSON.stringify({rejected: String(e)})));
""")
    assert out == {'messages': ['Kunde inte nå servern: Failed to fetch. Försök igen.']}


# ---------- another account in the same page starts on an empty page ----------

def _login_program(logins: str) -> str:
    js = _inline_script()
    return _DOM + """
let currentUser = null, resets = 0;
function resetAll() { resets++; }
function showApp() {} function loadSavedList() {}
""" + _between(js, 'let lastUserId = null;', 'if (HAS_SUPABASE && SUPABASE_URL') + """
(async () => {
  for (const id of LOGINS) {
    currentUser = null; await onLogin({user: {id, email: id + '@kommun.se'}});
    if (id === 'anna') el('savedList').innerHTML = 'ANNAS SPARADE ANALYSER';
  }
  console.log(JSON.stringify({resets, user: currentUser.id, list: el('savedList').innerHTML}));
})();
""".replace('LOGINS', logins)


@node
def test_another_account_signing_in_on_the_same_page_does_not_find_the_last_ones_analysis():
    assert _node(_login_program("['anna', 'bo']")) == {'resets': 1, 'user': 'bo', 'list': ''}


@node
def test_the_same_person_signing_in_again_keeps_the_analysis():
    """A session can run out at a gate: signing in again goes on from there."""
    assert _node(_login_program("['anna', 'anna', 'anna']")) == {
        'resets': 0, 'user': 'anna', 'list': 'ANNAS SPARADE ANALYSER'}


# ====================================================================
# The page is compiled once per process, and rendered for each request
# ====================================================================
#
# A page view took 34 ms, 29 of them compiling the same 260 kB of template
# again (render_template_string compiles on every call). 4 ms after.

def test_the_page_is_compiled_once_for_many_views(client, monkeypatch):
    monkeypatch.setattr(A, '_compiled', {})
    compiled = []
    from_string = A.app.jinja_env.from_string
    monkeypatch.setattr(A.app.jinja_env, 'from_string',
                        lambda source, *a, **k: compiled.append(len(source)) or from_string(source, *a, **k))
    first, second = client.get('/'), client.get('/')
    assert first.status_code == 200 and first.data == second.data
    assert len(compiled) == 1


def test_each_view_is_rendered_with_its_own_values(client, monkeypatch):
    """What is kept is the compiled template, not the page it gave."""
    monkeypatch.setattr(A, 'LICENSE_NOTE', 'Licensrad ett.')
    assert 'Licensrad ett.' in client.get('/').get_data(as_text=True)
    monkeypatch.setattr(A, 'LICENSE_NOTE', 'Licensrad två.')
    page = client.get('/').get_data(as_text=True)
    assert 'Licensrad två.' in page and 'Licensrad ett.' not in page


def test_two_pages_do_not_share_a_compiled_template_and_values_are_still_escaped(monkeypatch):
    monkeypatch.setattr(A, '_compiled', {})
    with A.app.test_request_context('/'):
        assert A._render('a {{ x }}', x=1) == 'a 1'
        assert A._render('b {{ x }}', x=2) == 'b 2'
        assert A._render('a {{ x }}', x='<script>') == 'a &lt;script&gt;'
    assert len(A._compiled) == 2


def test_the_login_page_goes_the_same_way(monkeypatch):
    monkeypatch.setattr(A, 'SUPABASE_URL', '')
    # A random value per run, as in test_auth_gate.py: nothing to find in the repo.
    monkeypatch.setattr(A, 'CAIA_PASSWORD', secrets.token_urlsafe(12))
    page = A.app.test_client().get('/login')
    assert page.status_code == 200 and b'<form' in page.data
    assert A.LOGIN_TEMPLATE in A._compiled


# ---------- "milj." is a million in the comparison with what was approved ----------
#
# The pattern asked for a word boundary after "milj.", and there is none
# between a point and a space: "1,3 milj. ton" was read as 1,3, and the same
# number written out in the next step was marked as changed a million times.

@pytest.mark.parametrize('text, value', [
    ('1,3 milj. ton', 1_300_000),
    ('1,3 milj.', 1_300_000),
    ('ca 2 milj. kr per år', 2_000_000),
    ('1,3 miljoner ton', 1_300_000),
    ('en miljon', None),                    # no number written
    ('3 tusen', 3_000),
    ('3 tusendelar', 3),                    # another word: not a thousand
    ('5 miljonprogram', 5),
])
def test_an_abbreviated_million_is_read_as_a_million(text, value):
    from caia import godkant
    got = [n.value for n in godkant.numbers(text)]
    assert got == ([] if value is None else [pytest.approx(value)])


# ---- the sanitiser is not older than its open advisories ----

def test_the_sanitiser_is_at_least_the_version_without_open_advisories():
    """DOMPurify is what keeps model text from running in the page. Three
    advisories (one critical, one high, one low) were open against 3.4.16 and
    older when the review was made, and the update proposal had waited two
    weeks. None of the three applies to the options the page uses, by their
    own summaries, but the page should not sit below the fixed version."""
    import re
    url = A.PAGE_LIBS['dompurify'][0]
    version = tuple(int(n) for n in re.search(r'/dompurify@(\d+)\.(\d+)\.(\d+)/', url).groups())
    assert version >= (3, 4, 17), url
