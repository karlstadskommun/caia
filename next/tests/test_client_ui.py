"""The page's own logic, run in node against stubbed DOM helpers.

Four things the handover review found in the client: numbers under ten tons
showed as "0" while the calc text said "0,4"; a failed final leg left its
bridge and kalkyl in the history, so every retry sent the next agent one more
of each; the approve button stayed clickable while intake was still asking
questions; and a refused account saw "no saved analyses yet" instead of why.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile

import pytest
from test_report_row import _inline_script
from caia.calc.engine import _fmt

pytestmark = pytest.mark.node


def _between(js: str, start: str, end: str) -> str:
    i = js.index(start)
    return js[i:js.index(end, i)]


def _node(program: str) -> dict:
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run(['node', f.name], check=True, capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return json.loads(out.stdout)


# ---------- the headline number reads like the calc text ----------

@pytest.mark.parametrize('n', [0.44, -0.44, 5, 9.96, 0.04, -0.04, 12.4, 1234.6, -2500])
def test_the_page_formats_tons_as_the_calc_text_does(n):
    fmt = _between(_inline_script(), 'function fmt(n)', '\n}\n') + '\n}\n'
    out = _node(fmt + f'console.log(JSON.stringify({{s: fmt({n})}}));')
    # sv-SE groups thousands with a no-break space and writes a true minus sign
    # (U+00A0/U+202F, U+2212); the calc text uses a plain space and a hyphen.
    page = out['s']
    for char, plain in ((chr(0xA0), ' '), (chr(0x202F), ' '), (chr(0x2212), '-')):
        page = page.replace(char, plain)
    assert page == _fmt(n)


# ---------- a failed run leaves the history as it found it ----------

GATE_STUBS = """
let runToken = 0;
const shown = [];
const state = {history: [{role: 'user', content: 'Åtgärd'}, {role: 'assistant', content: 'antaganden'}],
               running: false, phase: 'assumptions'};
function showApprove(on) { shown.push(on); }
function setInputEnabled() {}
function panelSection() { return null; }
function clearStepNote() {}
function addSystem() {}
function updateProgress() {}
const document = {getElementById: () => ({})};
"""


def test_a_failed_final_leg_can_be_retried_without_stacking_the_bridge():
    js = _inline_script()
    program = GATE_STUBS + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') + """
// kalkyl finishes, QA fails: the half-run leaves one output behind.
async function runStages(stages) {
  state.history.push({role: 'assistant', content: 'kalkyl'});
  state.history.push({role: 'user', content: BRIDGE.kalkyl});
  return false;
}
""" + _between(js, '// Park the user at a gate', '// Show an intermediate agent') + """
(async () => {
  const before = state.history.length;
  await approveGate('assumptions');
  const afterOne = state.history.length;
  await approveGate('assumptions');
  console.log(JSON.stringify({before, afterOne, afterTwo: state.history.length,
                              phase: state.phase, approveShown: shown[shown.length - 1]}));
})();
"""
    out = _node(program)
    assert out['afterOne'] == out['before']
    assert out['afterTwo'] == out['before']
    assert out['phase'] == 'assumptions' and out['approveShown'] is True


# ---------- a failed re-run at a gate leaves the version being approved on screen ----------
#
# Feedback at a gate re-runs the step. When that failed, the section showed
# the error where the version had been, the chat said "den tidigare versionen
# till höger gäller fortfarande", and the approve button approved a version
# no longer on screen.
#
# The panel functions, the gate and sendMessage below are the page's own. The
# DOM is a stand-in that keeps child nodes and class names. Setting innerHTML
# leaves one opaque node, so nothing is found inside it: where the note lands
# among the children is checked in a real browser, not here.

PANEL_DOM = """
class El {
  constructor() {
    this.className = ''; this.childNodes = []; this.dataset = {}; this.parent = null;
    this.text = ''; this.html = null;
    this.classList = {add: (c) => { if (!this.className.split(' ').includes(c)) this.className += ' ' + c; }};
  }
  set innerHTML(h) { const raw = new El(); raw.html = h; this.replaceChildren(raw); }
  set textContent(t) { this.text = t; this.replaceChildren(); }
  dump() {
    if (this.html !== null) return this.html;
    return '<div class="' + this.className + '">' + this.text + this.childNodes.map(n => n.dump()).join('') + '</div>';
  }
  appendChild(n) { n.parent = this; this.childNodes.push(n); return n; }
  replaceChildren(...nodes) {
    this.childNodes.forEach(n => { n.parent = null; });
    this.childNodes = nodes; nodes.forEach(n => { n.parent = this; });
  }
  insertBefore(n, ref) {
    const i = ref ? this.childNodes.indexOf(ref) : -1;
    n.parent = this;
    if (i < 0) this.childNodes.push(n); else this.childNodes.splice(i, 0, n);
    return n;
  }
  remove() {
    if (!this.parent) return;
    this.parent.childNodes = this.parent.childNodes.filter(x => x !== this); this.parent = null;
  }
  querySelectorAll(sel) { return this.childNodes.filter(n => n.html === null && ('.' + n.className) === sel); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  scrollIntoView() {}
}
const feed = new El();
const input = {value: 'Byt nivå till strategisk', style: {}};
const document = {
  createElement: () => new El(),
  getElementById: (id) => id === 'chatInput' ? input : id === 'analysisFeed' ? feed : {},
  querySelector: (sel) => feed.childNodes.find(n => sel.includes('"' + n.dataset.pstep + '"')) || null,
};
let runToken = 0;
const shown = [], said = [];
const state = {history: [{role: 'user', content: 'Åtgärd'}, {role: 'assistant', content: 'EMAP VERSION 1'}],
               running: false, phase: 'emap', mode: 'potential'};
const PANEL_STEPS = {emap: {num: 2, title: 'EMAP'}};
const STEP_LABELS = {emap: 'EMAP'};
function showApprove(on) { shown.push(on); }
function setInputEnabled() {} function updateProgress() {} function showAnalysisCard() {}
function addUser() {} function lockMode() {} function addSpinner() {} function removeSpinner() {}
function renderEvidence() {} function renderKalkylHero() {}
function addSystem(text, isErr) { said.push({text, isErr: !!isErr}); }
const voiced = [];
function addVoice(md, tag) { voiced.push({md, tag}); }
function escapeHtml(s) { return s; }
function cleanOutput(md) { return md; }
function renderMarkdownWithChips(md) { if (md.includes('GÅR INTE ATT RITA')) throw new Error('trasigt svar'); return md; }
function withKallmarkering(md) { return md; }
async function runStages() { return true; }
"""


def _gate_rerun_program(post_step: str, then: str = '') -> str:
    js = _inline_script()
    return PANEL_DOM + 'async function postStep(step, history) { ' + post_step + ' }\n' \
        + _between(js, 'function panelSection(step)', '// Hero + scenario range') \
        + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') \
        + _between(js, '// Draw one step', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline') + """
(async () => {
  panelStepDone('emap', 'EMAP VERSION 1');
  const sec = panelSection('emap');
  const kept = sec.childNodes[0];
  const before = {history: state.history.length, className: sec.className, panel: sec.dump()};
  await sendMessage();
  """ + then + """
  console.log(JSON.stringify({before, panel: sec.dump(), className: sec.className,
    sameNode: sec.childNodes.includes(kept), history: state.history.length,
    phase: state.phase, approveShown: shown[shown.length - 1], said, voiced,
    last: state.history[state.history.length - 1], sent: globalThis.sent || null}));
})();
"""


NOTE = 'Det här är den tidigare versionen, och det är den du godkänner.'


@pytest.mark.parametrize('post_step, error', [
    ("return {ok: false, data: {error: 'Modellen svarade inte.'}};", 'Modellen svarade inte.'),
    ("throw new Error('Failed to fetch');", 'Nätverksfel: Failed to fetch'),
    # The server answered, but the new version could not be drawn: it must not
    # sit in the history behind a panel that shows the old one.
    ("return {ok: true, data: {output: 'EMAP VERSION 2 GÅR INTE ATT RITA'}};",
     'Den nya versionen kunde inte visas: trasigt svar'),
])
def test_a_failed_rerun_at_a_gate_keeps_the_previous_version_on_screen(post_step, error):
    out = _node(_gate_rerun_program(post_step))
    assert 'EMAP VERSION 1' in out['before']['panel']
    # The version the approve button approves is back, as the same nodes...
    assert 'EMAP VERSION 1' in out['panel']
    assert out['sameNode'] is True
    assert out['className'] == out['before']['className'] == 'step-sec done'
    assert 'shimmer' not in out['panel'] and 'räknar...' not in out['panel']
    # ...and the error is said beside it, once, not in its place.
    assert out['panel'].count(NOTE) == 1 and error in out['panel']
    assert out['approveShown'] is True and out['phase'] == 'emap'
    assert out['history'] == out['before']['history']
    assert out['said'][-1]['isErr'] and 'gäller fortfarande' in out['said'][-1]['text']


def test_the_chat_does_not_claim_a_version_stands_when_none_could_be_put_back():
    # No section to keep (it never happens at a gate today): the error is all
    # the panel has, so the chat must not point at a version to the right.
    js = _inline_script()
    program = PANEL_DOM + "async function postStep() { return {ok: false, data: {error: 'Modellen svarade inte.'}}; }\n" \
        + _between(js, 'function panelSection(step)', '// Hero + scenario range') \
        + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') \
        + _between(js, '// Draw one step', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline') + """
(async () => {
  await sendMessage();
  console.log(JSON.stringify({panel: panelSection('emap').dump(), said, approveShown: shown[shown.length - 1]}));
})();
"""
    out = _node(program)
    assert NOTE not in out['panel']
    assert out['said'][-1]['isErr'] and 'gäller fortfarande' not in out['said'][-1]['text']
    assert 'Skicka rättelsen en gång till' in out['said'][-1]['text']
    assert out['approveShown'] is False  # nothing on screen to approve


def test_a_rerun_that_works_replaces_the_version_and_leaves_no_note():
    out = _node(_gate_rerun_program("return {ok: true, data: {output: 'EMAP VERSION 2'}};"))
    assert 'EMAP VERSION 2' in out['panel'] and 'EMAP VERSION 1' not in out['panel']
    assert NOTE not in out['panel'] and out['sameNode'] is False
    assert out['history'] == out['before']['history'] + 2  # the feedback and the new version
    assert not out['said'][-1]['isErr']


def test_two_failed_reruns_leave_one_note_and_approval_removes_it():
    fail = "return {ok: false, data: {error: 'Modellen svarade inte.'}};"
    again = "input.value = 'Försök igen'; await sendMessage();"
    out = _node(_gate_rerun_program(fail, then=again))
    assert out['panel'].count(NOTE) == 1 and 'EMAP VERSION 1' in out['panel']
    assert out['history'] == out['before']['history']
    out = _node(_gate_rerun_program(fail, then=again + " await approveGate('emap');"))
    assert NOTE not in out['panel'] and 'Modellen svarade inte.' not in out['panel']
    assert 'EMAP VERSION 1' in out['panel'] and out['sameNode'] is True



# ---------- a comment at a gate: the reply in the chat, the version in the panel ----------
# 2026-10-13: a question at the EMAP gate replaced the analysis with
# CAIA's note about its changes. The server now splits the answer
# (caia/feedback.py); the page has to put each part where it belongs.

def test_a_comment_at_a_gate_is_answered_in_the_chat_and_the_version_goes_to_the_panel():
    out = _node(_gate_rerun_program(
        "globalThis.sent = arguments[2] || null;"
        " return {ok: true, data: {reply: 'Jag flyttade nivån till system.', output: 'EMAP VERSION 2'}};"))
    assert out['sent'] == {'feedback': True}
    assert out['voiced'] == [{'md': 'Jag flyttade nivån till system.', 'tag': 'emap'}]
    assert 'EMAP VERSION 2' in out['panel'] and 'Jag flyttade' not in out['panel']
    # Only the version is what the next step reads as the analysis.
    assert out['last'] == {'role': 'assistant', 'content': 'EMAP VERSION 2'}
    assert out['history'] == out['before']['history'] + 2
    assert not out['said'][-1]['isErr'] and 'uppdaterad i panelen' in out['said'][-1]['text']


def test_a_reply_without_a_new_version_leaves_the_version_on_screen_and_says_so_calmly():
    out = _node(_gate_rerun_program(
        "return {ok: true, data: {reply: 'Nivån är System eftersom ...', output: ''}};"))
    assert out['voiced'] and out['voiced'][0]['md'].startswith('Nivån är System')
    assert 'EMAP VERSION 1' in out['panel'] and out['sameNode'] is True
    assert NOTE not in out['panel'] and 'Uppdaterar' not in out['panel']
    assert out['className'] == 'step-sec done'
    # The question was answered, nothing changed: the history is as it was,
    # so approving sends the next step the version on screen.
    assert out['history'] == out['before']['history']
    assert out['approveShown'] is True and out['phase'] == 'emap'
    assert not out['said'][-1]['isErr'] and 'oförändrad' in out['said'][-1]['text']


def test_neither_reply_nor_version_is_a_failed_rerun():
    out = _node(_gate_rerun_program("return {ok: true, data: {reply: '', output: '  '}};"))
    assert out['voiced'] == []
    assert out['panel'].count(NOTE) == 1 and 'EMAP VERSION 1' in out['panel']
    assert out['history'] == out['before']['history']
    assert out['said'][-1]['isErr']


# ---------- intake: no approving a profile that is being rewritten ----------

def _intake_program(reply: str) -> str:
    js = _inline_script()
    return GATE_STUBS.replace("phase: 'assumptions'", "phase: 'profile'") + """
const input = {value: 'Lägg till att bussen är eldriven', style: {}};
document.getElementById = (id) => id === 'chatInput' ? input : {};
function addUser() {} function addSpinner() {} function removeSpinner() {}
function addVoice() {} function renderProfiles() {} function lockMode() {}
async function authFetch(url, opts) { return REPLY; }
""".replace('REPLY', reply) + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') \
        + _between(js, '// Park the user at a gate', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline') + """
(async () => {
  const before = state.history.length;
  await sendMessage();
  console.log(JSON.stringify({before, after: state.history.length, phase: state.phase,
                              approveShown: shown[shown.length - 1]}));
})();
"""


def test_approve_is_hidden_while_intake_asks_a_follow_up_question():
    out = _node(_intake_program(
        "{ok: true, status: 200, jsonSafe: async () => ({status: 'clarifying', message: 'Hur många bussar?'})}"))
    assert out['approveShown'] is False
    assert out['phase'] == 'intake'
    assert out['after'] == out['before'] + 2  # the feedback and the question


def test_a_failed_intake_call_takes_the_message_back_and_restores_the_gate():
    out = _node(_intake_program(
        "{ok: false, status: 502, jsonSafe: async () => ({error: 'Modellen svarade inte.'})}"))
    assert out['after'] == out['before']
    assert out['phase'] == 'profile' and out['approveShown'] is True


# ---------- a refused account is told so ----------

def _saved_list_program(status: int, body: str) -> str:
    js = _inline_script()
    return """
const els = {};
const el = (id) => (els[id] = els[id] || {id, style: {}, innerHTML: '', textContent: '', classList: {toggle() {}}});
const document = {getElementById: el};
const HAS_SUPABASE = true, currentUser = {email: 'a@kommun.se'};
let signedOut = false;
async function signOut() { signedOut = true; }
async function openSaved() {}
async function authFetch() { return {ok: STATUS === 200, status: STATUS, jsonSafe: async () => (BODY)}; }
""".replace('STATUS', str(status)).replace('BODY', body) \
        + _between(js, 'function escapeHtml', '\n') + '\n' \
        + _between(js, 'function authNote', 'function showResend') \
        + _between(js, 'async function loadSavedList', 'async function openSaved') + """
loadSavedList().then(() => console.log(JSON.stringify({
  signedOut, list: el('savedList').innerHTML, authError: el('authError').textContent,
  authErrorShown: el('authError').style.display})));
"""


def test_a_refused_account_is_signed_out_and_told_why():
    out = _node(_saved_list_program(403, "{error: 'Kontot har inte behörighet till CAIA.'}"))
    assert out['signedOut'] is True
    assert out['authError'] == 'Kontot har inte behörighet till CAIA.'
    assert out['authErrorShown'] == 'block'


def test_a_failed_list_says_so_instead_of_claiming_there_is_nothing_saved():
    out = _node(_saved_list_program(502, "{error: 'Kunde inte nå Supabase.'}"))
    assert 'Kunde inte nå Supabase.' in out['list']
    assert 'Inga sparade' not in out['list']
    assert out['signedOut'] is False


# ---------- login errors in Swedish ----------

@pytest.mark.parametrize('english,swedish', [
    ('Invalid login credentials', 'Fel e-postadress eller lösenord.'),
    ('Email not confirmed', 'inte bekräftat'),
    ('User already registered', 'redan ett konto'),
    ('Password should be at least 6 characters.', 'för kort'),
    ('email rate limit exceeded', 'fler mejl'),
    ('For security purposes, you can only request this after 52 seconds.', 'Vänta en minut'),
    ('New password should be different from the old password.', 'annat lösenord'),
    ('Something new from Supabase', 'Inloggningen misslyckades: Something new from Supabase'),
])
def test_supabase_login_errors_reach_the_user_in_swedish(english, swedish):
    js = _inline_script()
    program = _between(js, 'const AUTH_MESSAGES', 'async function handleAuth') + \
        f'console.log(JSON.stringify({{s: authMessage({{message: {json.dumps(english)}}})}}));'
    assert swedish in _node(program)['s']


# ---------- a headline read from the report text says so ----------

@pytest.mark.parametrize('source,marked', [('rapport', True), ('calc', False)])
def test_the_hero_marks_a_headline_that_is_not_the_calcs(source, marked):
    js = _inline_script()
    program = _HERO_PRELUDE + _between(js, 'function fmt(n)', '\n}\n') + '\n}\n' + \
        _between(js, 'function setHeroLabel(', '\n}\n') + '\n}\n' + \
        _between(js, 'function updateHero(km)', '\n}\n') + '\n}\n' + \
        f"updateHero({{net: 4.2, source: {json.dumps(source)}}}); console.log(JSON.stringify({{sub: els.heroSub.innerHTML}}));"
    assert ('inte programmets kalkyl' in _node(program)['sub']) is marked


_HERO_PRELUDE = """
const els = {};
const document = {getElementById: (id) => (els[id] = els[id] || {style: {}, innerHTML: '', textContent: ''})};
const state = {mode: 'potential'};
const MODES = {potential: {hero: 'Förväntad klimatnytta'}, uppfoljning: {hero: 'Beräknad klimatnytta av insatsen'}};
const AVG_WINDOW = [2026, 2030];
"""


# ---------- the headline names the year it is for (2026-10-13) ----------

@pytest.mark.parametrize('km,label', [
    ({'net': 216, 'year': 2030, 'source': 'calc'}, 'Förväntad klimatnytta år 2030'),
    # A row saved before, or the language model's fallback: an average.
    ({'net': 86.4, 'source': 'rapport'}, 'Förväntad klimatnytta, medel per år 2026–2030'),
])
def test_the_hero_label_says_whether_the_number_is_a_year_or_an_average(km, label):
    js = _inline_script()
    program = _HERO_PRELUDE + _between(js, 'function fmt(n)', '\n}\n') + '\n}\n' + \
        _between(js, 'function setHeroLabel(', '\n}\n') + '\n}\n' + \
        _between(js, 'function updateHero(km)', '\n}\n') + '\n}\n' + \
        f"updateHero({json.dumps(km)}); console.log(JSON.stringify({{label: els.heroLabel.textContent}}));"
    assert _node(program)['label'] == label


def test_a_saved_row_says_whether_its_number_is_a_year_or_an_average():
    js = _inline_script()
    program = _between(js, 'function fmt(n)', '\n}\n') + '\n}\n' + \
        _between(js, 'function keyMetricText(', '\n}\n') + '\n}\n' + \
        "console.log(JSON.stringify({y: keyMetricText(216, {net: 216, year: 2030}), " \
        "a: keyMetricText(86.4, {net: 86.4})}));"
    out = _node(program)
    assert out['y'] == '216 ton CO₂e år 2030'
    assert out['a'] == '86 ton CO₂e/år i snitt'


# ---------- sign-up says what happened ----------

def _auth_program(sign_up_result: str, signup: bool = True, sign_in_result: str = '{data: {}, error: null}') -> str:
    js = _inline_script()
    return """
const els = {};
const el = (id) => (els[id] = els[id] || {id, style: {}, textContent: '', value: '',
  classList: {on: false, toggle(c, v) { this.on = v; }}});
const document = {getElementById: el};
const window = {location: {hash: '', search: '', origin: 'https://caia.test', pathname: '/'}};
const history = {replaceState() {}};
let isSignup = SIGNUP;
el('authEmail').value = 'anna@kommun.se'; el('authPassword').value = 'hemligt1';
const supabaseClient = {auth: {
  signUp: async () => (SIGNUP_RESULT),
  signInWithPassword: async () => (SIGNIN_RESULT),
}};
""".replace('SIGNUP_RESULT', sign_up_result).replace('SIGNIN_RESULT', sign_in_result) \
        .replace('SIGNUP', 'true' if signup else 'false') \
        + _between(js, 'function setAuthMode', 'async function resendConfirmation') + """
handleAuth().then(() => console.log(JSON.stringify({
  note: el('authError').textContent, shown: el('authError').style.display,
  info: el('authError').classList.on, resend: el('authResend').style.display, signup: isSignup})));
"""


def test_a_new_account_is_told_to_open_the_mail_and_the_message_stays_on_screen():
    # The message used to be written and hidden again by the mode switch.
    out = _node(_auth_program("{data: {user: {identities: [{id: 'x'}]}, session: null}, error: null}"))
    assert 'Kontot är skapat' in out['note'] and 'anna@kommun.se' in out['note']
    assert out['shown'] == 'block' and out['info'] is True
    assert out['resend'] == 'block' and out['signup'] is False


def test_signing_up_an_address_that_has_an_account_says_so_and_promises_no_mail():
    out = _node(_auth_program("{data: {user: {identities: []}, session: null}, error: null}"))
    assert 'redan ett konto' in out['note'] and 'mejl' not in out['note'].replace('Glömt', '')
    assert out['shown'] == 'block' and out['resend'] == 'none'


def test_an_unconfirmed_login_offers_to_send_the_mail_again():
    out = _node(_auth_program('null', signup=False,
                              sign_in_result="{data: {}, error: {message: 'Email not confirmed'}}"))
    assert 'inte bekräftat' in out['note'] and out['resend'] == 'block' and out['info'] is False


def test_a_wrong_password_does_not_offer_the_mail():
    out = _node(_auth_program('null', signup=False,
                              sign_in_result="{data: {}, error: {message: 'Invalid login credentials'}}"))
    assert out['resend'] == 'none'


# ---------- what a link from a mail brought back ----------

@pytest.mark.parametrize('hash_,search,error,recovery,implicit,cleaned', [
    ('#error=access_denied&error_code=otp_expired&error_description=x', '', 'otp_expired', None, False, True),
    ('', '?reset=1&token_hash=abc123&type=recovery', None, 'abc123', False, True),
    ('#access_token=t&type=recovery&refresh_token=r', '', None, None, True, False),
    # A confirmed sign-up: the client reads its token from the hash, so the
    # page must leave the address alone.
    ('#access_token=t&type=signup&refresh_token=r', '', None, None, False, False),
    ('', '', None, None, False, False),
])
def test_the_page_reads_what_a_mail_link_brought_back(hash_, search, error, recovery, implicit, cleaned):
    js = _inline_script()
    program = """
let cleaned = false;
const window = {location: {hash: HASH, search: SEARCH, pathname: '/'}};
const history = {replaceState() { cleaned = true; }};
""".replace('HASH', json.dumps(hash_)).replace('SEARCH', json.dumps(search)) \
        + _between(js, 'const AUTH_RETURN', 'function returnErrorMessage') \
        + 'console.log(JSON.stringify({r: AUTH_RETURN, cleaned}));'
    out = _node(program)
    assert out['r'] == {'error': error, 'recoveryHash': recovery, 'recoveryImplicit': implicit}
    assert out['cleaned'] is cleaned


# ---------- an analysis in progress is not thrown away without asking ----------

def _discard_program(history_len: int, phase: str, answer: bool) -> str:
    js = _inline_script()
    return """
let asked = 0, resets = 0, prevented = false, handler = null;
const window = {confirm: () => { asked++; return ANSWER; },
                addEventListener: (ev, fn) => { if (ev === 'beforeunload') handler = fn; }};
let state = {history: new Array(LEN).fill({role: 'user', content: 'x'}), phase: PHASE};
function resetAll() { resets++; }
""".replace('ANSWER', 'true' if answer else 'false').replace('LEN', str(history_len)) \
        .replace('PHASE', json.dumps(phase)) \
        + _between(js, 'function analysisInProgress()', 'function resetAll()') + """
startNewAnalysis();
const ev = {preventDefault() { prevented = true; }};
handler(ev);
console.log(JSON.stringify({asked, resets, prevented}));
"""


@pytest.mark.parametrize('history_len,phase,answer,asked,resets,prevented', [
    (3, 'emap', False, 1, 0, True),       # mid-analysis, user says no: nothing lost
    (3, 'emap', True, 1, 1, True),        # mid-analysis, user says yes
    (5, 'running', False, 1, 0, True),
    (0, 'idle', False, 0, 1, False),      # nothing to lose: no question
    (9, 'done', False, 0, 1, False),      # finished, the report is saved
])
def test_new_analysis_and_reload_ask_only_when_work_would_be_lost(history_len, phase, answer,
                                                                   asked, resets, prevented):
    out = _node(_discard_program(history_len, phase, answer))
    assert out == {'asked': asked, 'resets': resets, 'prevented': prevented}


def test_the_new_analysis_button_goes_through_the_question():
    from test_report_row import A
    page = A.HTML_TEMPLATE
    assert 'onclick="startNewAnalysis()">Ny analys</button>' in page
    assert 'onclick="resetAll()"' not in page


def test_a_failed_first_message_comes_back_to_the_input_and_frees_the_mode():
    js = _inline_script()
    program = GATE_STUBS.replace(
        "{history: [{role: 'user', content: 'Åtgärd'}, {role: 'assistant', content: 'antaganden'}],\n               running: false, phase: 'assumptions'}",
        "{history: [], running: false, phase: 'idle', mode: 'potential'}") + """
const input = {value: 'Gratis kollektivtrafik för unga', style: {}};
document.getElementById = (id) => id === 'chatInput' ? input : {};
const locks = [];
function addUser() {} function addSpinner() {} function removeSpinner() {}
function addVoice() {} function renderProfiles() {} function lockMode(on) { locks.push(on); }
async function authFetch() { return {ok: false, status: 502, jsonSafe: async () => ({error: 'Modellen svarade inte.'})}; }
""" + _between(js, 'const BRIDGE = {', '// Run a sequence of pipeline stages') \
        + _between(js, '// Park the user at a gate', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline') + """
sendMessage().then(() => console.log(JSON.stringify({input: input.value, locks, history: state.history.length})));
"""
    out = _node(program)
    assert out['history'] == 0
    assert out['input'] == 'Gratis kollektivtrafik för unga'
    assert out['locks'] == [True, False]


# ---------- the year-by-year chart under the headline ----------

CHART_DOM = """
const els = {};
function el(id) {
  if (!els[id]) els[id] = {id, style: {}, innerHTML: '', textContent: '', clientWidth: 650,
    offsetParent: {}, querySelector: () => null};
  return els[id];
}
const document = {getElementById: el};
function escapeHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function yearSpan(a, b) { return a === b ? String(a) : a + '–' + b; }
"""


def _chart(span_js: str, headline: str = 'undefined') -> dict:
    js = _inline_script()
    program = CHART_DOM + _between(js, 'function fmt(n)', '\n}\n') + '\n}\n' \
        + _between(js, 'let heroChartData = null;', 'let chartResizeTimer') + f"""
renderHeroChart({span_js}, {headline});
const svg = els.heroChartSvg ? els.heroChartSvg.innerHTML : '';
console.log(JSON.stringify({{chart: els.heroChart.style.display, track: els.scenTrack.style.display,
  caption: els.heroChartCaption ? els.heroChartCaption.textContent || els.heroChartCaption.innerHTML : '',
  svg, nan: /NaN|undefined|Infinity/.test(svg),
  years: [...svg.matchAll(/text-anchor="[a-z]+">(\\d{{4}})</g)].map(m => +m[1])}}));
"""
    return _node(program)


def test_the_chart_caption_states_the_headline_average_and_the_target_year():
    # Effect from 2027, full (820 t) from 2032, target 2045: the headline is
    # the mean over 2026–2030, (0 + 136,7 + 273,3 + 410 + 546,7) / 5 = 273,3,
    # and the target year is 820. That gap is what the chart is there to show.
    out = _chart("""(() => {
      const years = []; for (let y = 2025; y <= 2045; y++) years.push(y);
      const med = years.map(y => y < 2027 ? 0 : Math.min(1, (y - 2026) / 6) * 820);
      return {target_year: 2045, window: [2026, 2030], mode: 'potential',
              series: {years, min: med.map(v => v / 2), med, max: med.map(v => v * 1.5)}};
    })()""")
    assert out['chart'] == '' and out['track'] == 'none'
    assert '<b>273</b>' in out['caption'] and '2026–2030' in out['caption']
    assert 'År 2045' in out['caption'] and '<b>820</b>' in out['caption']
    assert not out['nan']
    # The window and the target year are always labelled, and no two year
    # labels (about 30 px wide at 12 px) overlap.
    assert {2026, 2030, 2045} <= set(out['years'])
    assert len(out['years']) == len(set(out['years']))
    spans = []
    for x, anchor in re.findall(r'<text class="chart-text" x="([\d.]+)" y="[\d.]+" text-anchor="([a-z]+)">\d{4}<', out['svg']):
        x = float(x)
        spans.append({'start': (x, x + 30), 'end': (x - 30, x), 'middle': (x - 15, x + 15)}[anchor])
    spans.sort()
    assert len(spans) == len(out['years'])
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), spans


@pytest.mark.parametrize('series', [
    'undefined',
    "{years: [2026, 2027], min: [0, 1], med: [0], max: [0, 2]}",
    "{years: [2026, 2027], min: [0, 1], med: [0, NaN], max: [0, 2]}",
    "{years: [2026, 2027], min: [0, 0], med: [0, 0], max: [0, 0]}",
])
def test_a_series_that_cannot_be_drawn_falls_back_to_the_range_bar(series):
    out = _chart(f"{{target_year: 2030, window: [2026, 2030], series: {series}}}")
    assert out['chart'] == 'none' and out['track'] == ''


def test_the_caption_writes_the_headline_as_the_card_shows_it():
    # The window's mean is 12,46. The server rounds the headline to 12,5 and
    # the card shows 13; rounding the mean once more would print 12 under it.
    out = _chart("""{target_year: 2030, window: [2026, 2030],
      series: {years: [2026, 2027, 2028, 2029, 2030], min: [6, 6, 6, 6, 6.2],
               med: [12, 12, 12, 13, 13.3], max: [20, 20, 20, 20, 20]}}""", '12.5')
    assert '<b>13</b>' in out['caption'].split('År')[0], out['caption']
    assert 'medel 13<' in out['svg']


# ---------- a reply is read from its first line ----------

# A chat stub that lays messages out as a column: each message has a height,
# the container shows 400 px of it. Enough to ask where the chat scrolled to.
CHAT_STUBS = """
const chat = {
  children: [], clientHeight: 400, scrollTop: 0,
  get scrollHeight() { return this.children.reduce((s, m) => s + m.h, 0); },
  appendChild(m) { m.parent = this; this.children.push(m); },
  contains(m) { return this.children.includes(m); },
  getBoundingClientRect() { return {top: 0}; },
};
function topOf(m) { let y = 0; for (const x of chat.children) { if (x === m) break; y += x.h; } return y; }
let nextHeight = 40;
const document = {
  getElementById() { return chat; },
  createElement() {
    const m = {h: nextHeight, className: '', innerHTML: ''};
    m.getBoundingClientRect = () => ({top: topOf(m) - chat.scrollTop});
    return m;
  },
};
function escapeHtml(s) { return s; } function renderMarkdown(s) { return s; }
function say(fn, h, ...args) { nextHeight = h; fn(...args); return chat.children[chat.children.length - 1]; }
"""


def _chat_js() -> str:
    js = _inline_script()
    return (CHAT_STUBS + _between(js, 'let readFrom = null;', 'function addSpinner(label)'))


def test_a_long_reply_is_shown_from_its_first_line():
    out = _node(_chat_js() + """
say(addUser, 60, 'Åtgärd');
const reply = say(addVoice, 1500, 'Långt svar', 'intake');
console.log(JSON.stringify({top: topOf(reply), scrollTop: chat.scrollTop}));
""")
    # 12 px of air above the label, and nothing of the reply above the fold
    assert out['scrollTop'] == out['top'] - 12


def test_a_short_reply_still_shows_everything_down_to_the_last_line():
    out = _node(_chat_js() + """
for (let i = 0; i < 12; i++) say(addSystem, 60, 'rad');
say(addUser, 60, 'Åtgärd');
say(addVoice, 120, 'Kort svar', 'intake');
console.log(JSON.stringify({scrollTop: chat.scrollTop, bottom: chat.scrollHeight - chat.clientHeight}));
""")
    assert out['scrollTop'] == out['bottom']


def test_what_follows_a_reply_does_not_push_its_first_line_away():
    out = _node(_chat_js() + """
say(addUser, 60, 'Åtgärd');
const first = say(addVoice, 300, 'Inledning', 'intake');
say(addVoice, 900, 'Följdfrågor', 'intake');
say(addSystem, 40, 'Profilen är klar');
console.log(JSON.stringify({top: topOf(first), scrollTop: chat.scrollTop}));
""")
    assert out['scrollTop'] == out['top'] - 12


def test_the_users_next_message_takes_the_chat_to_the_bottom_again():
    out = _node(_chat_js() + """
say(addUser, 60, 'Åtgärd');
say(addVoice, 1500, 'Långt svar', 'intake');
say(addUser, 60, 'Mitt svar');
const atBottom = chat.scrollTop === chat.scrollHeight - chat.clientHeight;
const next = say(addVoice, 1500, 'Nästa svar', 'intake');
console.log(JSON.stringify({atBottom, top: topOf(next), scrollTop: chat.scrollTop}));
""")
    assert out['atBottom'] is True
    assert out['scrollTop'] == out['top'] - 12


def test_a_cleared_chat_forgets_where_reading_started():
    out = _node(_chat_js() + """
say(addUser, 60, 'Åtgärd');
say(addVoice, 1500, 'Långt svar', 'intake');
chat.children = []; chat.scrollTop = 0;          // "Ny analys"
for (let i = 0; i < 12; i++) say(addSystem, 60, 'rad');
const atBottom = chat.scrollTop === chat.scrollHeight - chat.clientHeight;
const reply = say(addVoice, 1500, 'Nytt svar', 'intake');
console.log(JSON.stringify({atBottom, top: topOf(reply), scrollTop: chat.scrollTop}));
""")
    assert out['atBottom'] is True
    assert out['scrollTop'] == out['top'] - 12


def test_approving_a_step_lets_the_chat_follow_the_run_again():
    js = _inline_script()
    gate = _between(js, 'async function approveGate(phase)', 'const mark = state.history.length;')
    assert 'readFrom = null;' in gate
    assert gate.index('readFrom = null;') < gate.index('addSystem(gate.approved)')


# ---------- baslinje: the talk in the chat, the analysis in the panel ----------
# 2026-10-13: the baslinje panel opened with what the step does and a
# summary of EMAP, ended with gaps and "Frågor till miljöstrateg", and showed
# field names (A0, EF0_enhet) and numbers like 1,36e6. The talk now goes to
# the chat, the questions are put to "dig", and the panel reads as Swedish.
# The history keeps the text as the model wrote it: the next agents read it.

with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'baslinje.md'), encoding='utf-8') as _f:
    BASLINJE = _f.read()


def _helpers() -> str:
    js = _inline_script()
    return _between(js, 'function startsSentence(', '// The one place model text is sanitised') \
        + _between(js, 'function readableNumber(', 'function panelStepDone(')


def _parts(step: str, md: str) -> dict:
    return _node(_helpers() + f"""
const p = stepParts({json.dumps(step)}, {json.dumps(md)});
console.log(JSON.stringify(Object.assign(p, {{drawn: readablePanel(p.panel, {json.dumps(step)})}})));
""")


def test_the_baslinje_talk_goes_to_the_chat_and_the_analysis_stays_in_the_panel():
    p = _parts('baslinje', BASLINJE)
    for gone in ('Kort om detta steg', 'Underlag från EMAP', 'Dataluckor', 'Frågor till', 'Hur många tjänstebilar'):
        assert gone not in p['panel']
    for kept in ('Baslinje & BAU-analys för åtgärd', 'Nulägesbaslinje per drivare', 'BAU-scenario per drivare',
                 'Drivare 2: Laddinfrastruktur'):
        assert kept in p['panel']
    assert p['chat'].startswith('Utifrån EMAP-analysen sätter jag')
    assert 'EMAP-analysen identifierade två delåtgärder' in p['chat']
    assert '**Dataluckor**' in p['chat'] and 'Saknar uppgift om exakt antal tjänstebilar' in p['chat']
    assert '**Frågor till dig**' in p['chat'] and 'Hur många tjänstebilar' in p['chat']
    assert 'miljöstrateg' not in p['chat'] and '---' not in p['chat']
    # Said again after a re-run when they change: the gaps and questions only.
    assert p['followUp'].startswith('**Dataluckor**') and 'Utifrån EMAP' not in p['followUp']
    # No two rules in a row where the sections were taken out.
    lines = [line for line in p['panel'].split('\n') if line.strip()]
    assert not any(a.strip() == b.strip() == '---' for a, b in zip(lines, lines[1:]))


@pytest.mark.parametrize('md', [
    'Baslinje utan rubriker.\nA0: 3,0e6\nEF0: 0,13',
    # Only talk and no analysis: better the whole text in the panel than an empty one.
    '## Kort om detta steg\nJag gör så här.\n\n## Frågor till miljöstrateg\n- Vad?',
])
def test_a_baslinje_text_that_cannot_be_split_is_drawn_whole(md):
    p = _parts('baslinje', md)
    assert p['panel'] == md and p['chat'] == '' and p['followUp'] == ''


def test_other_steps_are_not_split():
    md = '## Kort om detta steg\nX\n\n## Analys\nY\nZ\n\n## Dataluckor för detta steg\n- W'
    for step in ('emap', 'kalkyl', 'qa'):
        assert _parts(step, md)['panel'] == md


@pytest.mark.parametrize('raw, drawn', [
    ('1,36e6 kg', '1,36 miljoner kg'),
    ('3,0e6 km/år', '3 miljoner km/år'),
    ('3,9e8', '390 miljoner'),
    ('1e9 kr', '1 miljard kr'),
    ('ca 6,2e6 kg/år (ca 6 200 ton).', 'ca 6,2 miljoner kg/år (ca 6 200 ton).'),
    ('1.25e4', '12 500'),
    ('2,5e-3 t', '0,0025 t'),
    # Not numbers in this form: names and units stay as they are.
    ('EF_el_SE_consumption_2030_BAU, kgCO2e/kWh, CO2e, Tier2', 'EF_el_SE_consumption_2030_BAU, kgCO2e/kWh, CO2e, Tier2'),
])
def test_numbers_in_e_notation_are_written_out(raw, drawn):
    out = _node(_helpers() + f'console.log(JSON.stringify({{s: readableNumbers({json.dumps(raw)})}}));')
    assert out['s'] == drawn


def test_the_baslinje_fields_are_named_in_swedish():
    p = _parts('baslinje', BASLINJE)
    drawn = p['drawn']
    for field in ('Nuläge_år:', 'A0:', 'A0_enhet', 'EF0:', 'EF0_enhet', 'Källor_nuläge', 'BAU_Tier',
                  'BAU_trend_A', 'BAU_trend_EF', 'BAU_årpunkter', 'Kommentar_BAU'):
        assert field not in drawn
    assert '**Aktivitet i dag:** 3 miljoner' in drawn
    assert '**Utsläpp per enhet i dag:** 0,13' in drawn
    assert '**Prognosmetod:** 2 (kända trender och beslutade styrmedel)' in drawn
    assert '**Prognosmetod:** 0 (nuläget hålls oförändrat)' in drawn
    assert '**Drivare 1: Körsträcka med icke-laddbara tjänstebilar i kommunens flotta**' in drawn
    # The history is not touched: the model's text is what the next agent reads.
    assert 'A0: 3,0e6' in BASLINJE and 'A0: 3,0e6' in p['panel']


def test_other_steps_ask_the_reader_not_a_job_title():
    p = _parts('qa', '## QA\nOk.\n\n## Frågor till miljöstrateg för detta steg\n- Stämmer det?\n\n'
                     'Fråga miljöstrategen om A0: 5.')
    assert '## Frågor till dig' in p['drawn'] and 'Frågor till miljöstrateg' not in p['drawn']
    # Only the heading is renamed, and the baslinje field names only in baslinje.
    assert 'Fråga miljöstrategen om A0: 5.' in p['drawn']


def _baslinje_program(post_step: str) -> str:
    js = _inline_script()
    dom = PANEL_DOM.replace("phase: 'emap'", "phase: 'baslinje'") \
        .replace("{role: 'assistant', content: 'EMAP VERSION 1'}", "{role: 'assistant', content: BASLINJE}") \
        .replace("const PANEL_STEPS = {emap: {num: 2, title: 'EMAP'}};",
                 "const PANEL_STEPS = {emap: {num: 2, title: 'EMAP'}, baslinje: {num: 3, title: 'Baslinje'}};") \
        .replace("const STEP_LABELS = {emap: 'EMAP'};", "const STEP_LABELS = {emap: 'EMAP', baslinje: 'Baslinjen'};")
    return f'const BASLINJE = {json.dumps(BASLINJE)};\n' + dom \
        + 'async function postStep(step, history) { ' + post_step + ' }\n' \
        + _between(js, 'function panelSection(step)', '// Hero + scenario range') \
        + _between(js, 'const BRIDGE = {', '// Draw one step') \
        + _between(js, '// Draw one step', '// Show an intermediate agent') \
        + _between(js, 'async function sendMessage()', '/* ---------- pipeline')


def test_a_baslinje_run_says_the_talk_in_the_chat():
    out = _node(_baslinje_program('return {ok: true, data: {output: BASLINJE}};') + """
(async () => {
  state.history = [{role: 'user', content: 'Åtgärd'}];
  const ok = await runStages(['baslinje']);
  console.log(JSON.stringify({ok, voiced, panel: panelSection('baslinje').dump(),
                              last: state.history[state.history.length - 1].content}));
})();
""")
    assert out['ok'] is True
    assert len(out['voiced']) == 1 and out['voiced'][0]['tag'] == 'baslinje'
    assert 'Frågor till dig' in out['voiced'][0]['md'] and 'Utifrån EMAP' in out['voiced'][0]['md']
    assert 'Nulägesbaslinje' in out['panel'] and 'Kort om detta steg' not in out['panel']
    assert out['last'] == BASLINJE


@pytest.mark.parametrize('new_question, said_again', [
    (False, False),
    (True, True),
])
def test_a_rerun_says_the_questions_again_only_when_they_changed(new_question, said_again):
    version = BASLINJE + ('\n- Finns det en ny fråga?\n' if new_question else '')
    out = _node(f'const VERSION_2 = {json.dumps(version)};\n' + _baslinje_program(
        "return {ok: true, data: {reply: 'Jag satte basåret till 2023.', output: VERSION_2}};") + """
(async () => {
  input.value = 'Varför 2023?';
  await sendMessage();
  console.log(JSON.stringify({voiced, said, last: state.history[state.history.length - 1].content}));
})();
""")
    assert len(out['voiced']) == 1
    md = out['voiced'][0]['md']
    assert md.startswith('Jag satte basåret till 2023.')
    assert ('Finns det en ny fråga?' in md) is said_again
    assert ('**Frågor till dig**' in md) is said_again
    assert 'Utifrån EMAP' not in md  # the introduction was said the first time
    assert out['last'] == version


def test_the_analysis_comes_back_to_the_panel_after_a_section_without_heading_syntax():
    md = ('Baslinje & BAU-analys för åtgärd: X\n\n## Underlag från EMAP\nTvå drivare.\n\n'
          '4) Nulägesbaslinje per drivare\nDrivare 1: Bilar\n  A0: 3,0e6\n  EF0: 0,13\n\n'
          '## Frågor till miljöstrateg\n- Hur många bilar?')
    p = _parts('baslinje', md)
    assert 'Drivare 1: Bilar' in p['panel'] and 'A0: 3,0e6' in p['panel']
    assert 'Drivare 1' not in p['chat'] and 'Två drivare.' in p['chat'] and 'Hur många bilar?' in p['chat']


def test_the_page_script_has_no_lookbehind():
    # Safari before 16.4 cannot parse one, and that stops the whole script.
    assert '(?<' not in _inline_script()


@pytest.mark.parametrize('value, shown', [(0.05, '5 %'), (1.0, '100 %'), (0, '0 %'), (0.075, '7,5 %'), (0.07, '7 %')])
def test_the_shares_of_the_effect_read_as_percent(value, shown):
    js = _between(_inline_script(), 'function evidenceDriverHtml(driver)', '\n}\n') + '\n}\n'
    out = _node('function escapeHtml(s) { return s; } function evidenceParamHtml() { return ""; }\n' + js
                + f"console.log(JSON.stringify({{h: evidenceDriverHtml({{number: 1, name: 'D', factors: {{territoriell: {value}}}}})}}));")
    assert '<div class="ev-factor-val">' + shown + '</div>' in out['h'].replace(' ', ' ')


# The code under the name is gone: it told a reader nothing (2026-10-13).
@pytest.mark.parametrize('name, detail, title', [
    ('ADOPTION_EXTRA_HANDLARE', 'antal aktiva handlare med cirkulärt erbjudande utöver BAU',
     'Antal aktiva handlare med cirkulärt erbjudande utöver BAU'),
    ('ANDEL_ERSATT_NYVARA', '', 'Andel ersatt nyvara'),
    ('Antal laddplatser', '', 'Antal laddplatser'),
])
def test_a_parameter_card_leads_with_what_the_parameter_is(name, detail, title):
    js = _between(_inline_script(), '// What a parameter is called on its card', 'function evidenceDriverHtml(driver)')
    out = _node('function escapeHtml(s) { return s; } function evidenceQualityChip() { return ""; }'
                ' function evidenceSpanHtml() { return ""; } const SOURCE_CHIP_MAXLEN = 40;\n' + js
                + f"console.log(JSON.stringify({{h: evidenceParamHtml({{name: {json.dumps(name)}, detail: {json.dumps(detail)},"
                  f" enhet: 'st', tidsaspekt: 'nivå 2030'}})}}));")
    assert '<span class="ev-param-name">' + title + '</span>' in out['h']
    assert 'ev-param-id' not in out['h'] and name not in out['h'].replace(title, '')
    # The description is the title now, so the line under it does not repeat it.
    assert '<div class="ev-param-unit">st · nivå 2030</div>' in out['h']


# ---------- EMAP as a view ----------
# 2026-10-13: the EMAP panel was the agent's text, "aktivitet_matt" and
# all, with no real headings. The page reads it into a view; the history
# keeps the text (the next agents read its field names).

def _emap(md: str) -> dict:
    return _node('function escapeHtml(s) { return s; } function capitalized(t) { return t ? t[0].toUpperCase() + t.slice(1) : t; }\n'
                 'function renderMarkdownWithChips(md) { return md; }\n' + _helpers() + f"""
const parts = stepParts('emap', {json.dumps(md)});
const v = parts.emap;
console.log(JSON.stringify({{view: v || null, chat: parts.chat, followUp: parts.followUp,
  html: v ? v.profiles.map(emapProfileHtml).join('') : null}}));
""")


def _fixture(name: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), 'fixtures', name), encoding='utf-8') as f:
        return f.read()


def test_the_emap_text_becomes_a_view_with_nothing_left_out():
    out = _emap(_fixture('emap.dev.md'))
    p, = out['view']['profiles']
    assert p['title'].startswith('Etablering av cirkulära verksamheter')
    assert [c['label'] for c in p['classes']] == ['Typ av åtgärd', 'Mekanism', 'Nivå', 'När effekten kommer',
                                                  'Mognad', 'Typ av effekt']
    assert p['classes'][2]['value'] == 'System/struktur'  # "Vald nivå (individ/hushåll, ...): System/struktur"
    assert all(c['why'] for c in p['classes'])
    assert [d['num'] for d in p['drivers']] == ['1', '2', '3']
    assert all(len(d['fields']) == 6 and not d['rest'] for d in p['drivers'])
    assert len(p['unsure']) == 3 and len(p['helps']) == 3 and p['extras'] == []
    html = out['html']
    for field in ('aktivitet_matt', 'EF_enhet', 'utsläppstyp', 'locus', 'overlapp_risk', 'EMAP_', '2.1'):
        assert field not in html
    assert 'Byta (Shift)' in html and 'Hög risk för dubbelräkning.' in html
    assert 'Har inga egna utsläpp' in html  # the enabler is not drawn as a sum
    # What would make the assessment surer is asked in the chat, not shown in the panel.
    assert 'Konkret plan för lokalstöd' in out['chat'] and 'Konkret plan för lokalstöd' not in html
    assert out['followUp'].startswith('**Underlag som skulle göra bedömningen säkrare**')


def test_an_older_emap_text_is_read_too_and_its_extra_note_kept():
    # A captured run in the older form: bold headings, "**Åtgärd 1: ...**", no drivers.
    out = _emap(_fixture('emap.md'))
    profiles = out['view']['profiles']
    assert len(profiles) == 2 and all(len(p['classes']) == 6 for p in profiles)
    assert profiles[1]['extras'][0]['title'].startswith('Notering om samband')
    assert 'funktionellt beroende' in out['html']


@pytest.mark.parametrize('md', ['EMAP VERSION 1', 'Något helt annat.\n\n- en punkt\n- en till'])
def test_an_emap_text_that_cannot_be_read_is_drawn_as_text(md):
    out = _emap(md)
    assert out['view'] is None and out['chat'] == ''


_EMAP_HEAD = ('EMAP-analys av åtgärd: Galleri\n\n1. Sammanfattning\nEtt galleri.\n\n2. EMAP-kategorisering\n\n'
              '2.1 EMAP_Åtgärdstyp\n- Vald kategori:\n**Teknisk åtgärd**\n- Kort motivering: För att 1.5\n'
              '1.5 gånger fler köper begagnat.\n\n2.2 EMAP_Mekanism (Avoid / Shift / Improve)\n- Vald kategori: Shift\n'
              '- Kort motivering: Byte.\n\n')


def test_numbered_items_in_the_uncertainties_stay_items():
    md = _EMAP_HEAD + ('3. Osäkerheter\n- Viktigaste osäkerheter i denna EMAP-bedömning:\n'
                       '    1. Osäkerheter kring tidsprofil är stora.\n    2. Underlaget för drivare saknas.\n'
                       '    3. Mognad oklar.\n- Vilken typ av underlag som skulle minska osäkerheten: Bättre data.\n\n'
                       '4. EMAP-drivare\nDrivare 1: Köp\n  aktivitet_matt: kg/år\n')
    p, = _emap(md)['view']['profiles']
    assert [c['label'] for c in p['classes']] == ['Typ av åtgärd', 'Mekanism']
    assert p['classes'][0]['value'] == 'Teknisk åtgärd'  # bold, on the line after
    assert len(p['classes'][0]['why']) == 2  # "1.5 gånger ..." is text, not a new class
    assert len(p['unsure']) == 3 and p['helps'] == ['Bättre data.'] and p['extras'] == []
    assert len(p['drivers']) == 1


def test_a_driver_without_its_section_heading_is_still_a_driver():
    md = _EMAP_HEAD + ('3. Osäkerheter\n- Viktigaste osäkerheter i denna EMAP-bedömning:\n  - Nivån.\n\n'
                       '4 EMAP-drivare\nDrivare 1: Km\n  aktivitet_matt: km/år\n')
    p, = _emap(md)['view']['profiles']
    assert [d['name'] for d in p['drivers']] == ['Km'] and p['drivers'][0]['fields']['aktivitet_matt'] == 'km/år'
    assert p['unsure'] == ['Nivån.']


def test_a_section_heading_without_a_number_is_a_heading():
    md = _EMAP_HEAD + '## Osäkerheter\n- Viktigaste osäkerheter:\n  - Nivån.\n\n## EMAP-drivare\nDrivare 1: Km\n'
    p, = _emap(md)['view']['profiles']
    assert p['unsure'] == ['Nivån.'] and len(p['drivers']) == 1 and p['extras'] == []


# ---------- the baslinje's sections are headings whatever form the model wrote ----------
#
# The prompt names the sections; the model writes them as "## X", "**X**" or
# a bare line. The bare form was drawn as prose, run together with the text
# under it, and the split that sends "Kort om detta steg" to the chat never
# found it (2026-10-14, the morning of the demo).

_SPLIT_STUBS = """
const readableNumbers = (s) => s;
const parseEmap = () => null;
"""


def _split_md(form: str) -> str:
    """The baslinje text in the three forms the model has written its
    section titles: a bare line, bold, or a markdown heading."""
    def t(title, numbered=''):
        if form == 'hash':
            return '## ' + title
        if form == 'bold':
            return '**' + title + '**'
        return numbered + title
    head = ('# ' if form == 'hash' else '') + 'Baslinje & BAU-analys för åtgärd: Boendeladdning'
    return '\n'.join([
        head, '',
        t('Kort om detta steg'),
        'Jag utgår från drivarna och sätter en nulägesbaslinje.',
        'Underlag från EMAP finns under nästa rubrik.', '',
        t('Underlag från EMAP'),
        'Profilen har 2 drivare: fossil körsträcka och elbilskörsträcka.', '',
        t('Nulägesbaslinje per drivare', '4) '), '',
        'Drivare 1: Fossil körsträcka, KBAB-hyresgäster',
        '  Nuläge_år: 2023', '  A0: 2,6e7', '  A0_enhet: km/år', '',
        t('BAU-scenario per drivare', '5) '), '',
        'Drivare 1: Fossil körsträcka, KBAB-hyresgäster', '  BAU_Tier: 2', '',
        t('Dataluckor för detta steg'),
        '- Ingen lokal data finns för KBAB:s bestånd.',
        '- Se avsnittet Dataluckor för detta steg i EMAP.', '',
        t('Frågor till miljöstrateg för detta steg'),
        '- Hur många bilar har hyresgästerna?', '',
    ])


def _split_program(tail: str) -> str:
    return _SPLIT_STUBS + _between(_inline_script(), 'function headingText', '// What the panel draws') + tail


@pytest.mark.parametrize('form', ['bare', 'bold', 'hash'])
def test_the_baslinje_sections_are_headings_whatever_form_the_model_wrote(form):
    md = _split_md(form)
    out = _node(_split_program('console.log(JSON.stringify(stepParts("baslinje", ' + json.dumps(md) + ')));'))
    chat, panel = out['chat'], out['panel']
    # The parts that talk to the person went to the chat, without their heading lines...
    assert 'Jag utgår från drivarna' in chat and 'Profilen har 2 drivare' in chat
    assert '**Frågor till dig**' in chat and 'Hur många bilar' in chat and 'Ingen lokal data' in chat
    # ...and a sentence that merely mentions a section is prose, not a heading.
    assert 'Underlag från EMAP finns under nästa rubrik.' in chat
    assert '- Se avsnittet Dataluckor för detta steg i EMAP.' in out['followUp']
    # The panel keeps the analysis under real headings, the same in every form.
    assert panel.startswith('# Baslinje & BAU-analys för åtgärd: Boendeladdning')
    assert '## Nulägesbaslinje per drivare' in panel and '## BAU-scenario per drivare' in panel
    assert panel.count('Drivare 1:') == 2
    assert 'Kort om detta steg' not in panel and 'Underlag från EMAP' not in panel
    assert '4) ' not in panel and '**Nulägesbaslinje' not in panel


def test_a_baslinje_already_written_with_headings_is_left_as_it_is():
    md = _split_md('hash')
    out = _node(_split_program(
        'console.log(JSON.stringify({same: baslinjeHeadings(' + json.dumps(md) + ') === ' + json.dumps(md) + '}));'))
    assert out['same'] is True
