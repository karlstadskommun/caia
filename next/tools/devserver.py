"""Local dev server with every model step stubbed, for UI work.

Serves the real app and the real parsers, but answers each step from canned
agent output (tests/fixtures/) so the page can be clicked through without
spending model calls. Intake asks one question, then returns a profile, then
a corrected one, which is what exercises the update path.

Run from next/:

    CAIA_KOMMUN=<profil> CAIA_DEV_OPEN=1 CAIA_INSECURE_COOKIE=1 python tools/devserver.py

and open http://127.0.0.1:5055. CAIA_STUB_DELAY=<seconds> slows every stub
down, to click "Ny analys" while a step is in flight.

CAIA_DEV_RUN=<directory> answers from one saved analysis instead: a package
directory written by tools/run_batch.py (intake.md, emap.md, baslinje.md,
evidens.md, kalkyl.md, kalkyl_meta.json, qa.md, rapport.md). A step the
directory has no file for falls back to tests/fixtures. That is how the
result view is read against a whole real run without a model call.
"""
from __future__ import annotations

import json
import os
import sys
import time

NEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TESTS = os.path.join(NEXT, 'tests')
sys.path.insert(0, os.path.join(NEXT, 'src'))
sys.path.insert(0, TESTS)

from caia.evidence import parse_evidence  # noqa: E402
from caia.profiles import parse_profiles  # noqa: E402
from caia.web import app as A  # noqa: E402

RUN = os.environ.get('CAIA_DEV_RUN') or ''


def _canned(*names: str) -> str | None:
    """The first of `names` that exists: in the saved run, then in tests/fixtures."""
    for folder in ([RUN] if RUN else []) + [os.path.join(TESTS, 'fixtures')]:
        for name in names:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
    return None


def _read(path: str) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()

FIRST = """ÅTGÄRDSPROFIL
*Namn:* Bilpool för kommunens anställda
*Beskrivning:* Kommunen ersätter egna tjänstebilar med en gemensam elbilspool för alla förvaltningar. Poolen omfattar 40 elbilar och ersätter cirka 120 tjänstebilar. Bokning sker digitalt och pooolen samlokaliseras med befintliga laddplatser.
*Sektor:* transporter
*Drivare:* antal tjänsteresor med bil per år
*Målgrupp:* kommunens egna anställda
*Utsläpp som påverkas:* territoriella utsläpp, kommunens egna utsläpp
*Rådighet:* direkt
*Typ av åtgärd:* organisation/styrning
*Tidsram:* 2026–2030 (ANTAGANDE: Tidsram 2026–2030 då inget annat angivits)
*Kommun:* Karlstads kommun (ANTAGANDE: Gäller Karlstads kommun)
*Kommentarer:* Ingen uppdelning gjord.
"""

SECOND = """Jag delade upp åtgärden i två, eftersom laddinfrastrukturen är ett eget beslut.

ÅTGÄRDSPROFIL 1
*Namn:* Bilpool för kommunens anställda
*Beskrivning:* Kommunen ersätter egna tjänstebilar med en gemensam elbilspool för alla förvaltningar. Poolen omfattar 60 elbilar och ersätter cirka 180 tjänstebilar.
*Sektor:* transporter
*Drivare:* antal tjänsteresor med bil per år
*Målgrupp:* kommunens egna anställda
*Utsläpp som påverkas:* territoriella utsläpp, kommunens egna utsläpp
*Rådighet:* direkt
*Typ av åtgärd:* organisation/styrning
*Tidsram:* 2027–2032
*Kommun:* Karlstads kommun
*Kommentarer:* Uppdaterad efter din rättelse: 60 bilar, start 2027.

ÅTGÄRDSPROFIL 2
*Namn:* Laddinfrastruktur vid kommunala arbetsplatser
*Beskrivning:* Utbyggnad av laddpunkter vid de arbetsplatser där poolbilarna står.
*Sektor:* energi
*Målgrupp:* kommunens egna verksamheter
*Utsläpp som påverkas:* territoriella utsläpp
*Rådighet:* direkt
*Typ av åtgärd:* infrastruktur
*Tidsram:* 2027–2029 (ANTAGANDE: följer bilpoolens utbyggnad)
*Kommun:* Karlstads kommun (ANTAGANDE: Gäller Karlstads kommun)
*Kommentarer:* Uppdelningen är gjord av mig.
"""

CLARIFY = 'Innan jag bygger profilen: hur många fordon rör det sig om, och när ska poolen vara i drift?'

calls = {'n': 0}


@A.app.route('/api/intake', methods=['POST'])
def stub_intake():  # noqa: D103 - overrides the real route below
    calls['n'] += 1
    n = calls['n']
    if n == 1:
        return A.jsonify({'status': 'clarifying', 'message': CLARIFY})
    text = FIRST if n == 2 else SECOND
    saved = RUN and os.path.join(RUN, 'intake.md')
    if saved and os.path.exists(saved):
        text = _read(saved)
    parsed = parse_profiles(text)
    return A.jsonify({
        'status': 'complete',
        'message': text,
        'profile_text': text,
        'profiles': parsed['profiles'],
        'preamble': parsed['preamble'],
    })


def stub_evidens():
    """Answer the evidens gate with a captured production run when there is one.

    Rendering against the real output matters more than against the template:
    the template is what was asked for, the fixture is what came back.
    """
    time.sleep(float(os.environ.get('CAIA_STUB_DELAY') or 0))
    fixture = _canned('evidens.md')
    if fixture:
        text = _read(fixture)
    else:
        from test_evidence import TEMPLATE  # noqa: PLC0415 - test-only helper
        text = TEMPLATE
    return A.jsonify({'output': text, 'evidence': parse_evidence(text)})


def stub_evidens_plan():
    """No drivers, so the page takes the single-call evidens path, which is
    stubbed above. Without this the page asked the real plan endpoint and
    then called the real model once per driver."""
    return A.jsonify({'drivers': []})


stage_calls = {}


def _stub_stage(name):
    """Answer a pipeline stage without calling a model.

    Serves the captured fixture when there is one, and counts calls so a
    re-run from a gate is visibly different from the first pass. That is what
    makes feedback at the EMAP and baslinje gates testable.
    """
    def view():
        # Real stages take 15-120s. The delay keeps a request in flight long
        # enough to click "Ny analys" underneath it, which is the race the
        # run token guards.
        time.sleep(float(os.environ.get('CAIA_STUB_DELAY') or 0))
        stage_calls[name] = stage_calls.get(name, 0) + 1
        run = stage_calls[name]

        # A hand-written sample in the current prompt format wins over a
        # captured run where the format has moved on since (emap.dev.md); a
        # saved run given in CAIA_DEV_RUN wins over both.
        fixture = (_canned(name + '.md') if RUN and os.path.exists(os.path.join(RUN, name + '.md'))
                   else _canned(name + '.dev.md', name + '.md'))
        if fixture:
            body = _read(fixture)
            # A saved report already carries Talens ursprung, which the page
            # appends itself from the kalkyl answer, as it does in production.
            if name == 'rapport' and A.KALLOR_RUBRIK in body:
                body = body[:body.index(A.KALLOR_RUBRIK)].rstrip() + '\n'
        else:
            body = '## ' + name + ' (stub)\n\nInget fixturunderlag för det här steget.'

        if run > 1:
            body = ('> Omkörd efter din feedback (körning ' + str(run) + ').\n\n') + body

        data = A.request.get_json(silent=True)
        if A._feedback(data):
            # The answer a framed re-run gives (caia/feedback.py), split by
            # the same code as the real route.
            body = ('[[SVAR]]\nStubbsvar på din kommentar: jag ändrade ingenting '
                    'på riktigt, men så här ser ett svar ut.\n[[/SVAR]]\n\n' + body)
        payload = A._gate_answer(body, A._feedback(data), A._history(data)) if name in ('emap', 'baslinje') \
            else {'output': body}
        # kalkyl carries the numbers the hero card renders from.
        meta = _canned(name + '_meta.json')
        if meta:
            payload.update(json.loads(_read(meta)))
        return A.jsonify(payload)
    view.__name__ = 'stub_' + name
    return view


if __name__ == '__main__':
    # Flask keeps the first registered view for a rule, so drop the real one.
    A.app.view_functions['api_intake'] = stub_intake
    A.app.view_functions['api_evidens'] = stub_evidens
    A.app.view_functions['api_evidens_plan'] = stub_evidens_plan
    for stage in ('emap', 'baslinje', 'kalkyl', 'qa', 'rapport'):
        A.app.view_functions['api_' + stage] = _stub_stage(stage)
    A.app.run(port=5055, debug=False)
