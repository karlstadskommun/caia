"""CAIA Web UI. Flask app with split chat/results layout."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import sys
import threading
import time
from datetime import timedelta
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import anthropic
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask.logging import default_handler, has_level_handler
from werkzeug.exceptions import HTTPException

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from caia import api_client, kommun, logsafe
from caia.agents.baslinje_bau import run_baslinje_bau
from caia.agents.cove_qa import run_cove_qa
from caia.agents.emap import run_emap
from caia.agents.evidens import run_evidens
from caia.agents.evidens_split import (
    EvidensSplitError,
    check_parts_cover,
    drivers_from_history,
    run_merge,
    run_part,
    split_part,
)
from caia.agents.intake import run_intake
from caia.agents.kalkyl import run_kalkyl
from caia.agents.kalkyl_extract import run_kalkyl_extract
from caia.agents.rapport import run_rapport
from caia.api_client import ConfigError, ModelOutputError
from caia.appendix import with_engine_appendix
from caia.calc import (CalcModel, activity_changes, compute, portfolj, render_activity,
                        render_appendix, render_markdown)
from caia.calc.engine import APPENDIX_HEADING, AVG_WINDOW, sanity_warnings, year_series
from caia.calc.portfolj import PortfoljError
from caia.calc.schema import plain
from caia.data.parameters import get_data_context, parameter_view, parse_file_register, parse_parameter_library
from caia.evidence import parse_evidence
from caia.feedback import frame_history, previous_version, split_reply
from caia.kallmarkering import KONTROLL_FEL as KALLOR_KONTROLL_FEL
from caia.kallmarkering import RUBRIK as KALLOR_RUBRIK
from caia.kallmarkering import SAKNAS as KALLOR_SAKNAS
from caia.kallmarkering import kallmarkering
from caia.mode import UPPFOLJNING, mode_of
from caia.pipeline import BRIDGE

app = Flask(__name__)

# Load the kommunprofil at boot, so a wrong or missing CAIA_KOMMUN stops the
# app with a message saying what is missing instead of failing in the middle
# of step 3. The line in the log says which municipality this instance is.
_k = kommun.active()
print(f"CAIA: kommunprofil {_k.slug} ({_k.namn}), {_k.root}", file=sys.stderr, flush=True)

# Where the software comes from. Deliberately not part of the kommunprofil: a
# another kommun's instance still runs code Karlstads kommun wrote, and says so. The
# kommunprofil test strips exactly this line before it checks that no
# Karlstad name reaches the page.
ORIGIN = ('Utvecklat av Karlstads kommun inom ramen för Klimatneutrala Karlstad 2030 '
          'som stöds av Viable Cities.')
# Shown next to ORIGIN on the start page; the licence is in LICENSE.
LICENSE_NOTE = 'Öppen källkod under EUPL 1.2.'


# The page's three libraries: the exact file and its hash (SRI). The page's
# script tags and its Content-Security-Policy are both written from this, so
# the policy lets in these files and no other path on the same host.
# clientlibs/package.json names the same versions for Dependabot, and a test
# holds the two together.
PAGE_LIBS = {
    'marked': ('https://cdn.jsdelivr.net/npm/marked@14.1.3/marked.min.js',
               'sha384-k8o8HikHweyzW55Wd3wl18ovJj6vHVYNQeQbeSM0fxx+0WiH4TcccOG9uz8Xd2JR'),
    'dompurify': ('https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js',
                  'sha384-P0JNneQf81HOl9VwNXK76cQ9VMD6Nfsnepxb0cCOg8+UzEdzgPHAPV4wVQrvYQSx'),
    '@supabase/supabase-js': (
        'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js',
        'sha384-0w2KAL2YHP6wKOkUDzkCDGgVvfmHnj02DHeQ6XcHOgTfFsGyonKOpShMH1x6nk9o'),
}


def _param_names() -> dict[str, str]:
    """Each parameter code in the library with the start of its description,
    so the page can say "andel resor (antal) med bil" where the model wrote
    TR_mode_share_car. The qualifiers go (what follows " - ", anything in
    parentheses), and a long description stops at its first " som ", " hos "
    or ", " past the opening words. {} if the library cannot be read: the page
    then shows the codes."""
    try:
        rows = [r for s in parse_parameter_library() for r in s['rows']]
    except Exception:  # noqa: BLE001 - a missing name must not fail the page
        app.logger.exception('Parameter names for the page could not be read')
        return {}
    # The data files are named the same way (DATA_MUNICIPAL_ORG); a name that
    # carries a year is also known without it, as the models write both.
    try:
        sources = [{'id': k, 'beskrivning': v.get('beskrivning')} for k, v in parse_file_register().items()]
        sources += [{'id': re.sub(r'_\d{4}$', '', s['id']), 'beskrivning': s['beskrivning']}
                    for s in sources if re.search(r'_\d{4}$', s['id'])]
    except Exception:  # noqa: BLE001 - as above
        app.logger.exception('Data source names for the page could not be read')
        sources = []
    names = {}
    for r in rows + sources:
        name = (r.get('beskrivning') or '').split(' - ')[0]
        name = re.sub(r'\s*\([^)]*\)', '', name).strip()
        name = re.sub(r'\bEF\b', 'utsläppsfaktor', name)
        if len(name) > 60:
            cut = re.search(r' som | hos |, ', name[25:])
            if cut:
                name = name[:25 + cut.start()]
        if r.get('id') and name:
            names[r['id']] = name
    return names


# render_template_string compiles its source on every call, and the page is
# 260 kB of template: 29 of the 33 ms a page view took. Each page is compiled
# once per process and rendered with the request's own context.
_compiled: dict = {}


def _render(source: str, **context) -> str:
    template = _compiled.get(source)
    if template is None:
        template = _compiled[source] = app.jinja_env.from_string(source)
    return render_template(template, **context)


def _page_context() -> dict:
    return {'kommun': kommun.active().public(), 'origin': ORIGIN,
            'param_names': _param_names(),
            'license_note': LICENSE_NOTE, 'avg_window': AVG_WINDOW, 'bridge': BRIDGE,
            'libs': PAGE_LIBS,
            # The lines that open a section the program writes into a report
            # (see sanitizedFragment in the page).
            'program_headings': [APPENDIX_HEADING, KALLOR_RUBRIK]}

CAIA_PASSWORD = os.environ.get('CAIA_PASSWORD', '')
# Explicit opt-in for running without any auth at all. Local dev only.
CAIA_DEV_OPEN = os.environ.get('CAIA_DEV_OPEN', '') == '1'
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip().rstrip('/')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '').strip()
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '').strip()
# Let Supabase's /auth/v1/user judge a token the app cannot check itself
# (security review S4). Off unless the project signs with something other
# than ES256 or HS256: with it on, a token claiming such an algorithm costs
# an outbound call, so it is only for a project that needs it.
CAIA_AUTH_FALLBACK = os.environ.get('CAIA_AUTH_FALLBACK', '') == '1'

# Session cookie signing key. A per-process random default silently breaks
# password-mode login across serverless instances: each cold start invalidates
# every session signed by another instance, which presents as a random login
# loop rather than an error. With Supabase JWT the Flask session carries no
# auth, so a random key there is harmless.
_secret = os.environ.get('CAIA_SECRET_KEY', '')
if not _secret:
    if CAIA_PASSWORD and not SUPABASE_URL:
        raise RuntimeError(
            "CAIA_SECRET_KEY must be set when CAIA_PASSWORD is used — a random "
            "per-instance key breaks login across serverless instances."
        )
    _secret = secrets.token_hex(32)
app.secret_key = _secret

# Password-mode session cookie. Secure by default: the password travels in it.
# CAIA_INSECURE_COOKIE=1 is for trying an install over plain http on a LAN,
# where a browser would otherwise drop the cookie and loop back to /login.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('CAIA_INSECURE_COOKIE', '') != '1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

def _is_secret_supabase_key(key: str) -> bool:
    """True for a key that must never reach a browser: a new-style secret key
    or a legacy JWT key whose role is service_role. Read unsigned; this only
    sorts the operator's own setting."""
    if key.startswith('sb_secret_'):
        return True
    try:
        payload = key.split('.')[1]
        role = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4))).get('role')
    except Exception:
        return False
    return role == 'service_role'


# The page hands SUPABASE_ANON_KEY to every visitor, signed in or not. With a
# secret key there, anyone could read and change everything in the project,
# so the app does not start (re-review 2026-10-07, L6).
if _is_secret_supabase_key(SUPABASE_ANON_KEY):
    raise RuntimeError(
        "SUPABASE_ANON_KEY är en hemlig nyckel (service_role eller sb_secret_). Sidan "
        "skickar den nyckeln till varje besökare. Sätt projektets publika nyckel "
        "(anon eller sb_publishable_) och byt ut den hemliga i Supabase.")
# The guide's own placeholder, and nothing else: a real key may hold a "<".
# A value that ends in "<...>" is the placeholder however much of the guide's
# line came along with it (the name, "export", quotes, which docker
# --env-file keeps): the app would start with a key that is printed in the
# guide (review of the fixes, 2026-10-08).
if re.search(r'<[^<>]*>[\s"\']*$', os.environ.get('CAIA_SECRET_KEY', '')):
    raise RuntimeError("CAIA_SECRET_KEY är guidens platshållare, inte en nyckel. "
                       "Skapa en med: python3 -c 'import secrets; print(secrets.token_hex(32))'")

# The settings that weaken the app say so at every start, so one left in a
# server's environment shows in its log (security review S13; the last two
# from the re-review, L6).
if CAIA_DEV_OPEN:
    print("CAIA: VARNING: CAIA_DEV_OPEN=1. Utan Supabase och lösenord släpps alla in "
          "utan inloggning. Bara för lokal utveckling.", file=sys.stderr, flush=True)
if not app.config['SESSION_COOKIE_SECURE']:
    print("CAIA: VARNING: CAIA_INSECURE_COOKIE=1. Inloggningskakan skickas även över "
          "okrypterad http. Bara för att prova på ett lokalt nät.", file=sys.stderr, flush=True)
if SUPABASE_URL.startswith('http://') and urlsplit(SUPABASE_URL).hostname not in ('localhost', '127.0.0.1'):
    print("CAIA: VARNING: SUPABASE_URL börjar med http://. Inloggningar och sparade "
          "rapporter går då okrypterat till Supabase.", file=sys.stderr, flush=True)
if CAIA_PASSWORD and not SUPABASE_URL and len(CAIA_PASSWORD) < 12:
    print("CAIA: VARNING: CAIA_PASSWORD är kortare än 12 tecken. Det är det enda som "
          "skyddar analyserna i lösenordsläge.", file=sys.stderr, flush=True)

# Request body cap. A whole analysis history (intake, EMAP, baslinje, evidens,
# kalkyl, QA) is well under 1 MB; the cap stops a client from making the app
# parse, and a model read, anything larger. Flask answers 413 above it.
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024


def _parse_allowlist(raw: str) -> set[str]:
    return {e.strip().lower() for e in raw.split(',') if e.strip()}


# Who may use the app in Supabase mode: full addresses and/or whole domains
# written as "@karlstad.se", comma separated; "*" lets every signed-in account
# in. The Supabase project decides who can create an account, not this code,
# and its anon key is public in the page, so /auth/v1/signup is reachable
# whatever the UI offers. Unset means nobody gets in: an open signup in front
# of Opus is a bill anyone can run up.
ALLOWED_EMAILS = _parse_allowlist(os.environ.get('CAIA_ALLOWED_EMAILS', ''))
if SUPABASE_URL and not ALLOWED_EMAILS:
    print("CAIA: CAIA_ALLOWED_EMAILS är inte satt, så ingen inloggad användare "
          "släpps in. Sätt adresser, domäner (@kommun.se) eller *.",
          file=sys.stderr, flush=True)


def email_is_allowed(claims: dict) -> bool:
    """Whether a verified token's account may use the app.

    A listed address gets in as it is. A listed domain lets in anyone with an
    address there, so the address has to be theirs: an account whose token
    says the address is unconfirmed is refused (security review S9). Only an
    explicit "no" counts, since older accounts carry no such claim.

    This is a second line, not the guard. The claim sits in user_metadata,
    which a signed-in user can edit, and a project that confirms addresses
    automatically marks every one confirmed. What keeps strangers out of a
    domain is that the Supabase project demands confirmation by email
    (DEPLOY.md and INSTALL.md say how to check it).

    The address is read strictly (re-review 2026-10-07, F8): it must be text
    with a name before the @, and only A to Z are lower-cased, as in the
    database's own check (deploy/reports.sql). Python's lower() turns the
    Kelvin sign into k, so "@\u212Aommun.se" would otherwise read as
    "@kommun.se". An address with blanks around it is refused, not trimmed:
    the database does not trim it, so the account could run an analysis here
    and not save it there (review of the fixes, 2026-10-08)."""
    if claims.get('is_anonymous'):
        return False
    if '*' in ALLOWED_EMAILS:
        return True
    raw = claims.get('email')
    if not isinstance(raw, str) or raw != raw.strip():
        return False
    email = ''.join(c.lower() if c.isascii() else c for c in raw)
    local, at, domain = email.rpartition('@')
    if not (at and local and domain):
        return False
    if email in ALLOWED_EMAILS:
        return True
    if '@' + domain not in ALLOWED_EMAILS:
        return False
    meta = claims.get('user_metadata')
    verified = meta.get('email_verified') if isinstance(meta, dict) else None
    if isinstance(verified, str):
        verified = verified.strip().lower() not in ('false', '0', 'no')
    return verified is None or bool(verified)


try:
    import jwt as pyjwt
    from jwt import PyJWKClient
except ImportError:
    pyjwt = None
    PyJWKClient = None
# Imported apart, so an older PyJWT without it cannot switch off all logins.
PyJWKClientError = getattr(pyjwt, 'PyJWKClientError', ())

_jwks_client = None
# The project's published keys by key id, each with when it was last read
# from the list: {kid: (key, read_at)}. PyJWKClient refetches the list every
# five minutes and keeps nothing when that fails, so these let a known key go
# on checking tokens through an outage. Only the project's own list lands
# here, and a key it drops goes. The dict is replaced whole and an entry is
# read in one step, so a request never sees half of an update.
_known: dict = {}
# Through an outage a key is trusted this long after it was read and no
# longer (re-review 2026-10-07, F6): an hour is how long a Supabase session
# token lives by default, so a token issued before the list was last fetched
# has run out by then, and a key the project has dropped since cannot go on
# checking tokens for as long as the instance lives. Counted on the wall
# clock, which goes on while a serverless instance is paused, and from the
# fetch itself (_KeyList), not from the last request the fetched list
# answered. A token issued in the five minutes after the fetch can so
# outlive the hour by as long, and is then told the login cannot be checked.
KNOWN_KEYS_TRUST_S = 3600
# How long a fetched list answers lookups before it is fetched again.
JWKS_CACHE_S = 300
# After a failed fetch the list is left alone this long.
JWKS_RETRY_S = 30
_jwks_down_until = 0.0
# One request at a time asks for the list (see _published_key). A request
# whose key is not known waits for that one this long and no longer: a fetch
# is capped at 5 s per network step, not as a whole, and without an end every
# request on the instance would wait behind one that hangs.
_jwks_lock = threading.Lock()
JWKS_WAIT_S = 10


class _KeyList(PyJWKClient or object):
    """PyJWKClient that knows, on the wall clock, when it last fetched the
    list (review of the fixes, 2026-10-08).

    PyJWKClient answers from its own copy for five minutes, counted on a
    clock that can stand still while a serverless instance is paused. A key's
    age was stamped at every lookup, so each answer from that copy made the
    keys look newly read: the hour could become an hour and five minutes,
    and after a pause the old copy answered as if no time had passed. Here
    the age is the fetch's, and a copy older than five minutes on the wall
    clock is fetched again."""
    fetched_at = 0.0

    def fetch_data(self):
        data = super().fetch_data()
        self.fetched_at = time.time()
        return data

    def get_jwk_set(self, refresh: bool = False):
        if time.time() - self.fetched_at > JWKS_CACHE_S:
            refresh = True
        return super().get_jwk_set(refresh)


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None and PyJWKClient and SUPABASE_URL:
        _jwks_client = _KeyList(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                                timeout=5, lifespan=JWKS_CACHE_S)
    return _jwks_client


def _remember_keys(jwks, kid=None, key=None) -> None:
    """Keep the list as just fetched (PyJWKClient's cache, no new request),
    so a key the project has dropped is not trusted in a later outage. Called
    after every good lookup: when the key asked for was found (kid, key), and
    when the list came back without it. The keys get the time the list was
    fetched, not the time of this lookup."""
    global _known
    read_at = getattr(jwks, 'fetched_at', None) or time.time()
    try:
        keys = {k.key_id: (k.key, read_at) for k in jwks.get_signing_keys() if k.key_id}
    except Exception:
        # The list could not be read back: the other keys keep the age they had.
        keys = dict(_known)
    if isinstance(kid, str) and key is not None:
        keys[kid] = (key, read_at)
    elif isinstance(kid, str):
        keys.pop(kid, None)
    _known = keys


def _known_key(kid):
    """The key with this id, if this instance read it from the project's
    list within the last hour."""
    key, read_at = _known.get(kid, (None, 0.0))
    # Not from the future either: a clock set back would keep the key trusted
    # until it caught up.
    return key if 0 <= time.time() - read_at < KNOWN_KEYS_TRUST_S else None


def _published_key(kid: str):
    """The project's signing key with this id, as (key, None). (None, detail)
    when the list was read and holds no such key. (None, None) when the list
    cannot be read right now.

    One request at a time asks for the list. While it does, a token whose key
    was read within the hour is checked with that key and does not wait; any
    other waits for the answer, at most JWKS_WAIT_S, and past that the list
    counts as unreadable for this request. Before the review of
    the re-review's fixes each request made its own failing fetch, one after
    the other, so a burst of made-up tokens during an outage kept every
    thread waiting for most of a minute."""
    global _jwks_down_until
    if time.monotonic() < _jwks_down_until:
        return None, None
    known = _known_key(kid)
    if known is not None:
        if not _jwks_lock.acquire(blocking=False):
            return known, None
    elif not _jwks_lock.acquire(timeout=JWKS_WAIT_S):
        return None, None
    try:
        if time.monotonic() < _jwks_down_until:
            return None, None  # the request before this one found it down
        jwks = _get_jwks_client()
        try:
            # By key id: get_signing_key_from_jwt would decode the token
            # again, and a garbled one must not look like a failed fetch.
            key = jwks.get_signing_key(kid).key
        except Exception as e:
            if type(e) is PyJWKClientError and 'Unable to find a signing key' in str(e):
                # A key id the project does not publish. PyJWKClient
                # refetches once on an unknown id, so a rotated key is found
                # without this, and the list it just fetched is the one to
                # remember: without this key.
                _remember_keys(jwks, kid)
                return None, str(e)
            _jwks_down_until = time.monotonic() + JWKS_RETRY_S
            app.logger.warning("Key list could not be fetched, next try in %ss: %r",
                               JWKS_RETRY_S, str(e))
            return None, None
        _remember_keys(jwks, kid, key)
        return key, None
    finally:
        _jwks_lock.release()


class AuthUnavailable(RuntimeError):
    """The token could not be checked right now, which is not the same as a
    token found wrong: the page says so instead of "not signed in"."""


def _hashed_ip() -> str:
    """The caller's address, hashed, for the log: enough to see that the same
    address keeps coming back, not who it is."""
    return hmac.new(app.secret_key.encode(), _client_ip().encode(),
                    hashlib.sha256).hexdigest()[:12]


def _refused(reason: str, detail=None) -> None:
    """Log a token that was not accepted (security review S5) and refuse it.
    Never the token itself; the detail is PyJWT's message or the algorithm."""
    app.logger.warning("Refused token from ip %s: %s%s", _hashed_ip(), reason,
                       f" ({str(detail)[:200]!r})" if detail is not None else '')
    return None


# Every token must carry an expiry and a subject (security review S12): one
# without exp would never run out.
_REQUIRED_CLAIMS = ['exp', 'sub']


def _decoded(token: str, key, alg: str) -> dict | None:
    try:
        payload = pyjwt.decode(token, key, algorithms=[alg], audience='authenticated',
                               options={'require': _REQUIRED_CLAIMS})
    except Exception as e:
        return _refused(f'{alg} validation failed', str(e))
    if not isinstance(payload.get('sub'), str) or not payload['sub']:
        return _refused('empty sub')
    return payload


def _ask_supabase(token: str) -> dict | None:
    """Supabase's own judgement of a token, for a project the app cannot
    check locally (CAIA_AUTH_FALLBACK=1). The token's issuer, audience and
    expiry are checked first, unsigned, so only a token that at least claims
    to be this project's live session costs the call."""
    try:
        pyjwt.decode(token, options={'verify_signature': False, 'verify_exp': True,
                                     'verify_aud': True, 'verify_iss': True,
                                     'require': _REQUIRED_CLAIMS + ['iss', 'aud']},
                     audience='authenticated', issuer=f'{SUPABASE_URL}/auth/v1')
    except Exception as e:
        return _refused('not this project\'s session', str(e))
    try:
        resp = urlopen(
            Request(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {token}'},
            ),
            timeout=5,
        )
        user = json.loads(resp.read().decode())
    except Exception as e:
        return _refused('Supabase /auth/v1/user said no', str(e))
    if not user.get('id'):
        return _refused('Supabase /auth/v1/user gave no user')
    return {'sub': user['id'], 'email': user.get('email'),
            'is_anonymous': user.get('is_anonymous', False),
            'user_metadata': user.get('user_metadata') or {}}


def get_user_claims() -> dict | None:
    """Verify the Supabase JWT in the Authorization header; return its claims.

    ES256 against the project's published keys (JWKS) is what Supabase signs
    with: a real login on 2026-10-07 gave alg ES256 with a key id, and the
    JWKS held that one EC key. HS256 with SUPABASE_JWT_SECRET is for a project
    still on the legacy shared secret. Both require aud "authenticated", an
    expiry and a subject, and the claims carry the `email` and
    `user_metadata` the allowlist reads.

    Anything else is refused here: a string that is not a JWT, a signature,
    expiry or audience found wrong, an algorithm the app does not check. Only
    with CAIA_AUTH_FALLBACK=1 does such a token go on to Supabase, and then
    only after the checks in _ask_supabase, so a made-up token cannot make
    every request cost an outbound call of up to 5 s (security review S4).

    When the key list cannot be fetched, a key this instance read from it
    within the last hour still checks the token here. Any other token cannot
    be checked: AuthUnavailable, a 503 that says so. Before the re-review of
    2026-10-07 (F5) such a token went on to Supabase, so during an outage
    anyone could make every request cost that call."""
    if not pyjwt or not SUPABASE_URL:
        return None
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None  # not logged: every visit before login looks like this
    token = auth_header[7:]
    if len(token) > 8192 or token.count('.') != 2:
        return _refused('not a JWT')
    try:
        header = pyjwt.get_unverified_header(token)
    except Exception:
        return _refused('unreadable header')
    alg = header.get('alg') if isinstance(header, dict) else None

    if alg == 'ES256':
        kid = header.get('kid')
        if not isinstance(kid, str) or not kid:
            if not CAIA_AUTH_FALLBACK:
                return _refused('ES256 without a key id')
            return _ask_supabase(token)
        key, missing = _published_key(kid)
        if key is not None:
            return _decoded(token, key, 'ES256')
        if missing is not None:
            if not CAIA_AUTH_FALLBACK:
                return _refused('ES256 key lookup failed', missing)
            return _ask_supabase(token)
        # The key list is down. A key read from it within the last hour
        # still checks the token here. A made-up token cannot bring this
        # about: it takes a failed fetch, or another request's fetch that
        # has gone on for longer than JWKS_WAIT_S.
        key = _known_key(kid)
        if key is not None:
            return _decoded(token, key, 'ES256')
        if CAIA_AUTH_FALLBACK:
            return _ask_supabase(token)
        app.logger.warning("Token from ip %s not checked: the key list is down and "
                           "its key is not one read from it in the last hour", _hashed_ip())
        raise AuthUnavailable()
    elif alg == 'HS256' and SUPABASE_JWT_SECRET:
        return _decoded(token, SUPABASE_JWT_SECRET, 'HS256')
    elif not CAIA_AUTH_FALLBACK:
        return _refused('algorithm the app does not check', alg)
    return _ask_supabase(token)


def get_user_from_token():
    """The user id (sub) of a valid token, or None."""
    claims = get_user_claims()
    return claims.get('sub') if claims else None


class SupabaseError(RuntimeError):
    """A Supabase call failed. Message is safe to show a user. `status` is
    the HTTP status when Supabase answered with one."""
    status: int | None = None


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ''


def content_security_policy(supabase_url: str) -> str:
    """What the page may load: its own inline script and style (the page is
    one template), marked, DOMPurify and supabase-js from jsDelivr (pinned
    with SRI), Roboto from Google Fonts, and calls to itself and to the
    Supabase project. Nothing else: no media, objects, frames or other
    hosts, so an element that slips past the sanitiser has nowhere to send
    anything (security review S2). 'unsafe-inline' is for the inline script
    and onclick handlers; what keeps model text from running is DOMPurify,
    and the policy is no second line against a script that does get in.

    The libraries are named file by file. With the whole host allowed, a
    script tag could load anything anyone has published on jsDelivr
    (re-review 2026-10-07)."""
    connect = "'self'"
    libs = [url for name, (url, _) in PAGE_LIBS.items()
            if _origin(supabase_url) or name != '@supabase/supabase-js']
    if _origin(supabase_url):
        connect += ' ' + _origin(supabase_url)
    return '; '.join([
        "default-src 'none'",
        "script-src 'self' 'unsafe-inline' " + ' '.join(libs),
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self'",
        f"connect-src {connect}",
        "media-src 'none'",
        "object-src 'none'",
        "frame-src 'none'",
        "worker-src 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
    ])


CSP = content_security_policy(SUPABASE_URL)


@app.after_request
def _security_headers(resp):
    """Headers every answer carries, errors included."""
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Content-Security-Policy', CSP)
    # API answers carry analyses and saved reports; no browser or proxy
    # cache should keep a copy.
    if request.path.startswith('/api/'):
        resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.errorhandler(AuthUnavailable)
def _handle_auth_unavailable(exc):
    resp = jsonify({'error': 'Inloggningen kan inte kontrolleras just nu. '
                             'Försök igen om en stund.'})
    resp.status_code = 503
    resp.headers['Retry-After'] = str(JWKS_RETRY_S)
    return resp


@app.errorhandler(SupabaseError)
def _handle_supabase_error(exc):
    """Answer JSON, not Flask's HTML 500 page.

    Registered centrally rather than try/except'd per endpoint so a report
    endpoint added later cannot reintroduce the HTML-500 that the frontend
    parses as JSON and reports as an unhelpful "Sparfel".
    """
    return jsonify({'error': str(exc)}), 502


def _path_only(path: str) -> str:
    """The table, without a filter that may hold a value."""
    return str(path).split('?', 1)[0][:80]


def _postgrest_code(e: HTTPError) -> str:
    try:
        code = json.loads(e.read().decode(errors='replace')).get('code')
    except Exception:  # noqa: BLE001 - an unreadable body is logged as no code
        return ''
    return f" ({code})" if isinstance(code, str) and re.fullmatch(r'[A-Z0-9]{1,10}', code) else ''


def supabase_request(method, path, data=None, token=None, params=None):
    """Call the Supabase REST API (PostgREST). Token = user JWT for RLS scoping."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += '?' + urlencode(params)
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode() if data is not None else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            resp_data = resp.read().decode()
            return json.loads(resp_data) if resp_data else None
    except HTTPError as e:
        # The response body can carry column names, constraint text and row
        # contents: a saved report's own text in a failed write (security
        # review S31). Neither the client nor the log gets it, only
        # PostgREST's error code ("23514", "PGRST301"), which says which rule
        # was hit.
        app.logger.error("Supabase %s %s failed: %s%s", method, _path_only(path), e.code,
                         _postgrest_code(e))
        failure = SupabaseError(f"Supabase svarade {e.code}.")
        failure.status = e.code
        raise failure from e
    except (URLError, TimeoutError, OSError) as e:
        app.logger.error("Supabase %s %s unreachable: %s", method, _path_only(path), e)
        raise SupabaseError("Kunde inte nå Supabase.") from e


# Who a refused account should write to. Optional: without it the message
# still says what is missing, only not to whom.
CONTACT = os.environ.get('CAIA_CONTACT', '').strip()
NOT_ALLOWED = ('Kontot saknar behörighet till CAIA. Be den som driftar CAIA '
               'lägga till din adress' + (f' ({CONTACT}).' if CONTACT else '.'))
NOT_SAVED = ('Analysen kunde inte sparas: databasen släpper inte in kontot. Den som '
             'driftar CAIA behöver lägga adressen eller domänen i databasens lista '
             '(caia.allowed).')


def _supabase_user():
    """(user_id, None) for an allowed caller, else (None, error response)."""
    claims = get_user_claims()
    if not claims:
        return None, (jsonify({'error': 'Ej inloggad'}), 401)
    if not email_is_allowed(claims):
        # The user id and the domain, not the whole address (S5).
        app.logger.warning("Refused account %s (domain %r): not on CAIA_ALLOWED_EMAILS, "
                           "anonymous, or an unconfirmed address",
                           claims.get('sub'),
                           str(claims.get('email') or '').rpartition('@')[2][:100])
        return None, (jsonify({'error': NOT_ALLOWED}), 403)
    return claims['sub'], None


def _password_tag() -> str:
    """Stored in the session at login and compared on every request, so a
    changed CAIA_PASSWORD logs every existing session out."""
    return hmac.new(app.secret_key.encode(), CAIA_PASSWORD.encode(),
                    hashlib.sha256).hexdigest()[:32]


def _password_session_ok() -> bool:
    tag = session.get('pw')
    return isinstance(tag, str) and hmac.compare_digest(tag, _password_tag())


def require_auth(f):
    """Supabase-JWT auth when configured; else CAIA_PASSWORD session; else
    refuse, unless CAIA_DEV_OPEN=1 says this is a local dev run.

    Without that last gate, a deploy that lost both SUPABASE_URL and
    CAIA_PASSWORD turns into an open proxy to Opus that anyone can bill."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if SUPABASE_URL:
            user_id, refused = _supabase_user()
            if refused:
                return refused
            request.user_id = user_id
            return f(*args, **kwargs)
        if not CAIA_PASSWORD:
            if CAIA_DEV_OPEN:
                return f(*args, **kwargs)
            return jsonify({'error': 'Autentisering är inte konfigurerad'}), 503
        if _password_session_ok():
            return f(*args, **kwargs)
        # Every protected route is under /api and answers JSON: a redirect to
        # the HTML login page would reach fetch() as a page it cannot parse.
        return jsonify({'error': 'Ej inloggad. Ladda om sidan och logga in igen.'}), 401
    return decorated


def require_supabase_auth(f):
    """Like require_auth but only Supabase JWT (for report CRUD)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not SUPABASE_URL:
            return jsonify({'error': 'Supabase ej konfigurerat'}), 501
        user_id, refused = _supabase_user()
        if refused:
            return refused
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


# Calls per caller to the routes that reach a model. A full analysis is 9-16
# calls (more with many drivers, each driver's evidens is its own call), so
# the day cap is about ten analyses. In process, like AIda's: on Vercel every
# warm instance counts for itself, so this caps one client looping a route,
# not a determined abuser spread over instances. The hard stop on spend is
# the monthly limit on the OpenRouter key (see docs/RUNBOOK.md).
def _count_setting(name: str, default: int) -> int:
    """A positive whole number from the environment. Empty means the default:
    an env file copied from .env.example, or a blank variable in Vercel, has
    the line with no value, and int('') stopped the app at boot."""
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} ska vara ett heltal, inte {raw!r}.") from None
    if value < 1:
        raise RuntimeError(f"{name} ska vara minst 1, inte {value}.")
    return value


RATE_LIMIT_PER_MIN = _count_setting('CAIA_RATE_LIMIT_PER_MIN', 20)
RATE_LIMIT_PER_DAY = _count_setting('CAIA_RATE_LIMIT_PER_DAY', 150)
# Proxies in front of the app that append to X-Forwarded-For (security
# review S8). One: nginx on an own server, Vercel's edge in production.
TRUSTED_PROXIES = _count_setting('CAIA_TRUSTED_PROXIES', 1)
_rate_hits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
# Flask's logger passes warnings and up unless told otherwise; the line per
# model call below is information.
app.logger.setLevel(logging.INFO)
# The usage line per model call (tokens, seconds, estimated USD) comes from
# api_client, outside Flask's logger. Same level, and Flask's handler unless
# the runtime already gave the logging tree one, as Flask itself decides.
_usage_log = logging.getLogger('caia.api_client')
_usage_log.setLevel(logging.INFO)
if not has_level_handler(_usage_log):
    _usage_log.addHandler(default_handler)


def _client_ip() -> str:
    """The address the outermost trusted proxy saw. nginx
    ($proxy_add_x_forwarded_for, INSTALL.md) appends it last to whatever the
    client sent; the entries before it are the client's own words, so reading
    the first one let a client pick a new address per request and walk past
    both throttles. Vercel overwrites the header with the client's address,
    so the last entry is the only one there.

    With CAIA_TRUSTED_PROXIES proxies in front (default one), each appends
    one entry, so the client is that many from the end. A header with fewer
    entries did not pass all of them; then the nearest proxy's address
    counts, which throttles harder rather than trusting the client."""
    hops = [h.strip() for h in request.headers.get('X-Forwarded-For', '').split(',')]
    if len(hops) >= TRUSTED_PROXIES and hops[-TRUSTED_PROXIES]:
        return hops[-TRUSTED_PROXIES]
    return request.remote_addr or 'unknown'


def _check_rate_limit(key: str, per_min: int, per_day: int,
                      hits_by_key: dict[str, list[float]] | None = None) -> int | None:
    """Sliding window. Seconds to wait, or None if this call may go ahead
    (and is then counted)."""
    table = _rate_hits if hits_by_key is None else hits_by_key
    now = time.monotonic()
    with _rate_lock:
        # Pruned before the checks, so a burst that only ever hits a limit
        # still keeps the table bounded.
        if len(table) > 1000:
            for k in [k for k, v in table.items() if not v or now - v[-1] > 86400]:
                del table[k]
        hits = [t for t in table.get(key, []) if now - t < 86400]
        recent = [t for t in hits if now - t < 60]
        if len(recent) >= per_min:
            table[key] = hits
            return max(1, int(60 - (now - recent[0])))
        if len(hits) >= per_day:
            table[key] = hits
            return max(1, int(86400 - (now - hits[0])))
        hits.append(now)
        table[key] = hits
    return None


def _log_rate_limit(uid) -> None:
    app.logger.warning("Rate limit hit on %r by %s", request.path,
                       f"user {uid}" if uid else f"ip {_hashed_ip()}")


def rate_limited(f):
    """Cap calls to a route that spends money on model tokens. Goes inside
    @require_auth so it counts per signed-in user where there is one."""
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = getattr(request, 'user_id', None)
        key = f"u:{uid}" if uid else f"ip:{_client_ip()}"
        retry_after = _check_rate_limit(key, RATE_LIMIT_PER_MIN, RATE_LIMIT_PER_DAY)
        if retry_after is not None:
            _log_rate_limit(uid)
            resp = jsonify({'error': 'För många anrop. Vänta en stund och försök igen.'})
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry_after)
            return resp
        # Who spent the money (re-review 2026-10-07, M1): the user id, which
        # the operator can look up in Supabase, never the address.
        app.logger.info("Model call %s by %s", request.path,
                        f"user {uid}" if uid else f"ip {_hashed_ip()}")
        return f(*args, **kwargs)
    decorated.rate_limited = True
    return decorated


# Saving, listing and opening reports costs no model tokens but does reach
# Supabase and, on save, reads up to 300 000 characters (security review S3).
# Its own count, so a page that lists reports often never eats into the
# budget for analyses; a real session saves a report or two and lists a few
# times. The other routes that reach no model count here too (re-review
# 2026-10-07, F4): the evidens plan, which parses a whole history, and the
# parameter list. A session calls each a handful of times.
REPORT_RATE_PER_MIN = 30
REPORT_RATE_PER_DAY = 600
_report_hits: dict[str, list[float]] = {}


def report_rate_limited(f):
    """Cap calls to the routes that reach no model. Inside the auth
    decorator, so it counts per signed-in user where there is one."""
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = getattr(request, 'user_id', None)
        key = f"u:{uid}" if uid else f"ip:{_client_ip()}"
        retry_after = _check_rate_limit(key, REPORT_RATE_PER_MIN, REPORT_RATE_PER_DAY,
                                        _report_hits)
        if retry_after is not None:
            _log_rate_limit(uid)
            resp = jsonify({'error': 'För många anrop. Vänta en stund och försök igen.'})
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry_after)
            return resp
        return f(*args, **kwargs)
    decorated.rate_limited = True
    return decorated


# Wrong passwords per client IP before /login stops checking for a while.
# A room behind one conference IP shares the count, so a workshop on the
# shared password raises it: five typos would lock every group out.
LOGIN_FAILURES_PER_WINDOW = _count_setting('CAIA_LOGIN_FAILURES_PER_WINDOW', 5)
LOGIN_WINDOW_S = 600
_login_failures: dict[str, list[float]] = {}


def _login_blocked(ip: str) -> bool:
    now = time.monotonic()
    with _rate_lock:
        recent = [t for t in _login_failures.get(ip, []) if now - t < LOGIN_WINDOW_S]
        # Only addresses with a failure inside the window keep an entry, so
        # the table cannot grow by one for every address that asks.
        if recent:
            _login_failures[ip] = recent
        else:
            _login_failures.pop(ip, None)
        return len(recent) >= LOGIN_FAILURES_PER_WINDOW


def _login_failed(ip: str) -> None:
    now = time.monotonic()
    with _rate_lock:
        _login_failures.setdefault(ip, []).append(now)
        if len(_login_failures) > 1000:
            for k in [k for k, v in _login_failures.items() if now - v[-1] >= LOGIN_WINDOW_S]:
                del _login_failures[k]


class RequestError(ValueError):
    """The request body is not what the route takes. Message is for the user."""


@app.errorhandler(RequestError)
def _handle_request_error(exc):
    return jsonify({'error': str(exc)}), 400


@app.errorhandler(HTTPException)
def _handle_http_error(exc):
    """JSON for /api, so fetch() gets something it can show. A 413 from
    MAX_CONTENT_LENGTH, a 405 or a 404 used to arrive as an HTML page."""
    if not request.path.startswith('/api/'):
        return exc
    return jsonify({'error': exc.description or exc.name}), exc.code


@app.errorhandler(Exception)
def _handle_unexpected(exc):
    """An error no endpoint caught. Flask's own log line carries its message,
    which can quote the analysis (security review S31); this one has the type
    and where."""
    # repr: a %0A in the path would otherwise start a log line of its own.
    _log_failure(f'{request.method} {request.path!r} failed', exc)
    if not request.path.startswith('/api/'):
        return 'Något gick fel på servern.', 500
    return jsonify({'error': 'Något gick fel på servern. Försök igen.'}), 500


# A history holds at most this many turns: intake questions and answers, one
# answer per step, one approval per gate, and feedback rounds. Real runs stay
# under 40.
MAX_HISTORY_TURNS = 120

# How much text a history may carry (security review S6). The rate limit
# counts calls, and each call could carry 2 MB, so one account could spend
# many analyses' worth of tokens. Measured 2026-10-07 on the 33 complete
# analyses on disk from the October test runs: the largest history was
# 171 398 characters over 14 turns (median 89 535), the longest single turn
# 41 288. Both caps are a little over twice that, room for a few feedback
# rounds on a long analysis.
MAX_HISTORY_CHARS = 400_000
# One turn. The total above is what bounds the tokens a call can carry; this
# one keeps a single paste from being the whole of it. It was 100 000 until
# 2026-11-10, which the server's own kalkyl text passed: the engine's appendix
# has a row per driver, scenario and year, so twelve drivers to 2045 gave
# 112 000 characters and the next step refused the history ("Tur 11 är för
# lång"). 200 000 holds twelve drivers to the middle of the 2060s; a kalkyl
# longer than that is refused where it is made (see api_kalkyl).
MAX_TURN_CHARS = 200_000
# The evidens parts sent to the merge, together and each (see
# api_evidens_merge). They are model input outside the history's total, so
# they keep their own cap.
MAX_PARTS_CHARS = 100_000


def _history(data) -> list[dict]:
    """The request's `history`, checked: a list of {role, content} turns where
    role is user or assistant and content is text. Everything downstream
    (the agents, the driver parser) assumes that shape. The turns are built
    anew from those two fields: the list goes to the model provider as it
    is, and a client's other keys (cache_control, megabytes of anything)
    would otherwise ride along outside every size limit."""
    if not isinstance(data, dict):
        raise RequestError('Förfrågan ska vara ett JSON-objekt.')
    history = data.get('history', [])
    if not isinstance(history, list):
        raise RequestError('history ska vara en lista.')
    if len(history) > MAX_HISTORY_TURNS:
        raise RequestError(f'Historiken har {len(history)} turer; högst {MAX_HISTORY_TURNS}.')
    for i, turn in enumerate(history):
        if not (isinstance(turn, dict) and turn.get('role') in ('user', 'assistant')
                and isinstance(turn.get('content'), str)):
            raise RequestError(f'Tur {i} i historiken ska vara {{role: user|assistant, '
                               'content: text}.')
        if len(turn['content']) > MAX_TURN_CHARS:
            raise RequestError(f'Tur {i} i historiken är för lång (högst {MAX_TURN_CHARS} tecken).')
    total = sum(len(turn['content']) for turn in history)
    if total > MAX_HISTORY_CHARS:
        raise RequestError(f'Analysen har blivit för lång ({total} tecken, högst '
                           f'{MAX_HISTORY_CHARS}). Börja om med en kortare beskrivning.')
    return [{'role': turn['role'], 'content': turn['content']} for turn in history]


def _mode(data) -> str:
    """The request's analysis mode (caia.mode). Missing means potential."""
    try:
        return mode_of(data.get('mode') if isinstance(data, dict) else None)
    except ValueError as e:
        raise RequestError(str(e)) from None


def _log_failure(msg: str, exc: BaseException) -> None:
    """The failure's type and where it happened, not its message, which can
    quote the analysis (security review S31: caia.logsafe)."""
    logsafe.log_failure(app.logger, msg, exc)


def _step_error(exc: Exception):
    """The answer for a step that failed. Says what the user or the operator
    can act on; the traceback goes to the log, not to the browser.

    `retryable` marks the failures that came back fast and can pass: the
    provider busy (429), unreachable, or answering 5xx. The page retries only
    those. A timeout already took minutes and a new try is a new paid call
    that will likely wait as long; an answer that did not parse, or an error
    of our own, would fail the same way again."""
    if isinstance(exc, ModelOutputError):
        return jsonify({'error': str(exc)}), 502
    if isinstance(exc, anthropic.AuthenticationError):
        msg = ('Språkmodelltjänsten (OpenRouter) godtog inte nyckeln. Den som driftar '
               'CAIA behöver kontrollera OPENROUTER_API_KEY.')
    elif isinstance(exc, anthropic.APIStatusError) and exc.status_code == 402:
        msg = ('OpenRouter-kontot har slut på krediter eller har nått sin gräns. Den som '
               'driftar CAIA behöver fylla på eller höja gränsen.')
    elif isinstance(exc, anthropic.RateLimitError):
        msg = 'Språkmodelltjänsten tar inte emot fler anrop just nu. Vänta en minut och kör steget igen.'
    elif isinstance(exc, anthropic.APITimeoutError):
        msg = 'Modellen svarade inte i tid. Kör steget igen.'
    elif isinstance(exc, anthropic.APIConnectionError):
        msg = 'Kunde inte nå språkmodelltjänsten. Kör steget igen om en stund.'
    elif isinstance(exc, anthropic.APIStatusError):
        msg = (f'Språkmodelltjänsten svarade med fel {exc.status_code}. '
               'Kör steget igen om en stund.')
    elif isinstance(exc, kommun.KommunProfilError):
        # The message names files on the server; it goes to the log only
        # (security review S11).
        ref = secrets.token_hex(4)
        app.logger.error("kommunprofil error [%s] on %s: %s", ref, request.path, exc)
        return jsonify({'error': f'Kommunprofilen går inte att läsa (fel-id {ref}). Ge '
                                 'fel-id:t till den som driftar CAIA.'}), 500
    elif isinstance(exc, ConfigError):
        msg = str(exc)
    else:
        ref = secrets.token_hex(4)
        _log_failure(f"step failed [{ref}] on {request.path}", exc)
        return jsonify({'error': f'Steget misslyckades (fel-id {ref}). Kör det igen; '
                                 'återkommer felet, ge fel-id:t till den som driftar CAIA.'}), 500
    _log_failure(f"step failed on {request.path}", exc)
    retryable = (isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError))
                 and not isinstance(exc, anthropic.APITimeoutError)) or (
        isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500)
    return jsonify({'error': msg, 'retryable': True} if retryable else {'error': msg}), 502


LOGIN_TEMPLATE = r"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CAIA | Logga in</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root { --kk-gold: #FFCC01; --kk-dark-red: #B5201F; --kk-charcoal: #444; --kk-warm-bg: #FFFBF5; --kk-gray-200: #e5e5e5; --kk-gray-400: #a3a3a3; --kk-gold-light: #FFF1B6; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Roboto', sans-serif; height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--kk-warm-bg); }
.login-box { background: white; border-radius: 12px; padding: 40px; width: 360px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); border-top: 3px solid var(--kk-gold-light); }
.login-box h1 { font-size: 24px; color: var(--kk-charcoal); margin-bottom: 8px; }
.login-box p { font-size: 13px; color: var(--kk-gray-400); margin-bottom: 24px; }
.login-box input { width: 100%; padding: 12px 16px; border: 1px solid var(--kk-gray-200); border-radius: 8px; font-size: 14px; font-family: inherit; outline: none; }
.login-box input:focus { border-color: var(--kk-dark-red); box-shadow: 0 0 0 2px rgba(181,32,31,0.15); }
.login-box button { width: 100%; padding: 12px; background: var(--kk-charcoal); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 12px; font-family: inherit; }
.login-box button:hover { background: var(--kk-dark-red); }
.error { color: var(--kk-dark-red); font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<div class="login-box">
  <h1>CAIA</h1>
  <p>Climate Action Impact Analysis</p>
  <form method="POST">
    <input type="password" name="password" placeholder="L&#xF6;senord" autofocus>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <button type="submit">Logga in</button>
  </form>
</div>
</body>
</html>"""


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CAIA | Klimatanalys</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
{# Pinned to exact versions with SRI. `marked` was fully unpinned, so a
   compromised or simply changed CDN build got to parse LLM-authored markdown
   with DOMPurify loaded from the same origin — i.e. the sanitiser and the
   thing it sanitises had the same single point of failure. Hashes are sha384
   of these exact URLs; bumping a version means recomputing them, otherwise
   the browser refuses the script and the page dies loudly (which is the
   intended failure mode). #}
<script src="{{ libs['marked'][0] }}"
        integrity="{{ libs['marked'][1] }}"
        crossorigin="anonymous"></script>
<script src="{{ libs['dompurify'][0] }}"
        integrity="{{ libs['dompurify'][1] }}"
        crossorigin="anonymous"></script>
{% if has_supabase %}<script src="{{ libs['@supabase/supabase-js'][0] }}"
        integrity="{{ libs['@supabase/supabase-js'][1] }}"
        crossorigin="anonymous"></script>{% endif %}
<style>
:root {
  --kk-charcoal: #444;
  --kk-charcoal-text: #2f2e2c;
  --kk-gray-50:  #fafaf9;
  --kk-gray-100: #f4f3f1;
  --kk-gray-200: #e6e4e0;
  --kk-gray-300: #cfccc7;
  --kk-gray-400: #999;
  --kk-gray-500: #6a6864;
  --kk-gray-600: #555350;
  --kk-orange:      #E84E0D;
  --kk-orange-soft: #FDE7DC;
  --kk-orange-pale: #FEF4EF;
  --kk-gold:     #FFCC01;
  --kk-red:      #B5201F;
  --kk-cream:    #FFFAE8;
  --kk-cream-text: #6F5A00;
  --kk-green:    #4a7c59;
  --kk-bg:       #FAF9F6;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  height: 100vh; display: flex; flex-direction: column;
  background: var(--kk-bg); color: var(--kk-charcoal-text);
  font-size: 14px; line-height: 1.55;
}

/* Auth overlay */
#authOverlay { position: fixed; inset: 0; background: var(--kk-bg); display: none; align-items: center; justify-content: center; z-index: 100; }
.login-box { background: white; border-radius: 12px; padding: 40px; width: 370px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); border-top: 3px solid var(--kk-orange); }
.login-box h1 { font-size: 26px; color: var(--kk-charcoal); margin-bottom: 6px; }
.login-box p { font-size: 13px; color: var(--kk-gray-400); margin-bottom: 22px; }
.login-box input { width: 100%; padding: 12px 16px; border: 1px solid var(--kk-gray-200); border-radius: 8px; font-size: 14px; font-family: inherit; outline: none; margin-bottom: 10px; }
.login-box input:focus { border-color: var(--kk-orange); box-shadow: 0 0 0 3px rgba(232,78,13,0.13); }
.login-box button { width: 100%; padding: 12px; background: var(--kk-orange); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 6px; font-family: inherit; }
.login-box button:hover { background: #cf4309; }
.login-box button:disabled { background: var(--kk-gray-400); cursor: not-allowed; }
.login-box .error { color: var(--kk-red); font-size: 12px; margin: 4px 0 8px; }
.login-box .error.info { color: var(--kk-charcoal); }
.login-box .auth-hint { font-size: 12px; line-height: 1.45; color: var(--kk-gray-500); margin: 0 0 8px; }
.login-box .auth-link { color: var(--kk-gray-500); font-size: 12.5px; }
.login-box #authResend { display: block; margin: 0 0 6px; color: var(--kk-orange); }

/* Topbar */
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background: white; border-bottom: 1px solid var(--kk-gray-200); flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 12px; }
.topbar-logo { font-size: 22px; font-weight: 500; letter-spacing: -0.3px; color: var(--kk-charcoal); display: flex; align-items: center; gap: 8px; }
.topbar-logo::before { content: ''; width: 9px; height: 9px; border-radius: 50%; background: var(--kk-orange); display: inline-block; }
.topbar-sep { width: 1px; height: 22px; background: var(--kk-gray-200); }
.topbar-sub { font-size: 13px; color: var(--kk-gray-500); letter-spacing: 0.3px; white-space: nowrap; }
.topbar-right { display: flex; align-items: center; gap: 10px; position: relative; }
.btn-pill { background: none; border: 1px solid var(--kk-gray-200); border-radius: 100px; padding: 6px 14px; font-size: 11.5px; font-weight: 500; color: var(--kk-gray-500); cursor: pointer; font-family: inherit; transition: all 0.15s; }
.btn-pill:hover { background: var(--kk-orange-pale); border-color: var(--kk-orange); color: var(--kk-orange); }
.user-email { font-size: 11.5px; color: var(--kk-gray-400); }
.saved-menu { position: absolute; top: 38px; right: 0; background: white; border: 1px solid var(--kk-gray-200); border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); min-width: 280px; max-height: 360px; overflow-y: auto; z-index: 50; display: none; }
.saved-menu-header { font-size: 10.5px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--kk-gray-400); padding: 12px 14px 6px; }
.saved-item { padding: 9px 14px; border-top: 1px solid var(--kk-gray-100); cursor: pointer; font-size: 13px; }
.saved-item:hover { background: var(--kk-orange-pale); }
.saved-item .si-name { color: var(--kk-charcoal); font-weight: 500; }
.saved-item .si-meta { font-size: 11px; color: var(--kk-gray-400); margin-top: 2px; }
.saved-empty { padding: 12px 14px; font-size: 12.5px; color: var(--kk-gray-400); }

/* Pipeline progress, with the analysis mode at the row's right end. The steps
   scroll inside their own box when the row gets narrow, so the mode never
   leaves the screen; on a phone the mode takes a row of its own under them. */
.progress-bar { display: flex; align-items: center; gap: 16px; padding: 10px 24px; background: white; border-bottom: 1px solid var(--kk-gray-200); flex-shrink: 0; }
.progress-steps { display: flex; align-items: center; gap: 3px; flex: 1 1 auto; min-width: 0; overflow-x: auto; scrollbar-width: thin; }
.progress-step { display: flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 100px; font-size: 11px; font-weight: 500; white-space: nowrap; color: var(--kk-gray-400); background: var(--kk-gray-100); transition: all 0.3s; }
.progress-step.active { color: var(--kk-orange); background: var(--kk-orange-pale); box-shadow: inset 0 0 0 1px var(--kk-orange-soft); }
.progress-step.done { color: var(--kk-green); background: #eef5f0; }
.progress-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--kk-gray-400); flex-shrink: 0; }
.progress-step.active .progress-dot { background: var(--kk-orange); }
.progress-step.done .progress-dot { background: var(--kk-green); }
.progress-arrow { color: var(--kk-gray-300); font-size: 13px; margin: 0 1px; flex-shrink: 0; }

/* Main layout */
.main { display: flex; flex: 1; overflow: hidden; }
.chat-panel { width: 40%; display: flex; flex-direction: column; border-right: 1px solid var(--kk-gray-200); background: white; }
.results-panel { width: 60%; display: flex; flex-direction: column; background: var(--kk-bg); overflow-y: auto; padding: 28px; }

/* Chat */
.chat-messages { flex: 1; overflow-y: auto; padding: 18px 18px 8px; display: flex; flex-direction: column; gap: 16px; }
.msg-user { align-self: flex-end; max-width: 88%; background: var(--kk-charcoal); color: white; padding: 10px 14px; border-radius: 10px 10px 3px 10px; font-size: 14px; line-height: 1.5; word-wrap: break-word; }
.voice-aida { position: relative; align-self: stretch; padding: 2px 0 2px 16px; }
.voice-aida::before { content: ''; position: absolute; left: 0; top: 4px; bottom: 4px; width: 3px; border-radius: 2px; background: var(--kk-orange); }
.voice-label { font-size: 10.5px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--kk-orange); margin-bottom: 5px; display: flex; align-items: center; gap: 5px; }
.voice-label::before { content: ''; width: 5px; height: 5px; border-radius: 50%; background: var(--kk-orange); }
.voice-label .agent { color: var(--kk-gray-400); font-weight: 600; letter-spacing: 1px; }
.voice-body { font-size: 14px; color: var(--kk-charcoal); line-height: 1.55; }
.voice-body p { margin: 4px 0; }
.voice-body strong, .voice-body b { font-weight: 600; }
.voice-body ul, .voice-body ol { margin: 6px 0 2px 18px; }
.voice-body li { padding: 1px 0; }
.msg-system { align-self: center; font-size: 11.5px; color: var(--kk-gray-500); letter-spacing: 0.2px; display: flex; align-items: center; gap: 6px; background: var(--kk-cream); padding: 5px 12px; border-radius: 100px; }
.msg-system .check { color: var(--kk-green); font-weight: 700; }
.msg-system.err { background: #fdecea; color: var(--kk-red); }

/* Spinner */
.spinner-container { display: flex; align-items: center; gap: 10px; padding: 4px 0 4px 16px; }
.spinner { width: 16px; height: 16px; border: 2px solid var(--kk-gray-200); border-top-color: var(--kk-orange); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinner-label { font-size: 13px; color: var(--kk-gray-500); }

/* Chat input */
.chat-input-area { padding: 14px 16px; border-top: 1px solid var(--kk-gray-200); display: flex; gap: 8px; background: white; }
.chat-input-area textarea { flex: 1; padding: 11px 14px; border: 1px solid var(--kk-gray-200); border-radius: 8px; font-size: 14px; font-family: inherit; resize: none; outline: none; color: var(--kk-charcoal); min-height: 44px; max-height: 120px; }
.chat-input-area textarea::placeholder { color: var(--kk-gray-400); }
.chat-input-area textarea:focus { border-color: var(--kk-orange); box-shadow: 0 0 0 3px rgba(232,78,13,0.13); }
/* Analysis mode: "Välj analystyp:" and a segmented control, right-aligned on
   the step row, chosen before the first message. Text only: the two names say
   what the analysis is, so nothing needs explaining next to them. The bordered
   track and the label keep the two segments apart from the step pills. Once
   the analysis starts the label reads "Analystyp:" and only the chosen segment
   stays, naming the running mode. */
.mode-switch { display: flex; align-items: center; gap: 8px; margin: 0 0 0 auto; padding: 0; border: 0; min-width: 0; flex-shrink: 0; }
.mode-switch legend { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.mode-label { font-size: 11.5px; color: var(--kk-gray-500); white-space: nowrap; }
.mode-seg { display: inline-flex; gap: 2px; padding: 2px; border: 1px solid var(--kk-gray-200); border-radius: 100px; }
.mode-switch label { cursor: pointer; }
.mode-switch input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.mode-pill { display: inline-block; padding: 4px 12px; border-radius: 100px; font-size: 11.5px; font-weight: 500; line-height: 1.3; color: var(--kk-gray-500); white-space: nowrap; transition: background 0.15s, color 0.15s; }
.mode-switch label:hover input:not(:checked) + .mode-pill { color: var(--kk-charcoal); }
.mode-switch input:checked + .mode-pill { background: var(--kk-orange-pale); color: var(--kk-orange); box-shadow: inset 0 0 0 1px var(--kk-orange-soft); }
.mode-switch input:focus-visible + .mode-pill { box-shadow: 0 0 0 3px rgba(232,78,13,0.25); }
.mode-switch:disabled label { cursor: default; }
.mode-switch:disabled .mode-seg { border-color: transparent; }  /* same height locked, so the row does not jump */
.mode-switch:disabled input:not(:checked) + .mode-pill { display: none; }
@media (prefers-reduced-motion: reduce) { .mode-pill { transition: none; } }
.btn-send { padding: 10px 20px; background: var(--kk-orange); color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit; white-space: nowrap; }
.btn-send:hover { background: #cf4309; }
.btn-send:disabled { background: var(--kk-gray-400); cursor: not-allowed; }

/* Approve */
.approve-area { padding: 12px 16px; border-top: 1px solid var(--kk-gray-200); background: var(--kk-cream); text-align: center; }
.btn-approve { padding: 10px 24px; background: var(--kk-green); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: inherit; }
.btn-approve:hover { background: #3d6a4a; }

/* Results panel */
.results-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--kk-gray-400); text-align: center; padding: 40px; }
.results-empty h2 { font-size: 22px; font-weight: 500; margin-bottom: 8px; color: var(--kk-charcoal); }
.results-empty p { font-size: 13px; max-width: 360px; }
.start-notes { list-style: none; margin: 22px 0 0; padding: 0; max-width: 440px; text-align: left; display: flex; flex-direction: column; gap: 10px; }
.start-notes li { font-size: 12.5px; line-height: 1.5; color: var(--kk-gray-500); background: white; border: 1px solid var(--kk-gray-200); border-left: 3px solid var(--kk-orange); border-radius: 8px; padding: 10px 14px; }
.start-notes b { color: var(--kk-charcoal); font-weight: 600; }
.report-actions { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 16px; }
.btn-save { background: var(--kk-charcoal); color: white; border: none; padding: 7px 14px; font-size: 12px; font-weight: 500; border-radius: 6px; cursor: pointer; font-family: inherit; }
.btn-save.secondary { background: white; color: var(--kk-charcoal); border: 1px solid var(--kk-gray-300); }
.print-attribution { display: none; }
/* Print, and "Spara som PDF" in the same dialog: the number, the chart and the
   report on white paper, without the chat, the buttons or the step trail. */
@media print {
  @page { margin: 16mm 14mm; }
  html, body { height: auto; display: block; background: white; }
  #appContainer { display: block !important; overflow: visible !important; }
  .topbar, .progress-bar, .chat-panel, .report-actions, .trail-toggle, #analysisFeed,
  .modal-overlay, #authOverlay, .results-empty, .saved-menu, .recalc, .qa-warn details { display: none !important; }
  .main { display: block; overflow: visible; }
  .results-panel { width: 100%; overflow: visible; padding: 0; background: white; }
  .card, .report-container { border: none; box-shadow: none; }
  .report-container { padding: 0; }
  .hero-chart, .card, .report-container table, .report-container pre { break-inside: avoid; }
  .report-container h1, .report-container h2, .report-container h3 { break-after: avoid; }
  .card, .card-strip, .chart-svg, .hero-value { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .chart-line.draw { animation: none; }
  .print-attribution { display: block; margin-top: 20px; padding-top: 8px; border-top: 1px solid var(--kk-gray-300); font-size: 10.5px; line-height: 1.5; color: var(--kk-gray-600); }
  .print-attribution hr { display: none; }
}
.btn-save:hover { background: var(--kk-charcoal-text); }
#saveIndicator { font-size: 11.5px; color: var(--kk-gray-400); align-self: center; margin-right: auto; }

/* Hero card */
.card { background: white; border: 1px solid var(--kk-gray-200); border-radius: 6px; overflow: hidden; margin-bottom: 20px; }
.card-strip { height: 4px; background: linear-gradient(90deg, var(--kk-gold), var(--kk-orange)); }
.hero { text-align: center; padding: 24px 26px; }
.hero-label { font-size: 10.5px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--kk-gray-500); margin-bottom: 10px; }
.hero-value { font-size: 44px; font-weight: 500; color: var(--kk-orange); line-height: 1; letter-spacing: -1px; }
.hero-value span { font-size: 17px; font-weight: 400; color: var(--kk-gray-500); letter-spacing: 0; }
.hero-sub { font-size: 12.5px; color: var(--kk-gray-500); margin-top: 10px; display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; }
.hero-warn { margin-top: 10px; font-size: 12.5px; line-height: 1.45; color: var(--kk-red); }
/* The report's short interpretation of the number, under it. Prose is set
   left in the centred card: five centred sentences are hard to read. */
.hero-interp { margin: 14px auto 0; max-width: 64ch; text-align: left; font-size: 14px; line-height: 1.55; color: var(--kk-charcoal); }
.hero-interp p { margin: 0; }
.hero-interp p + p { margin-top: 6px; }
/* The button sits centred under the warning it answers, like everything else
   in the card, with what it does in a line under it (2026-10-14: a
   left-set button beside its note read as misplaced). */
.recalc { margin-top: 12px; display: flex; flex-direction: column; align-items: center; gap: 7px; }
.recalc button { font: inherit; font-size: 13px; font-weight: 600; color: white; background: var(--kk-orange);
  border: 0; border-radius: 100px; padding: 7px 16px; cursor: pointer; }
.recalc button:hover { background: var(--kk-red); }
.recalc button:focus-visible { outline: 2px solid var(--kk-charcoal-text); outline-offset: 2px; }
.recalc button:disabled { opacity: .5; cursor: default; }
.recalc span { font-size: 12px; color: var(--kk-gray-600); }
/* QA's warning: one line and "Läs mer", in the same cream and red rule as the
   QA step's own summary so the two read as one thing. Set left in the centred
   card, like the interpretation above. */
.qa-warn { margin: 12px auto 0; max-width: 62ch; padding: 10px 14px 10px 13px; text-align: left;
  background: var(--kk-cream); border-left: 3px solid var(--kk-red); border-radius: 0 6px 6px 0;
  font-size: 13px; line-height: 1.5; color: var(--kk-charcoal-text); }
.qa-warn > p { margin: 0; }
.qa-warn-head { font-weight: 600; color: var(--kk-red); }
.qa-warn details { margin-top: 4px; }
.qa-warn summary { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; list-style: none;
  font-weight: 600; text-decoration: underline; text-underline-offset: 2px; }
.qa-warn summary::-webkit-details-marker { display: none; }
.qa-warn summary::after { content: ''; width: 5px; height: 5px; border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor; transform: translateY(-2px) rotate(45deg); transition: transform .15s; }
.qa-warn details[open] summary::after { transform: translateY(1px) rotate(-135deg); }
.qa-warn summary:focus-visible, .qa-open-step:focus-visible { outline: 2px solid var(--kk-charcoal-text); outline-offset: 2px; border-radius: 2px; }
.qa-warn .when-open, .qa-warn details[open] .when-closed { display: none; }
.qa-warn details[open] .when-open { display: inline; }
.qa-more > p { margin: 10px 0 2px; font-weight: 600; }
.qa-more ul { margin: 0; padding-left: 18px; }
.qa-more li { margin: 3px 0; }
.qa-more > p.qa-recalc-why { font-weight: 400; color: var(--kk-gray-600); }
.qa-open-step { font: inherit; font-weight: 600; color: var(--kk-red); background: none; border: 0; padding: 0;
  margin-top: 10px; cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { .qa-warn summary::after { transition: none; } }
.hero-sub b { color: var(--kk-charcoal); font-weight: 600; }

/* Report markdown body */
.report-container { background: white; border: 1px solid var(--kk-gray-200); border-radius: 6px; padding: 28px 32px; }
.report-container h1, .report-container h2, .report-container h3 { color: var(--kk-charcoal); margin: 20px 0 8px; line-height: 1.3; }
.report-container h1 { font-size: 22px; }
.report-container h2 { font-size: 18px; border-bottom: 2px solid var(--kk-orange-soft); padding-bottom: 6px; }
.report-container h3 { font-size: 15px; }
.report-container p { margin: 6px 0; line-height: 1.6; font-size: 14px; }
.report-container ul, .report-container ol { margin: 6px 0 6px 24px; font-size: 14px; }
.report-container li { margin: 3px 0; line-height: 1.5; }
.report-container table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
.report-container th, .report-container td { border: 1px solid var(--kk-gray-200); padding: 8px 12px; text-align: left; }
.report-container th { background: var(--kk-gray-50); font-weight: 600; }
.report-container pre { background: var(--kk-gray-100); padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 12px; margin: 12px 0; }
.report-container code { font-size: 12px; background: var(--kk-gray-100); padding: 2px 4px; border-radius: 3px; }
.report-container pre code { background: none; padding: 0; }
.report-container strong { font-weight: 600; }

/* The report as parts (2026-10-15, after the workshop 14/10): the
   title, the number and the report's own verdict are read first, and each
   part of the report is a row that opens with one click, with a line saying
   what is in it. The rows are the report's own sections, in its own order. */
.report-title { font-size: 21px; font-weight: 600; line-height: 1.3; color: var(--kk-charcoal-text); margin: 0 2px -4px; }
.report-container.structured { background: none; border: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.report-pre { background: white; border: 1px solid var(--kk-gray-200); border-radius: 6px; padding: 12px 20px; }
.report-verdict { background: white; border: 1px solid var(--kk-gray-200); border-radius: 6px; padding: 16px 22px; }
.report-verdict .section-eyebrow { margin-bottom: 8px; }
.report-container .verdict-text p { font-size: 15px; line-height: 1.6; margin: 0; color: var(--kk-charcoal-text); }
.report-container .verdict-text p + p { margin-top: 8px; }
.verdict-status { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 24px; margin: 14px 0 0; padding-top: 12px;
  border-top: 1px solid var(--kk-gray-100); font-size: 13px; }
.verdict-status > dl { display: flex; gap: 6px; align-items: baseline; margin: 0; }
.verdict-status dt { color: var(--kk-gray-500); }
.verdict-status dd { margin: 0; font-weight: 600; color: var(--kk-charcoal-text); }
.verdict-status .warn dd { color: var(--kk-red); }
.verdict-check { font: inherit; font-weight: 600; color: var(--kk-red); background: none; border: 0; padding: 0; cursor: pointer;
  text-decoration: underline; text-underline-offset: 2px; }
.parts-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 6px 2px -6px; }
.parts-toggle { font: inherit; font-size: 12px; font-weight: 600; color: var(--kk-gray-500); background: none; border: 0; padding: 2px 0; cursor: pointer; }
.parts-toggle:hover { color: var(--kk-orange); }
.report-parts { background: white; border: 1px solid var(--kk-gray-200); border-radius: 6px; }
.part + .part { border-top: 1px solid var(--kk-gray-200); }
.part > summary { list-style: none; cursor: pointer; display: grid; grid-template-columns: 10px 1fr; column-gap: 14px; padding: 14px 20px; }
.part > summary::-webkit-details-marker { display: none; }
.part-caret { grid-row: 1 / span 2; margin-top: 6px; width: 7px; height: 7px; border-right: 1.75px solid var(--kk-gray-400);
  border-bottom: 1.75px solid var(--kk-gray-400); transform: rotate(-45deg); transition: transform .15s; }
.part[open] > summary .part-caret { transform: translate(1px, -1px) rotate(45deg); border-color: var(--kk-orange); }
.part-title { font-size: 15px; font-weight: 600; line-height: 1.35; color: var(--kk-charcoal-text); }
.part-teaser { display: block; font-size: 13px; line-height: 1.45; color: var(--kk-gray-500); margin-top: 2px; }
.part-teaser.warn { color: var(--kk-red); }
.part[open] > summary .part-teaser { display: none; }
.part > summary:hover .part-title { color: var(--kk-orange); }
.part > summary:focus-visible, .parts-toggle:focus-visible, .verdict-check:focus-visible { outline: 2px solid var(--kk-charcoal-text); outline-offset: 2px; border-radius: 2px; }
.part-body { padding: 0 22px 18px 44px; }
.part-body > :first-child { margin-top: 0; }
/* A wide table (Talens ursprung has five columns) scrolls on its own instead
   of pushing the page wider than the screen. */
.table-scroll { overflow-x: auto; margin: 12px 0; }
.report-container .table-scroll table { margin: 0; }
@media (prefers-reduced-motion: reduce) { .part-caret { transition: none; } }
@media (max-width: 768px) {
  .report-title { font-size: 18px; }
  .report-verdict { padding: 14px 16px; }
  .part > summary { padding: 13px 14px; column-gap: 12px; }
  .part-body { padding: 0 14px 16px; }
  .report-container .table-scroll table { min-width: 560px; }
}
@media print {
  .report-title { margin-bottom: 12px; }
  .parts-toggle, .part-teaser, .part-caret, .verdict-check { display: none !important; }
  .report-pre, .report-verdict, .report-parts { border: none; padding-left: 0; padding-right: 0; }
  .part + .part { border-top: none; }
  .part > summary { display: block; padding: 18px 0 6px; }
  .part-body { padding: 0; }
  .table-scroll { overflow: visible; }
}
/* Its own rule: a browser that does not know the pseudo-element drops only
   this. It prints a closed part whole even if beforeprint never comes. */
@media print { .part::details-content { content-visibility: visible; display: block; } }

/* Analysis card — right panel builds live, step by step (åtgärdskort) */
.analysis-card { display: flex; flex-direction: column; gap: 16px; }
.section-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: var(--kk-gray-400); }

/* Hero scenario range */
.scenario { margin-top: 16px; padding: 0 4px; }
.scenario-track { position: relative; height: 5px; border-radius: 3px; background: linear-gradient(90deg, var(--kk-gray-200), var(--kk-orange-soft) 50%, var(--kk-gray-200)); margin: 8px 0 8px; }
.scenario-marker { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); width: 14px; height: 14px; border-radius: 50%; background: var(--kk-orange); border: 2px solid white; box-shadow: 0 1px 5px rgba(0,0,0,0.22); transition: left 0.4s ease; }
.scenario-ends { display: flex; justify-content: space-between; align-items: baseline; font-size: 11.5px; color: var(--kk-gray-500); }
.scenario-ends b { color: var(--kk-charcoal); font-weight: 600; }
.scenario-ends .scen-mid { font-size: 10.5px; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); }
/* The headline's range, the average per year and the total, side by side:
   three measures of one effect, so the same size and no accent colour. */
.hero-figures { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin: 4px 0 18px;
  border-top: 1px solid var(--kk-gray-200); border-bottom: 1px solid var(--kk-gray-200); }
.hero-figures .fig { padding: 12px 10px 11px; }
.hero-figures .fig + .fig { border-left: 1px solid var(--kk-gray-200); }
.hero-figures .fig-label { font-size: 12px; color: var(--kk-gray-500); }
.hero-figures .fig-value { font-size: 21px; font-weight: 600; color: var(--kk-charcoal); margin-top: 3px; line-height: 1.15; }
.hero-figures .fig-value small { font-size: 12px; font-weight: 400; color: var(--kk-gray-500); }
.hero-figures .fig-note { font-size: 12px; color: var(--kk-gray-500); margin-top: 2px; }
@media (max-width: 520px) {
  .hero-figures .fig + .fig { border-left: 0; border-top: 1px solid var(--kk-gray-200); }
}
.scenario-cum { text-align: center; font-size: 12px; color: var(--kk-gray-500); margin-top: 10px; }
.scenario-cum b { color: var(--kk-charcoal); font-weight: 600; }
/* Year-by-year chart: how the headline is built. The band is low to high, the
   line the middle scenario, the shaded years what "medel per år" averages. */
.hero-chart { margin: 4px 0 10px; }
.chart-svg svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart-band { fill: var(--kk-orange-soft); }
.chart-line { fill: none; stroke: var(--kk-orange); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.chart-window { fill: var(--kk-gray-100); }
.chart-zero { stroke: var(--kk-gray-300); stroke-width: 1; }
.chart-avg { stroke: var(--kk-charcoal); stroke-width: 1.25; stroke-dasharray: 4 3; }
.chart-dot { fill: var(--kk-orange); stroke: white; stroke-width: 2; }
.chart-text { font-size: 12px; fill: var(--kk-gray-500); font-family: inherit; }
.chart-text.strong { fill: var(--kk-charcoal-text); font-weight: 600; }
.chart-text.avg { fill: var(--kk-charcoal); }
.hero-chart figcaption { font-size: 12.5px; color: var(--kk-gray-500); margin-top: 6px; }
.hero-chart figcaption b { color: var(--kk-charcoal); font-weight: 600; }
.chart-line.draw { animation: chart-draw 1.1s ease-out both; }
@keyframes chart-draw { from { stroke-dashoffset: var(--len); } to { stroke-dashoffset: 0; } }
@media (prefers-reduced-motion: reduce) { .chart-line.draw { animation: none; } }

/* Live step sections */
.step-sec { background: white; border: 1px solid var(--kk-gray-200); border-radius: 8px; overflow: hidden; }
.step-sec-head { display: flex; align-items: center; gap: 10px; padding: 11px 16px; background: var(--kk-gray-50); border-bottom: 1px solid var(--kk-gray-100); }
.step-sec.running .step-sec-head { background: var(--kk-orange-pale); }
.step-sec-num { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--kk-gray-200); color: var(--kk-gray-500); font-size: 11.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.step-sec.running .step-sec-num { background: var(--kk-orange); color: white; }
.step-sec.done .step-sec-num { background: var(--kk-green); color: white; }
.step-sec-time { font-size: 11px; color: var(--kk-gray-500); font-variant-numeric: tabular-nums; min-width: 2.6em; text-align: right; }
.step-sec-title { font-size: 11.5px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; color: var(--kk-charcoal); flex: 1; }
.step-sec-status { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--kk-gray-400); white-space: nowrap; }
.step-sec.done .step-sec-status { color: var(--kk-green); }
.mini-spin { width: 12px; height: 12px; border: 2px solid var(--kk-gray-200); border-top-color: var(--kk-orange); border-radius: 50%; animation: spin 0.8s linear infinite; }
.step-sec-body { padding: 14px 18px; font-size: 13.5px; line-height: 1.6; color: var(--kk-charcoal); }
/* A re-run from a gate failed: the previous version stays in the body, and
   this says so above it. */
.step-sec-note { padding: 10px 18px; background: var(--kk-orange-pale); border-left: 3px solid var(--kk-red); border-bottom: 1px solid var(--kk-gray-100); font-size: 12.5px; line-height: 1.45; color: var(--kk-charcoal); }
.step-sec-note-head { font-weight: 600; color: var(--kk-red); }
.step-sec-note-why { margin-top: 2px; }
.step-sec-updating { display: flex; align-items: center; gap: 8px; padding: 8px 18px; background: var(--kk-orange-pale); border-bottom: 1px solid var(--kk-gray-100); font-size: 12.5px; color: var(--kk-charcoal); }
.step-sec.updating .step-sec-body { opacity: .45; transition: opacity .2s; }
.step-sec-body p { margin: 6px 0; }
.step-sec-body ul, .step-sec-body ol { margin: 6px 0 6px 20px; }
.step-sec-body li { margin: 2px 0; }
.step-sec-body h1, .step-sec-body h2, .step-sec-body h3, .step-sec-body h4 { font-size: 13.5px; font-weight: 600; margin: 12px 0 4px; color: var(--kk-charcoal); }
.step-sec-body table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12.5px; }
.step-sec-body th, .step-sec-body td { border: 1px solid var(--kk-gray-200); padding: 6px 9px; text-align: left; }
.step-sec-body th { background: var(--kk-gray-50); font-weight: 600; }
.step-sec-body strong { font-weight: 600; }
.shimmer { height: 11px; border-radius: 4px; background: linear-gradient(90deg, var(--kk-gray-100) 25%, var(--kk-gray-200) 37%, var(--kk-gray-100) 63%); background-size: 400% 100%; animation: shimmer 1.4s ease infinite; margin: 8px 0; }
.shimmer.w90 { width: 90%; } .shimmer.w70 { width: 70%; } .shimmer.w50 { width: 50%; }
@keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }

/* Källa / antagande chips inside step bodies */
.kalla-chip { display: inline-block; font-size: 9.5px; font-weight: 700; letter-spacing: 0.4px; text-transform: uppercase; padding: 1px 8px; border-radius: 100px; background: var(--kk-orange-pale); color: var(--kk-orange); white-space: nowrap; vertical-align: middle; }
.kalla-chip.antag { background: var(--kk-cream); color: var(--kk-cream-text); }
.kalla-chip.andrad { background: var(--kk-orange-soft); color: var(--kk-orange); }

/* Åtgärdsprofil cards (step 1). The measure itself, not analysis of it, so the
   card leads with the name and lays the fields out as a scannable claims sheet.
   What a reader has to be able to see at a glance is which values CAIA assumed. */
.step-sec.profile { border-left: 3px solid var(--kk-orange); }
.step-sec.profile .step-sec-body { padding: 0; }
.pf-card { padding: 14px 18px; }
.pf-card + .pf-card { border-top: 1px solid var(--kk-gray-100); }
.pf-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px; }
.pf-name { font-size: 15px; font-weight: 600; color: var(--kk-charcoal-text); line-height: 1.35; flex: 1; }
.pf-count { flex-shrink: 0; font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); }
.pf-desc { font-size: 13px; line-height: 1.6; color: var(--kk-gray-600); margin: 0 0 12px; }
.pf-grid { display: grid; grid-template-columns: 116px 1fr; gap: 7px 14px; }
.pf-label { font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); padding-top: 2px; }
.pf-value { font-size: 13px; line-height: 1.5; color: var(--kk-charcoal-text); }
.pf-value.empty { color: var(--kk-gray-400); font-style: italic; }
.pf-note { display: block; font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-500); margin-top: 2px; }
/* A corrected field says so and shows what it replaced, because the previous
   value exists nowhere else once the cards re-render. */
.pf-value.changed { box-shadow: -10px 0 0 -8px var(--kk-orange); padding-left: 6px; margin-left: -6px; }
.pf-was { display: block; font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-400); margin-top: 2px; text-decoration: line-through; }
.pf-raw { padding: 14px 18px; font-size: 13.5px; line-height: 1.6; }
/* A profile the parser could not structure: shown verbatim, marked as such. */
.pf-unparsed { font-size: 13px; line-height: 1.6; color: var(--kk-gray-600); border-left: 2px solid var(--kk-gray-200); padding-left: 10px; }
.pf-unparsed p { margin: 4px 0; }

/* EMAP: the step as a view. A driver is an activity times an emission
   factor, so it is drawn as that sum; the orange operators are the one
   accent. The classification folds its reasons away under each value. */
.step-sec.emap .step-sec-body { padding: 4px 18px 14px; }
.em-profile + .em-profile { border-top: 1px solid var(--kk-gray-200); margin-top: 14px; padding-top: 4px; }
.step-sec-body .em-title { font-size: 16px; font-weight: 600; line-height: 1.35; color: var(--kk-charcoal-text); margin: 12px 0 6px; }
/* "Det viktigaste": what the person at the gate should know before reading
   the step, built from what the step produced (keyPointsHtml). */
.key-points { margin: 0 0 14px; padding: 10px 14px 10px 13px; background: var(--kk-orange-pale);
  border-left: 3px solid var(--kk-orange); border-radius: 0 6px 6px 0; max-width: 72ch; }
.key-points.warn { background: var(--kk-cream); border-left-color: var(--kk-red); }
.key-points.ok { background: #EEF4EF; border-left-color: var(--kk-green); }
.key-points h4 { margin: 0 0 4px; font-size: 13px; font-weight: 700; color: var(--kk-charcoal-text); }
.key-points ul { margin: 0; padding-left: 18px; }
.key-points li { margin: 2px 0; font-size: 13px; line-height: 1.5; color: var(--kk-charcoal-text); }
.key-points li.warn { color: var(--kk-red); }
.step-sec.evidens .key-points { margin: 14px 18px 0; }
.em-summary { font-size: 13.5px; line-height: 1.6; color: var(--kk-charcoal-text); max-width: 68ch; }
.em-summary p { margin: 0 0 6px; }
.step-sec-body .em-h { font-size: 13px; font-weight: 600; color: var(--kk-charcoal-text); margin: 18px 0 8px; }
.step-sec-body .em-drivers { list-style: none; padding: 0; margin: 0; }
.step-sec-body .em-driver { padding: 10px 0 12px; margin: 0; }
.em-driver + .em-driver { border-top: 1px solid var(--kk-gray-100); }
.em-dname { display: flex; align-items: baseline; gap: 9px; font-size: 14px; font-weight: 600; line-height: 1.4; color: var(--kk-charcoal-text); margin-bottom: 8px; }
.em-dnum { flex-shrink: 0; width: 19px; height: 19px; border-radius: 50%; background: var(--kk-gray-100); color: var(--kk-gray-500); font-size: 10.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.em-eq { display: grid; grid-template-columns: minmax(0, 1.2fr) auto minmax(0, 1fr) auto minmax(0, 1.2fr); align-items: stretch; gap: 6px; margin-left: 28px; }
.em-term { background: var(--kk-gray-50); border: 1px solid var(--kk-gray-100); border-radius: 6px; padding: 7px 10px; }
.em-term-lab { font-size: 11px; color: var(--kk-gray-500); margin-bottom: 2px; }
.em-term-val { font-size: 12.5px; line-height: 1.4; color: var(--kk-charcoal-text); overflow-wrap: anywhere; }
.em-op { align-self: center; font-size: 17px; font-weight: 500; color: var(--kk-orange); padding: 0 1px; }
.step-sec-body .em-enabler, .step-sec-body .em-sector, .step-sec-body .em-overlap { font-size: 12.5px; line-height: 1.5; color: var(--kk-gray-600); margin: 6px 0 0 28px; max-width: 70ch; }
.step-sec-body .em-enabler { margin-top: 0; }
.em-risk { font-weight: 600; }
.em-risk.hog { color: var(--kk-red); }
.em-risk.medel { color: var(--kk-cream-text); }
.em-risk.lag { color: var(--kk-gray-600); }
.em-rest, .em-text { font-size: 12.5px; line-height: 1.55; color: var(--kk-gray-600); margin: 6px 0 0 28px; }
.em-text { margin-left: 0; max-width: 70ch; }
.em-classes { margin: 0; }
.em-class { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 12px; padding: 6px 0; border-top: 1px solid var(--kk-gray-100); }
.em-class:first-child { border-top: none; }
.em-class dt { font-size: 12.5px; color: var(--kk-gray-500); padding-top: 1px; }
.em-class dd { margin: 0; font-size: 13px; }
.em-val { font-weight: 600; color: var(--kk-charcoal-text); }
.em-class summary { cursor: pointer; list-style: none; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.em-class summary::-webkit-details-marker { display: none; }
.em-class summary:focus-visible { outline: 2px solid var(--kk-orange); outline-offset: 2px; border-radius: 3px; }
.em-why-btn { font-size: 11.5px; color: var(--kk-gray-500); text-decoration: underline; text-underline-offset: 2px; }
.em-class details[open] .em-why-btn { color: var(--kk-charcoal); }
.em-why { font-size: 12.5px; line-height: 1.55; color: var(--kk-gray-600); margin-top: 4px; max-width: 70ch; }
.em-why p { margin: 0 0 4px; }
.step-sec-body .em-list { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.55; color: var(--kk-charcoal-text); max-width: 70ch; }
.step-sec-body .em-list li { margin: 0; }
.step-sec-body .em-list li + li { margin-top: 3px; }
@media (max-width: 720px) {
  .em-eq { grid-template-columns: 1fr; margin-left: 0; }
  .em-op { justify-self: center; }
  .step-sec-body .em-enabler, .step-sec-body .em-sector, .step-sec-body .em-overlap, .em-rest { margin-left: 0; }
  .em-class { grid-template-columns: 1fr; gap: 2px; }
}

/* Evidens: one card per driver. This is the second approval gate, so the three
   climate factors and the min/med/max span are the content, and the agent's
   reasoning prose folds away under them. */
.step-sec.evidens .step-sec-body { padding: 0; }
.ev-card { padding: 14px 18px; }
.ev-card + .ev-card { border-top: 1px solid var(--kk-gray-100); }
.ev-head { display: flex; align-items: baseline; gap: 9px; margin-bottom: 3px; }
.ev-num { flex-shrink: 0; width: 19px; height: 19px; border-radius: 50%; background: var(--kk-gray-100); color: var(--kk-gray-500); font-size: 10.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.ev-name { font-size: 14.5px; font-weight: 600; color: var(--kk-charcoal-text); line-height: 1.35; }
.ev-mek { font-size: 12.5px; line-height: 1.5; color: var(--kk-gray-600); margin: 0 0 11px 28px; }
/* Territoriell / konsumtion / överlapp decide whether a reduction is counted
   twice, so they sit on one line where they can be compared at a glance. */
.ev-factors { display: flex; gap: 8px; margin: 0 0 12px 28px; }
.ev-factor { flex: 1; background: var(--kk-gray-50); border-radius: 6px; padding: 7px 9px; }
.ev-factor-val { font-size: 15px; font-weight: 600; color: var(--kk-charcoal-text); font-variant-numeric: tabular-nums; }
.ev-factor-val.words { font-size: 11.5px; font-weight: 500; line-height: 1.35; color: var(--kk-gray-500); }
.ev-factor-lab { font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); margin-top: 1px; }
.ev-motiv { font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-500); margin: -6px 0 12px 28px; }
.ev-param { margin: 0 0 12px 28px; padding-left: 10px; border-left: 2px solid var(--kk-gray-200); }
.ev-param-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 3px; }
.ev-param-name { font-size: 13.5px; font-weight: 600; line-height: 1.35; color: var(--kk-charcoal); }
/* The agent's own name for the parameter, kept small so a reader can still
   point at it in the chat, as in the parameter library. */
.ev-param-id { font-size: 11px; color: var(--kk-gray-500); overflow-wrap: anywhere; }
.ev-param-unit { font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-500); margin-bottom: 7px; }
.ev-src { font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-500); margin-top: 6px; }
/* The middle value is the one the calculation uses; the ends are the range
   around it. Weighting them equally would read as three alternatives. */
.ev-span { display: grid; grid-template-columns: 1fr 1.25fr 1fr; gap: 8px; align-items: stretch; }
.ev-span-cell { padding: 7px 9px; border-radius: 6px; background: var(--kk-gray-50); }
.ev-span-cell.mid { background: var(--kk-orange-pale); border: 1px solid var(--kk-orange-soft); }
.ev-span-lab { font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); margin-bottom: 2px; }
.ev-span-cell.mid .ev-span-lab { color: var(--kk-orange); }
.ev-span-val { font-size: 12.5px; line-height: 1.4; color: var(--kk-gray-600); }
.ev-span-cell.mid .ev-span-val { font-size: 13.5px; font-weight: 600; color: var(--kk-charcoal-text); }
.ev-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 7px; }
.kalla-chip.kval-hog { background: #e6f2ea; color: #2f6b45; }
.kalla-chip.kval-medel { background: var(--kk-cream); color: var(--kk-cream-text); }
.kalla-chip.kval-lag { background: #fbe7e7; color: var(--kk-red); }
.ev-komm { font-size: 11.5px; line-height: 1.45; color: var(--kk-gray-500); margin-top: 6px; }
.ev-extra { font-size: 12px; color: var(--kk-gray-500); margin: 4px 0 0 28px; }
/* The agent's prose is kept, but folded: it is context, not the decision. */
.ev-prose { border-top: 1px solid var(--kk-gray-100); }
.ev-prose-toggle { width: 100%; text-align: left; background: none; border: none; padding: 11px 18px; font-family: inherit; font-size: 12px; font-weight: 600; color: var(--kk-gray-500); cursor: pointer; display: flex; align-items: center; gap: 7px; }
.ev-prose-toggle:hover { color: var(--kk-orange); }
.ev-prose-toggle .trail-caret { transition: transform 0.15s; }
.ev-prose.open .trail-caret { transform: rotate(90deg); }
.ev-prose-body { display: none; padding: 0 18px 14px; font-size: 12.5px; line-height: 1.6; color: var(--kk-gray-600); }
.ev-prose.open .ev-prose-body { display: block; }
.ev-prose-sec { font-size: 10.5px; font-weight: 700; letter-spacing: 0.6px; text-transform: uppercase; color: var(--kk-gray-400); margin: 12px 0 4px; }
.ev-prose-body p { margin: 5px 0; }
.ev-prose-body ul { margin: 5px 0 5px 18px; }

/* A correction made in the chat has to be visible in the panel, which the eye
   is not on at that moment. The card names when it changed and flashes once. */
.pf-updated { animation: pf-flash 1.6s ease-out 1; }
@keyframes pf-flash { 0% { background: var(--kk-orange-soft); } 100% { background: transparent; } }
@media (prefers-reduced-motion: reduce) { .pf-updated { animation: none; } }

/* Collapsible analysis trail (shown after the report is ready) */
.trail-toggle { width: 100%; text-align: left; background: none; border: none; border-top: 1px solid var(--kk-gray-200); padding: 16px 2px 2px; font-size: 12px; font-weight: 600; color: var(--kk-gray-500); cursor: pointer; font-family: inherit; display: flex; align-items: center; gap: 8px; }
.trail-toggle:hover { color: var(--kk-orange); }
.trail-caret { transition: transform 0.2s; display: inline-block; }
.trail-toggle.open .trail-caret { transform: rotate(90deg); }

/* Parameters modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(47,46,44,0.45); display: none; align-items: center; justify-content: center; z-index: 90; padding: 28px 18px; }
.modal { background: white; border-radius: 10px; max-width: 1080px; width: 100%; max-height: calc(100vh - 56px); overflow-y: auto; box-shadow: 0 10px 50px rgba(0,0,0,0.25); }
.modal-bar { position: sticky; top: 0; z-index: 10; background: white; padding: 12px 18px; display: flex; justify-content: flex-end; border-bottom: 1px solid var(--kk-gray-200); border-radius: 10px 10px 0 0; }
.modal-title { font-size: 18px; font-weight: 600; color: var(--kk-charcoal); }
.modal-sub { font-size: 12.5px; color: var(--kk-gray-500); margin-top: 4px; max-width: 640px; }
.modal-body { padding: 16px 26px 28px; overflow-x: auto; }
.param-table { min-width: 680px; }
.param-summary { background: var(--kk-gray-50); border: 1px solid var(--kk-gray-200); border-radius: 8px; padding: 12px 16px; margin: 16px 0 8px; font-size: 13px; color: var(--kk-gray-600); }
.param-summary b { color: var(--kk-charcoal); }
.param-sec { font-size: 14px; font-weight: 600; color: var(--kk-charcoal); margin: 24px 0 8px; }
.param-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.param-table th { text-align: left; font-size: 10.5px; letter-spacing: 0.5px; text-transform: uppercase; color: var(--kk-gray-400); font-weight: 700; padding: 6px 10px; border-bottom: 1px solid var(--kk-gray-200); }
.param-table td { padding: 9px 10px; border-bottom: 1px solid var(--kk-gray-100); vertical-align: top; color: var(--kk-charcoal); }
.param-name { font-weight: 600; max-width: 380px; }
.param-id { color: var(--kk-gray-500); font-size: 11.5px; margin-top: 2px; overflow-wrap: anywhere; }
.param-note { color: var(--kk-gray-500); font-size: 11.5px; margin-top: 2px; max-width: 340px; }
.param-val { font-weight: 600; white-space: nowrap; }
.prov-badge { display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: 0.3px; padding: 2px 8px; border-radius: 100px; white-space: nowrap; }
.prov-lokal { background: #eef5f0; color: var(--kk-green); }
.prov-datafil { background: #eef1f6; color: #3b5b8c; }
.prov-schablon { background: var(--kk-cream); color: var(--kk-cream-text); }
.param-summary .prov-lokal, .param-summary .prov-datafil, .param-summary .prov-schablon { padding: 1px 7px; border-radius: 100px; font-weight: 600; }

/* About modal content */
.about-lead { font-size: 14px; line-height: 1.6; color: var(--kk-charcoal); margin: 16px 0 8px; }
.about-sec { font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--kk-gray-400); margin: 24px 0 10px; }
.attribution { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--kk-gray-100); font-size: 11.5px; line-height: 1.5; color: var(--kk-gray-400); text-align: center; }
.results-empty .attribution { max-width: 460px; margin-left: auto; margin-right: auto; }
.about-step { display: flex; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--kk-gray-100); font-size: 13.5px; line-height: 1.55; color: var(--kk-charcoal); }
.about-step b { font-weight: 600; }
.about-num { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--kk-orange-pale); color: var(--kk-orange); font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.modal-body p { font-size: 13.5px; line-height: 1.6; color: var(--kk-charcoal); margin: 8px 0; }

/* Portfolio modal: several saved analyses on shared emission pots */
.pf-pick { display: flex; gap: 10px; align-items: flex-start; padding: 9px 4px; border-bottom: 1px solid var(--kk-gray-100); font-size: 13px; cursor: pointer; }
.pf-pick:hover { background: var(--kk-orange-pale); }
.pf-pick input { margin-top: 3px; accent-color: var(--kk-orange); }
.pf-pick .si-meta { font-size: 11px; color: var(--kk-gray-400); margin-top: 2px; }
.pf-action { margin: 22px 0 6px; font-size: 14px; font-weight: 600; color: var(--kk-charcoal); }
.pf-action .si-meta { font-weight: 400; font-size: 11.5px; color: var(--kk-gray-400); }
.pf-skip { font-size: 12.5px; color: var(--kk-gray-500); margin: 6px 0; }
.pf-table select { font-family: inherit; font-size: 12.5px; padding: 4px 6px; border: 1px solid var(--kk-gray-200); border-radius: 6px; background: white; max-width: 280px; }
.pf-targets { font-size: 12.5px; color: var(--kk-gray-600); margin: 8px 0 0; }
.pf-targets label { display: block; margin: 3px 0; cursor: pointer; }
.pf-targets input { accent-color: var(--kk-orange); }
.pf-buttons { display: flex; gap: 10px; align-items: center; margin-top: 20px; }
.pf-msg { font-size: 12.5px; line-height: 1.45; color: var(--kk-red); margin-top: 10px; }
.pf-result { margin-top: 22px; }
.report-container h4 { font-size: 14px; color: var(--kk-charcoal); margin: 18px 0 6px; }
.btn-pill:focus-visible, .btn-approve:focus-visible, .btn-save:focus-visible, .pf-pick input:focus-visible { outline: 2px solid var(--kk-orange); outline-offset: 2px; }

@media (max-width: 768px) {
  /* The name and its expansion fill a phone's width, so the buttons take a
     row of their own instead of running off the screen. */
  .topbar { flex-wrap: wrap; row-gap: 10px; padding: 12px 16px; }
  .topbar-right { flex-wrap: wrap; gap: 6px; }
  /* The seven steps already fill a phone's width, so the mode goes on a row
     of its own under them, starting at the left edge like the steps. */
  .progress-bar { flex-wrap: wrap; row-gap: 8px; padding: 10px 16px; }
  .progress-steps { flex-basis: 100%; }
  .mode-switch { margin-left: 0; }
  .main { flex-direction: column; }
  .chat-panel, .results-panel { width: 100%; height: 50%; }
  .results-panel { padding: 16px; }
  .chat-panel { border-right: none; border-bottom: 1px solid var(--kk-gray-200); }
  /* The label column does not fit next to a value on a phone, so the field
     stacks instead of wrapping every value onto three lines. */
  .pf-grid { grid-template-columns: 1fr; gap: 2px; }
  .pf-label { padding-top: 6px; }
  /* "2 åtgärder · 2 antaganden · uppdaterad 12:19" is too long for a phone
     header on one line, and truncating it hides the update signal. */
  .step-sec.profile .step-sec-status { white-space: normal; text-align: right; }
}
</style>
</head>
<body>

{% if has_supabase %}
<div id="authOverlay">
  <div class="login-box">
    <h1>CAIA</h1>
    <p>Climate Action Impact Analysis</p>
    <div id="authForm">
      <input type="email" id="authEmail" placeholder="E-post" autocomplete="email" autofocus>
      <input type="password" id="authPassword" placeholder="L&#xF6;senord" autocomplete="current-password" onkeydown="if(event.key==='Enter')handleAuth()">
      <div id="authSignupHint" class="auth-hint" style="display:none">Anv&#xE4;nd din jobbadress. L&#xF6;senordet ska ha minst 6 tecken. Du f&#xE5;r ett mejl med en l&#xE4;nk att bekr&#xE4;fta kontot med.</div>
      <div id="authError" class="error" style="display:none"></div>
      <a href="#" id="authResend" class="auth-link" style="display:none" onclick="resendConfirmation(event)">Skicka bekr&#xE4;ftelsemejlet igen</a>
      <button onclick="handleAuth()" id="authSubmitBtn">Logga in</button>
      <div style="text-align:center;margin-top:14px;font-size:13px;color:var(--kk-gray-400)">
        <span id="authToggleText">Inget konto?</span>
        <a href="#" onclick="toggleAuthMode(event)" id="authToggleLink" style="color:var(--kk-orange)">Skapa konto</a>
      </div>
      <div style="text-align:center;margin-top:8px;font-size:13px">
        <a href="#" id="authForgot" class="auth-link" onclick="forgotPassword(event)">Gl&#xF6;mt l&#xF6;senordet?</a>
      </div>
    </div>
    <div id="newPasswordForm" style="display:none">
      <p style="margin-top:0">V&#xE4;lj ett nytt l&#xF6;senord, minst 6 tecken.</p>
      <input type="password" id="newPassword" placeholder="Nytt l&#xF6;senord" autocomplete="new-password" onkeydown="if(event.key==='Enter')saveNewPassword()">
      <div id="newPasswordError" class="error" style="display:none"></div>
      <button onclick="saveNewPassword()" id="newPasswordBtn">Spara och logga in</button>
    </div>
    <div class="attribution">{{ origin }}</div>
  </div>
</div>
<div id="appContainer" style="display:none;flex-direction:column;flex:1;overflow:hidden">
{% endif %}

<div class="topbar">
  <div class="topbar-left">
    <span class="topbar-logo">CAIA</span>
    <span class="topbar-sep"></span>
    <span class="topbar-sub">Climate Action Impact Analysis</span>
  </div>
  <div class="topbar-right">
    {% if has_supabase %}
    <button class="btn-pill" onclick="toggleSavedMenu()">Sparade analyser</button>
    <button class="btn-pill" onclick="openPortfolio()">Portf&#xF6;lj</button>
    <div class="saved-menu" id="savedMenu">
      <div class="saved-menu-header">Sparade analyser</div>
      <div id="savedList"><div class="saved-empty">Inga sparade analyser &#xE4;n.</div></div>
    </div>
    {% endif %}
    <button class="btn-pill" onclick="openAbout()">Om verktyget</button>
    <button class="btn-pill" onclick="openParams()">Parametrar</button>
    <button class="btn-pill" onclick="startNewAnalysis()">Ny analys</button>
    {% if has_supabase %}
    <span class="user-email" id="userEmail"></span>
    <button class="btn-pill" onclick="signOut()">Logga ut</button>
    {% elif password_mode %}
    <a class="btn-pill" href="/logout" style="text-decoration:none">Logga ut</a>
    {% endif %}
  </div>
</div>

<div class="progress-bar" id="progressBar">
  <div class="progress-steps">
    <div class="progress-step active" data-step="intake"><span class="progress-dot"></span>&#xC5;tg&#xE4;rdsf&#xF6;rslag</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="emap"><span class="progress-dot"></span>Utsl&#xE4;ppsk&#xE4;llor</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="baslinje"><span class="progress-dot"></span>Baslinje</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="evidens"><span class="progress-dot"></span>Evidens</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="kalkyl"><span class="progress-dot"></span>Kalkyl</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="qa"><span class="progress-dot"></span>QA</div>
    <span class="progress-arrow">&#x203A;</span>
    <div class="progress-step" data-step="rapport"><span class="progress-dot"></span>Rapport</div>
  </div>
  <fieldset class="mode-switch" id="modeSwitch">
    <legend id="modeLegend">V&#xE4;lj analystyp</legend>
    <span class="mode-label" id="modeLabel" aria-hidden="true">V&#xE4;lj analystyp:</span>
    <div class="mode-seg">
      <label><input type="radio" name="mode" value="potential" checked onchange="setMode(this.value)"><span class="mode-pill">Prognos</span></label>
      <label><input type="radio" name="mode" value="uppfoljning" onchange="setMode(this.value)"><span class="mode-pill">Uppf&#xF6;ljning</span></label>
    </div>
  </fieldset>
</div>

<div class="main">
  <div class="chat-panel">
    <div class="chat-messages" id="chatMessages">
      <div class="msg-system">Beskriv en klimat&#xE5;tg&#xE4;rd du vill analysera &#x2014; allt fr&#xE5;n en kort rubrik till en l&#xE4;ngre beskrivning.</div>
    </div>
    <div id="approveArea" class="approve-area" style="display:none">
      <button class="btn-approve" id="btnApprove" onclick="onApprove()">Godk&#xE4;nn profilen och forts&#xE4;tt</button>
    </div>
    <div class="chat-input-area" id="inputArea">
      <textarea id="chatInput" placeholder="Beskriv &#xE5;tg&#xE4;rden..." rows="1" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage()}"></textarea>
      <button class="btn-send" id="btnSend" onclick="sendMessage()">Skicka</button>
    </div>
  </div>

  <div class="results-panel" id="resultsPanel">
    <div class="results-empty" id="resultsEmpty">
      <h2>CAIA</h2>
      <p>Ber&#xE4;knar f&#xF6;rv&#xE4;ntad klimatnytta av &#xE5;tg&#xE4;rder i {{ kommun.plan }}. Beskriv en &#xE5;tg&#xE4;rd i chatten f&#xF6;r att b&#xF6;rja.</p>
      <ul class="start-notes">
        <li><b>R&#xE4;knar med data f&#xF6;r {{ kommun.namn }}.</b> Utsl&#xE4;pp, resvanor och parameterbiblioteket kommer d&#xE4;rifr&#xE5;n. En &#xE5;tg&#xE4;rd som &#xE4;r t&#xE4;nkt f&#xF6;r en annan kommun r&#xE4;knas som om den genomf&#xF6;rdes i {{ kommun.ort }}, s&#xE5; l&#xE4;s resultatet som ett exempel p&#xE5; metoden.</li>
        <li><b>R&#xE4;kna med 7 till 30 minuter per analys.</b> Den stannar fyra g&#xE5;nger s&#xE5; att du kan granska, r&#xE4;tta i chatten och godk&#xE4;nna innan den r&#xE4;knar vidare. Hur l&#xE5;ng tid det tar beror mest p&#xE5; hur noga du l&#xE4;ser och svarar.</li>
        <li><b>Skriv inga personuppgifter.</b> Texten skickas till en AI-spr&#xE5;kmodell hos en extern leverant&#xF6;r.</li>
      </ul>
      <div class="attribution">{{ origin }} {{ license_note }}</div>
    </div>
    <div id="analysisCard" class="analysis-card" style="display:none">
      <div class="report-actions" id="reportActions" style="display:none">
        <span id="saveIndicator"></span>
        <button class="btn-save" onclick="printReport()">Skriv ut eller spara som PDF</button>
        <button class="btn-save secondary" onclick="downloadReport()">Ladda ner som text (.md)</button>
      </div>
      <h2 class="report-title" id="reportTitle" style="display:none"></h2>
      <div class="card" id="heroCard" style="display:none">
        <div class="card-strip"></div>
        <div class="hero">
          <div class="hero-label" id="heroLabel">F&#xF6;rv&#xE4;ntad klimatnytta, medel per &#xE5;r {{ avg_window[0] }}&#x2013;{{ avg_window[1] }}</div>
          <div class="hero-value" id="heroValue">&#x2013; <span>ton CO&#x2082;e/&#xE5;r</span></div>
          <div class="hero-sub" id="heroSub"></div>
          <div class="hero-warn" id="heroWarn" style="display:none"></div>
          <div class="hero-interp" id="heroInterp" style="display:none"></div>
          <div class="scenario" id="heroScenario" style="display:none">
            <div class="hero-figures" id="heroFigures" style="display:none"></div>
            <figure class="hero-chart" id="heroChart" style="display:none">
              <div class="chart-svg" id="heroChartSvg"></div>
              <figcaption id="heroChartCaption"></figcaption>
            </figure>
            <div class="scenario-track" id="scenTrack"><div class="scenario-marker" id="scenMarker"></div></div>
            <div class="scenario-ends">
              <span id="scenLo"></span><span class="scen-mid">Mellanscenario</span><span id="scenHi"></span>
            </div>
            <div class="scenario-cum" id="scenCum"></div>
          </div>
        </div>
      </div>
      <div class="report-container" id="reportContent" style="display:none"></div>
      <div class="print-attribution" id="printAttribution"></div>
      <button class="trail-toggle" id="trailToggle" style="display:none" onclick="toggleTrail()">
        <span class="trail-caret">&#x203A;</span><span id="trailLabel">Visa analysunderlag (alla steg)</span>
      </button>
      <div id="analysisFeed"></div>
    </div>
  </div>
</div>

{% if has_supabase %}</div>{% endif %}

<div class="modal-overlay" id="paramsModal">
  <div class="modal">
    <div class="modal-bar"><button class="btn-pill" onclick="closeParams()">St&#xE4;ng</button></div>
    <div class="modal-body">
      <div class="modal-title">Klimatfaktorer &#x2014; parameterbibliotek</div>
      <div class="modal-sub">De v&#xE4;rden ber&#xE4;kningarna vilar p&#xE5;. K&#xE4;llan visar vad som &#xE4;r lokalt verifierat och vad som &#xE4;r nationell schablon.</div>
      <div id="paramsBody"></div>
    </div>
  </div>
</div>

{% if has_supabase %}
<div class="modal-overlay" id="portfolioModal">
  <div class="modal">
    <div class="modal-bar"><button class="btn-pill" onclick="closePortfolio()">St&#xE4;ng</button></div>
    <div class="modal-body">
      <div class="modal-title">Portf&#xF6;lj: flera &#xE5;tg&#xE4;rder tillsammans</div>
      <div class="modal-sub">Varje analys r&#xE4;knar sin &#xE5;tg&#xE4;rd f&#xF6;r sig. Verkar flera &#xE5;tg&#xE4;rder p&#xE5; samma utsl&#xE4;pp r&#xE4;knar summan av deras tal samma ton flera g&#xE5;nger. Portf&#xF6;ljen r&#xE4;knar dem tillsammans, s&#xE5; att de aldrig kan minska mer &#xE4;n det utsl&#xE4;pp som finns.</div>
      <div id="portfolioBody"></div>
    </div>
  </div>
</div>
{% endif %}

<div class="modal-overlay" id="aboutModal">
  <div class="modal">
    <div class="modal-bar"><button class="btn-pill" onclick="closeAbout()">St&#xE4;ng</button></div>
    <div class="modal-body">
      <div class="modal-title">Om CAIA</div>
      <div class="modal-sub">Climate Action Impact Analysis. Hur verktyget r&#xE4;knar ut klimatnyttan av en &#xE5;tg&#xE4;rd.</div>
      <p class="about-lead">CAIA uppskattar hur mycket v&#xE4;xthusgasutsl&#xE4;pp en f&#xF6;reslagen kommunal &#xE5;tg&#xE4;rd kan minska, uttryckt i ton CO&#x2082;e per &#xE5;r. Du beskriver en &#xE5;tg&#xE4;rd i fritext; en kedja av specialiserade AI-agenter arbetar igenom den steg f&#xF6;r steg, grundat i ett bibliotek av {{ kommun.ort }}-parametrar. Resultatet &#xE4;r ett beslutsklart &#xE5;tg&#xE4;rdskort med en huvudsiffra, scenarier och tydligt redovisade antaganden.</p>

      <div class="about-sec">De sju stegen</div>
      <div class="about-step"><span class="about-num">1</span><div><b>&#xC5;tg&#xE4;rdsf&#xF6;rslag (intake)</b> &#x2014; Tolkar din beskrivning, st&#xE4;ller vid behov n&#xE5;gra klarg&#xF6;rande fr&#xE5;gor, och formar en strukturerad &#xE5;tg&#xE4;rdsprofil (sektor, m&#xE5;lgrupp, r&#xE5;dighet, tidsram). Antaganden m&#xE4;rks tydligt.</div></div>
      <div class="about-step"><span class="about-num">2</span><div><b>Utsl&#xE4;ppsk&#xE4;llor</b> &#x2014; Pekar ut vilka utsl&#xE4;ppsk&#xE4;llor &#xE5;tg&#xE4;rden p&#xE5;verkar och klassar &#xE5;tg&#xE4;rden: typ, mekanism (undvika / skifta / effektivisera), niv&#xE5;, mognad och typ av effekt. Ingen r&#xE4;kning &#xE4;n.</div></div>
      <div class="about-step"><span class="about-num">3</span><div><b>Baslinje</b> &#x2014; S&#xE4;tter nul&#xE4;get (aktivitetsniv&#xE5; &#xD7; emissionsfaktor) och hur utsl&#xE4;ppen utvecklas <i>utan</i> &#xE5;tg&#xE4;rd (&#x201D;business as usual&#x201D;) fram till m&#xE5;l&#xE5;ret, fr&#xE5;n parameterbiblioteket.</div></div>
      <div class="about-step"><span class="about-num">4</span><div><b>Evidens &amp; antaganden</b> &#x2014; Bed&#xF6;mer hur mycket &#xE5;tg&#xE4;rden p&#xE5;verkar, med ett spann (f&#xF6;rsiktigt / troligt / optimistiskt) och k&#xE4;llor. S&#xE4;tter klimatfaktorer: territoriellt, konsumtionsbaserat och &#xF6;verlapp (s&#xE5; samma minskning inte r&#xE4;knas dubbelt).</div></div>
      <div class="about-step"><span class="about-num">5</span><div><b>Kalkyl &amp; tidsprofil</b> &#x2014; R&#xE4;knar utsl&#xE4;ppsminskningen i ton CO&#x2082;e/&#xE5;r med en <b>deterministisk Python-motor</b> (inte gissad av spr&#xE5;kmodellen), inklusive hur effekten rampas upp &#xF6;ver tid.</div></div>
      <div class="about-step"><span class="about-num">6</span><div><b>QA-granskning</b> &#x2014; En oberoende kontroll (chain-of-verification) av k&#xE4;llor, enheter, storleksordning och dubbelr&#xE4;kning. Flaggar de st&#xF6;rsta os&#xE4;kerheterna.</div></div>
      <div class="about-step"><span class="about-num">7</span><div><b>Slutrapport</b> &#x2014; St&#xE4;ller samman ett beslutsklart &#xE5;tg&#xE4;rdskort: huvudsiffra (medel/&#xE5;r), scenariospann, nyckelantaganden, QA-status och rekommendation.</div></div>

      <div class="about-sec">Du godk&#xE4;nner mellan stegen</div>
      <p>CAIA stannar efter steg 1 till 4 och v&#xE4;ntar p&#xE5; dig. Varje resultat visas i panelen till h&#xF6;ger innan n&#xE4;sta steg b&#xF6;rjar. Du kan godk&#xE4;nna det, eller skriva vad som blev fel i chatten &#x2014; d&#xE5; g&#xF6;rs steget om med din r&#xE4;ttelse och de senare stegen r&#xE4;knar p&#xE5; den r&#xE4;ttade versionen. Steg 5 till 7 &#xE4;r ber&#xE4;kning och sammanst&#xE4;llning och k&#xF6;rs i ett svep.</p>

      <div class="about-sec">Om siffrorna</div>
      <p>Alla v&#xE4;rden &#xE4;r <b>estimat</b>. Sj&#xE4;lva matematiken &#xE4;r deterministisk kod, men antagandena bygger p&#xE5; ett parameterbibliotek d&#xE4;r en del v&#xE4;rden &#xE4;r lokalt verifierade f&#xF6;r {{ kommun.ort }} och en del &#xE4;r nationella schabloner. Klicka <b>Parametrar</b> f&#xF6;r att se exakt vilka faktorer som anv&#xE4;nds och hur v&#xE4;l de &#xE4;r underbyggda. Kontrollera schablonm&#xE4;rkta v&#xE4;rden mot lokal data innan beslut.</p>

      <div class="about-sec">Ursprung</div>
      <p>{{ origin }}</p>
      <p>{{ license_note }}</p>
    </div>
  </div>
</div>

<script>
// The active kommunprofil (caia.kommun) and the software's origin line. The
// page says nothing about a municipality that does not come from here.
const KOMMUN = {{ kommun|tojson }};
// The years "medel/år" averages over in a potential analysis (calc.engine).
const AVG_WINDOW = {{ avg_window|tojson }};
const ORIGIN = {{ origin|tojson }};
const HAS_SUPABASE = {{ 'true' if has_supabase else 'false' }};
const SUPABASE_URL = {{ supabase_url|tojson }};
const SUPABASE_ANON_KEY = {{ supabase_anon_key|tojson }};
let supabaseClient = null;
let currentUser = null;
let isSignup = false;

const STEPS = ['intake','emap','baslinje','evidens','kalkyl','qa','rapport'];
const STEP_LABELS = {
  intake: 'Åtgärdsförslag', emap: 'Utsläppskällor', baslinje: 'Baslinje',
  evidens: 'Evidens & antaganden', kalkyl: 'Kalkyl & tidsprofil', qa: 'QA-granskning', rapport: 'Slutrapport'
};
// `headline` is the deterministic calc's terr/cons/net from the kalkyl step. It
// is what the hero shows and what gets saved with the report; null when the
// pipeline fell back to LLM math and there is no computed number to save.
let state = { phase: 'idle', history: [], reportMarkdown: null, running: false, profiles: null, headline: null, kallmarkeringMd: null, mode: 'potential' };
// The two analyses (caia/mode.py). Every step request carries the mode; the
// server is stateless and appends the follow-up rules when it says so.
const MODES = {
  potential: {prompt: 'Beskriv en klimatåtgärd du vill analysera, allt från en kort rubrik till en längre beskrivning.',
              placeholder: 'Beskriv åtgärden...', hero: 'Förväntad klimatnytta'},
  uppfoljning: {prompt: 'Beskriv den genomförda insatsen: vad som gjordes, vad den kostade och vad som har mätts.',
                placeholder: 'Beskriv insatsen...', hero: 'Beräknad klimatnytta av insatsen'},
};
function setMode(mode) {
  if (!MODES[mode] || state.history.length) return;
  state.mode = mode;
  const first = document.querySelector('#chatMessages .msg-system');
  if (first && document.getElementById('chatMessages').children.length === 1) first.textContent = MODES[mode].prompt;
  document.getElementById('chatInput').placeholder = MODES[mode].placeholder;
}
function lockMode(locked) {
  const fs = document.getElementById('modeSwitch');
  fs.disabled = locked;
  fs.title = locked ? 'Vill du byta analystyp, börja om med Ny analys.' : '';
  // "Välj" only while there is a choice; afterwards the row just names the mode.
  document.getElementById('modeLabel').textContent = locked ? 'Analystyp:' : 'Välj analystyp:';
  document.getElementById('modeLegend').textContent = locked ? 'Analystyp' : 'Välj analystyp';
  document.querySelectorAll('#modeSwitch input').forEach(i => { i.checked = i.value === state.mode; });
}
// Bumped by resetAll. An intake call started before "Ny analys" must not draw
// the old measure into the new run when its response finally arrives.
let runToken = 0;

/* ---------- auth ---------- */
async function authFetch(url, options) {
  options = options || {};
  options.headers = options.headers || {};
  if (supabaseClient) {
    const sess = await supabaseClient.auth.getSession();
    if (sess.data.session) options.headers['Authorization'] = 'Bearer ' + sess.data.session.access_token;
  }
  const resp = await fetch(url, options);
  // Read the body once, eagerly, so jsonSafe() is idempotent and never depends on
  // a clone that a later caller might have consumed.
  const bodyText = await resp.text();
  resp.jsonSafe = async () => {
    try { return JSON.parse(bodyText); }
    catch(e) {
      if (resp.status === 504 || resp.status === 502 || bodyText.indexOf('TIMEOUT') >= 0)
        return {error: 'Steget tog för lång tid. Försök igen.'};
      if (resp.status >= 500) return {error: 'Serverfel (' + resp.status + '). Försök igen.'};
      return {error: 'Oväntat svar från servern.'};
    }
  };
  return resp;
}

async function postJson(url, body) {
  if (url.startsWith('/api/') && !url.startsWith('/api/reports')) body = Object.assign({mode: state.mode}, body);
  const resp = await authFetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  return {ok: resp.ok, status: resp.status, data: await resp.jsonSafe()};
}

// A step that fails for a reason that can pass is tried again before the user
// is asked to redo it: a failure the server marks retryable (the model
// provider busy, unreachable or answering 5xx, all fast), a dropped
// connection (status 0) or the platform's 503. With ten or more people at the
// same step the provider will refuse some calls, and before this one refusal
// sent a user back to approve the gate again, re-running every part that had
// worked. Not retried: a model timeout (minutes already spent, and a new try
// is a new paid call), an answer that did not parse, our own faults (500,
// 422), the platform's 504, and answers about the request itself (401, 403,
// 413, the per-user limit 429). Those would fail the same way again.
function worthRetry(r) {
  return r.status === 0 || r.status === 503 || !!(r.status === 502 && r.data && r.data.retryable);
}
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
async function postRetrying(url, body, delays, onRetry) {
  const token = runToken;
  for (let attempt = 0; ; attempt++) {
    const r = await postJson(url, body)
      .catch(e => ({ok: false, status: 0, data: {error: 'Nätverksfel: ' + e.message}}));
    if (r.ok || !worthRetry(r) || attempt >= delays.length || token !== runToken) return r;
    if (onRetry) onRetry(attempt + 1);
    // Jitter, so parts that failed together do not all come back together.
    await sleep(delays[attempt] + Math.random() * 1000);
    if (token !== runToken) return r;
  }
}
const STEP_RETRY_MS = [4000];
const PART_RETRY_MS = [3000, 10000];
function stepStatus(step, label) {
  // A gate re-run says how it is going in its own line: the head of the
  // version on screen belongs to the snapshot a failed re-run puts back.
  const s = panelSection(step);
  const el = s && (s.querySelector('.step-sec-updating') || s.querySelector('.step-sec-status'));
  if (el) el.innerHTML = '<span class="mini-spin"></span>' + label;
}

// One pipeline step. Evidens is three phases (agents/evidens_split.py): a plan
// that lists the drivers, one call per driver in parallel, and a merge that
// checks them against each other. Each is its own request, so no single
// function run holds more than one model call. If any driver fails, the step
// fails: a merge over the drivers that happened to succeed would hand the
// calculation a total with a driver silently missing.
// `extra` goes along with the request: {feedback: true} on a re-run from the
// step's own gate, so the server can ask for a reply and a version apart
// (caia/feedback.py). Evidens has no such reply and leaves it out.
async function postStep(step, history, extra) {
  const token = runToken;
  const retrying = () => { if (token === runToken) stepStatus(step, 'försöker igen...'); };
  if (step !== 'evidens') return postRetrying('/api/' + step, Object.assign({history}, extra), STEP_RETRY_MS, retrying);
  const plan = await postRetrying('/api/evidens/plan', {history}, STEP_RETRY_MS, retrying);
  if (!plan.ok) return plan;
  // "Ny analys" while the plan was out: do not start N paid model calls
  // whose results the caller would throw away.
  if (token !== runToken) return {ok: false, data: {error: 'Avbruten'}};
  const drivers = plan.data.drivers || [];
  if (!drivers.length) return postRetrying('/api/evidens', {history}, STEP_RETRY_MS, retrying);
  let done = 0;
  const again = new Set();
  const showProgress = () => {
    if (token !== runToken) return;
    const tail = again.size ? ' (försöker igen med drivare ' + [...again].join(', ') + ')' : '';
    stepStatus('evidens', done + ' av ' + drivers.length + ' drivare...' + tail);
  };
  showProgress();
  // Each part is retried on its own, so one refused call costs that part a
  // second try, not every part a second run.
  const parts = await Promise.all(drivers.map(d =>
    postRetrying('/api/evidens/part', {history, driver: d.number}, PART_RETRY_MS,
                 () => { again.add(d.number); showProgress(); })
      .then(r => { done++; again.delete(d.number); showProgress(); return r; })));
  if (token !== runToken) return {ok: false, data: {error: 'Avbruten'}};
  const failed = drivers.filter((d, i) => !parts[i].ok);
  if (failed.length) {
    const why = failed.map(d => 'drivare ' + d.number + ' (' + (parts[drivers.indexOf(d)].data.error || 'okänt fel') + ')').join('; ');
    return {ok: false, data: {error: 'Antagandena kunde inte tas fram för ' + why + '. Steget avbröts så att kalkylen inte räknar på ett ofullständigt underlag. Försök igen.'}};
  }
  stepStatus('evidens', 'stämmer av drivarna mot varandra...');
  return postRetrying('/api/evidens/merge', {history, parts: parts.map(p => ({number: p.data.number, text: p.data.text}))},
                      STEP_RETRY_MS, retrying);
}

function showAuth() { document.getElementById('authOverlay').style.display = 'flex'; document.getElementById('appContainer').style.display = 'none'; }
function showApp() { document.getElementById('authOverlay').style.display = 'none'; document.getElementById('appContainer').style.display = 'flex'; }

// One mode at a time. Switching used to hide the message as well, and the
// sign-up path switched to login right after writing "Konto skapat", so a new
// user saw the message vanish and nothing else happen.
function setAuthMode(signup) {
  isSignup = signup;
  document.getElementById('authSubmitBtn').textContent = isSignup ? 'Skapa konto' : 'Logga in';
  document.getElementById('authToggleText').textContent = isSignup ? 'Har du redan konto?' : 'Inget konto?';
  document.getElementById('authToggleLink').textContent = isSignup ? 'Logga in' : 'Skapa konto';
  document.getElementById('authSignupHint').style.display = isSignup ? '' : 'none';
  document.getElementById('authForgot').style.display = isSignup ? 'none' : '';
  document.getElementById('authPassword').autocomplete = isSignup ? 'new-password' : 'current-password';
}
function toggleAuthMode(e) {
  e.preventDefault(); setAuthMode(!isSignup); authNote(null); showResend(false);
}
// kind 'info' is a plain message (what happens next), anything else an error.
function authNote(text, kind) {
  const el = document.getElementById('authError');
  if (!text) { el.style.display = 'none'; return; }
  el.textContent = text;
  el.classList.toggle('info', kind === 'info');
  el.style.display = 'block';
}
function showResend(on) { document.getElementById('authResend').style.display = on ? 'block' : 'none'; }

// Supabase answers in English; the page does not. First match wins, so the
// mail limit comes before the general rate limit.
const AUTH_MESSAGES = [
  [/invalid login credentials/i, 'Fel e-postadress eller lösenord.'],
  [/email not confirmed/i, 'Kontot är inte bekräftat än. Öppna länken i mejlet, logga sedan in. Hittar du inget mejl: skicka ett nytt nedan.'],
  [/already registered|already been registered/i, 'Det finns redan ett konto med den adressen. Logga in i stället.'],
  [/password should be at least/i, 'Lösenordet är för kort. Det ska ha minst 6 tecken.'],
  [/should be different from the old/i, 'Välj ett annat lösenord än det gamla.'],
  [/only request this after|security purposes/i, 'Vänta en minut innan du ber om ett nytt mejl.'],
  [/email rate limit/i, 'Det går inte att skicka fler mejl just nu. Försök igen om en stund.'],
  [/rate limit|too many requests/i, 'För många försök. Vänta en stund och försök igen.'],
  [/signups? not allowed|signup(s)? (are )?disabled/i, 'Det går inte att skapa konton här. Kontakta den som driver CAIA.'],
  [/unable to validate email|invalid email/i, 'E-postadressen ser inte ut att stämma.'],
];
function authMessage(err) {
  const text = (err && err.message) || '';
  const hit = AUTH_MESSAGES.find(([re]) => re.test(text));
  return hit ? hit[1] : 'Inloggningen misslyckades: ' + text;
}

// What a link in a mail from Supabase brought back in the address, read before
// the client is created so nothing has acted on it yet. A confirmation link a
// mail scanner already opened comes back with error_code=otp_expired. A
// password link carries token_hash and type=recovery in the query (a project
// template that builds the link itself), or an access token with
// type=recovery in the hash (the Supabase default). A successful confirmation leaves the hash alone: the
// client reads its token from there.
const AUTH_RETURN = (() => {
  const out = {error: null, recoveryHash: null, recoveryImplicit: false};
  try {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const query = new URLSearchParams(window.location.search);
    out.error = hash.get('error_code') || query.get('error_code') || hash.get('error') || query.get('error') || null;
    if (query.get('type') === 'recovery' && query.get('token_hash')) out.recoveryHash = query.get('token_hash');
    out.recoveryImplicit = hash.get('type') === 'recovery' && !!hash.get('access_token');
    if (out.error || out.recoveryHash) history.replaceState(null, '', window.location.pathname);
  } catch (e) { /* an address the parser cannot read is a normal visit */ }
  return out;
})();
function returnErrorMessage(code) {
  if (code === 'otp_expired') return 'Länken i mejlet har redan använts eller gått ut. Prova att logga in. Står det att kontot inte är bekräftat: fyll i din adress och skicka ett nytt mejl.';
  return 'Länken i mejlet fungerade inte. Prova att logga in, eller fyll i din adress och skicka ett nytt mejl.';
}

async function handleAuth() {
  const email = document.getElementById('authEmail').value.trim();
  const password = document.getElementById('authPassword').value;
  const btn = document.getElementById('authSubmitBtn');
  if (!email || !password) { authNote('Fyll i e-post och lösenord.'); return; }
  authNote(null); showResend(false);
  btn.disabled = true; btn.textContent = '...';
  try {
    let res;
    // Without emailRedirectTo the confirmation link goes to the Supabase
    // project's Site URL, which may be another app sharing the project. The
    // address must also be listed under Auth > URL Configuration > Redirect URLs.
    if (isSignup) res = await supabaseClient.auth.signUp({email, password, options: {emailRedirectTo: window.location.origin}});
    else res = await supabaseClient.auth.signInWithPassword({email, password});
    if (res.error) {
      authNote(authMessage(res.error));
      if (/email not confirmed/i.test(res.error.message || '')) showResend(true);
    } else if (isSignup && !res.data.session) {
      // With confirmation on, Supabase answers a sign-up for an address that
      // already has an account with a success and no identities, and sends
      // nothing. Without this the page promised a mail that never came.
      const ids = res.data.user && res.data.user.identities;
      setAuthMode(false);
      if (Array.isArray(ids) && ids.length === 0) {
        authNote('Det finns redan ett konto med den adressen. Logga in, eller välj Glömt lösenordet.');
      } else {
        authNote('Kontot är skapat. Öppna länken i mejlet till ' + email + ' och logga sedan in här. Kolla skräpposten om det dröjer.', 'info');
        showResend(true);
      }
    }
  } catch(e) { authNote('Fel: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = isSignup ? 'Skapa konto' : 'Logga in'; }
}

async function resendConfirmation(e) {
  e.preventDefault();
  const email = document.getElementById('authEmail').value.trim();
  if (!email) { authNote('Fyll i din e-postadress först.'); return; }
  try {
    const {error} = await supabaseClient.auth.resend({type: 'signup', email, options: {emailRedirectTo: window.location.origin}});
    if (error) authNote(authMessage(error));
    else authNote('Ett nytt mejl är på väg till ' + email + '. Kolla skräpposten om det inte kommer inom några minuter.', 'info');
  } catch(err) { authNote('Fel: ' + err.message); }
}

async function forgotPassword(e) {
  e.preventDefault();
  const email = document.getElementById('authEmail').value.trim();
  if (!email) { authNote('Fyll i din e-postadress och klicka på Glömt lösenordet igen.'); return; }
  try {
    // A project mail template that builds the link as the redirect address
    // plus "&token_hash=..." needs an address with a query already: ?reset=1.
    const {error} = await supabaseClient.auth.resetPasswordForEmail(email, {redirectTo: window.location.origin + '/?reset=1'});
    if (error) authNote(authMessage(error));
    else authNote('Finns det ett konto med ' + email + ' får du ett mejl med en länk där du väljer ett nytt lösenord.', 'info');
  } catch(err) { authNote('Fel: ' + err.message); }
}

// While the new-password form is up, a sign-in from the recovery link must not
// take the user into the app before they have chosen a password.
let settingPassword = false;
function showNewPassword() {
  settingPassword = true;
  showAuth();
  document.getElementById('authForm').style.display = 'none';
  document.getElementById('newPasswordForm').style.display = '';
  document.getElementById('newPassword').focus();
}
async function saveNewPassword() {
  const pw = document.getElementById('newPassword').value;
  const errEl = document.getElementById('newPasswordError');
  const btn = document.getElementById('newPasswordBtn');
  const fail = (text) => { errEl.textContent = text; errEl.style.display = 'block'; };
  if (pw.length < 6) { fail('Lösenordet ska ha minst 6 tecken.'); return; }
  btn.disabled = true;
  try {
    const {error} = await supabaseClient.auth.updateUser({password: pw});
    if (error) { fail(authMessage(error)); return; }
    settingPassword = false;
    document.getElementById('newPasswordForm').style.display = 'none';
    document.getElementById('authForm').style.display = '';
    const {data: {session}} = await supabaseClient.auth.getSession();
    if (session) onLogin(session); else authNote('Lösenordet är bytt. Logga in med det nya.', 'info');
  } catch(e) { fail('Fel: ' + e.message); }
  finally { btn.disabled = false; }
}

async function signOut() { if (supabaseClient) await supabaseClient.auth.signOut(); }

// The page keeps an analysis through a sign-out, so that the same person can
// sign in again and go on (a session can run out at a gate). Another account
// signing in on the same page used to find it too: the chat, the steps and
// the report of the person before.
let lastUserId = null;
async function onLogin(session) {
  if (lastUserId && session.user.id !== lastUserId) {
    resetAll();
    // The saved list of the person before stood until the new one had loaded.
    const list = document.getElementById('savedList'); if (list) list.innerHTML = '';
  }
  lastUserId = session.user.id;
  currentUser = session.user;
  const ue = document.getElementById('userEmail'); if (ue) ue.textContent = currentUser.email;
  showApp(); loadSavedList();
}

if (HAS_SUPABASE && SUPABASE_URL && SUPABASE_ANON_KEY) {
  supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  (async () => {
    if (AUTH_RETURN.recoveryHash) {
      const {error} = await supabaseClient.auth.verifyOtp({token_hash: AUTH_RETURN.recoveryHash, type: 'recovery'});
      if (!error) showNewPassword();
      else { showAuth(); authNote('Länken för nytt lösenord har redan använts eller gått ut. Fyll i din adress och be om en ny med Glömt lösenordet.'); }
    }
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (AUTH_RETURN.recoveryImplicit && session) showNewPassword();
    else if (settingPassword) { /* the form is up; saveNewPassword signs in */ }
    else if (session) onLogin(session);
    else { showAuth(); if (AUTH_RETURN.error && !AUTH_RETURN.recoveryHash) { authNote(returnErrorMessage(AUTH_RETURN.error)); showResend(true); } }
    supabaseClient.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY') showNewPassword();
      else if (event === 'SIGNED_IN' && session && !currentUser && !settingPassword) onLogin(session);
      else if (event === 'SIGNED_OUT') { currentUser = null; settingPassword = false; showAuth(); }
    });
  })();
}

/* ---------- saved reports ---------- */
function toggleSavedMenu() {
  const m = document.getElementById('savedMenu');
  const show = m.style.display !== 'block';
  m.style.display = show ? 'block' : 'none';
  if (show) loadSavedList();
}

async function loadSavedList() {
  if (!HAS_SUPABASE || !currentUser) return;
  try {
    const r = await authFetch('/api/reports');
    const rows = await r.jsonSafe();
    const el = document.getElementById('savedList');
    if (r.status === 403) {
      // Signed in, but not on CAIA_ALLOWED_EMAILS: say it at the door, not
      // at the first analysis step.
      await signOut();
      authNote(rows.error || 'Kontot saknar behörighet till CAIA.');
      return;
    }
    if (!r.ok) { el.innerHTML = '<div class="saved-empty">Kunde inte hämta sparade analyser: ' + escapeHtml(rows.error || ('fel ' + r.status)) + '</div>'; return; }
    if (!Array.isArray(rows) || rows.length === 0) { el.innerHTML = '<div class="saved-empty">Inga sparade analyser &#xE4;n.</div>'; return; }
    el.innerHTML = '';
    rows.forEach(row => {
      const net = (row.key_metric && (row.key_metric.net != null ? row.key_metric.net : row.key_metric.cons));
      const metric = (net != null) ? keyMetricText(net, row.key_metric) : '';
      const d = escapeHtml((row.created_at || '').slice(0,10));
      const item = document.createElement('div');
      item.className = 'saved-item';
      item.innerHTML = '<div class="si-name">' + escapeHtml(row.action_name || 'Namnlös') +
        '</div><div class="si-meta">' + d + (metric ? ' · ' + escapeHtml(metric) : '') + '</div>';
      item.addEventListener('click', () => openSaved(row.id));  // no inline onclick = no attr injection
      el.appendChild(item);
    });
  } catch(e) {
    document.getElementById('savedList').innerHTML = '<div class="saved-empty">Kunde inte hämta sparade analyser: ' + escapeHtml(e.message) + '</div>';
  }
}

let openSavedSeq = 0;
async function openSaved(id) {
  document.getElementById('savedMenu').style.display = 'none';
  // Opening a saved report clears the panel a live analysis draws into, and
  // left the chat standing at a gate whose step was gone.
  // The analysis goes only once the saved one has arrived: a failed fetch
  // must not cost the work it was asked to replace.
  const discard = analysisInProgress();
  if (discard && !confirmDiscard()) return;
  // The answer can be slow. Only the last report asked for is shown, and not
  // after "Ny analys": two clicks used to show whichever answered last.
  const seq = ++openSavedSeq, token = runToken;
  try {
    const r = await authFetch('/api/reports/' + encodeURIComponent(id));
    const row = await r.jsonSafe();
    if (seq !== openSavedSeq || token !== runToken) return;
    if (!r.ok || !row || !row.formatted_report) { addSystem('Kunde inte öppna analysen: ' + ((row && row.error) || 'okänt fel'), true); return; }
    // An analysis begun while the report was on its way was never asked
    // about, so the report does not replace it.
    if (!discard && analysisInProgress()) return;
    if (discard) resetAll();
    state.reportMarkdown = row.formatted_report;
    // Another report: the parts start closed again. Its own QA status is in
    // its text, not in the last live run's verdict.
    reportOpen.clear();
    // The number above the report is this row's or none. A row without one
    // (the calc fell back to the model) used to stand under the number of
    // the analysis or report shown before it.
    hideHero();
    showReport(row.formatted_report, row.key_metric, {name: row.action_name});
    // The saved row has no mode; a follow-up report says so under its title.
    setHeroLabel(/Analysläge:\s*uppföljning/i.test(row.formatted_report) ? 'uppfoljning' : 'potential', null,
                 row.key_metric && row.key_metric.year);
    // Saved report = no live trail; show only the report.
    document.getElementById('reportActions').style.display = '';
    document.getElementById('analysisFeed').innerHTML = '';
    document.getElementById('analysisFeed').style.display = 'none';
    document.getElementById('trailToggle').style.display = 'none';
    document.getElementById('heroScenario').style.display = 'none';
    heroChartData = null;
    document.getElementById('heroWarn').style.display = 'none';  // belonged to the last live run
    updateProgress('rapport', true);
  } catch(e) { addSystem('Fel vid öppning: ' + e.message, true); }
}

/* ---------- chat helpers ---------- */
function escapeHtml(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
// Same rule as the calc text (calc.engine._fmt): one decimal below 10 ton,
// so a small measure does not show as "0 ton".
function fmt(n) {
  if (Math.abs(n) < 10 && Math.round(n * 10) !== 0)
    return n.toLocaleString('sv-SE', {minimumFractionDigits: 1, maximumFractionDigits: 1});
  return (Math.round(n) || 0).toLocaleString('sv-SE');  // || 0: no "-0"
}
// breaks:true -> single newlines render as line breaks, so the intake profile's
// per-field lines (*Namn:* ... \n *Beskrivning:* ...) don't collapse into one block.
// Model output is rendered as HTML, so what may survive is listed rather than
// what may not. A list of forbidden tags let <video poster>, <audio src> and
// <source src> through (security review S2): each made the browser fetch an
// address with no click, and a manipulated model can put the analysis in that
// address. These are the elements marked writes for an analysis. Attributes:
// href, plus marked's own `align` (table columns) and `start` (a numbered list
// that resumes after a paragraph); none of them can carry an address except
// href, and href may only be https: or mailto:. DOMPurify tests every allowed
// attribute it does not know as safe against that address pattern, so `3`
// and `left` failed it and the two vanished; ADD_URI_SAFE_ATTR says they hold
// no address.
const SANITIZE = {
  ALLOWED_TAGS: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr', 'ul', 'ol', 'li',
                 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'strong', 'b', 'em', 'i',
                 'del', 's', 'sub', 'sup', 'code', 'pre', 'blockquote'],
  ALLOWED_ATTR: ['href', 'align', 'start'],
  ADD_URI_SAFE_ATTR: ['align', 'start'],
  ALLOWED_URI_REGEXP: /^(?:https:\/\/|mailto:)/i,
  ALLOW_DATA_ATTR: false,
  ALLOW_ARIA_ATTR: false,
};
// A link in a report opens in a tab of its own, so the analysis stays open,
// and the other site is told neither where the click came from nor given a
// handle on this tab. Set here because the list above lets neither attribute
// through from model text.
function markLinks(frag) {
  for (const a of frag.querySelectorAll('a[href]')) {
    if (!/^https:/i.test(a.getAttribute('href'))) continue;
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
  }
  return frag;
}
// A report is model text followed by sections the program wrote: the
// calculation appendix and Talens ursprung. Each is read as a document of
// its own. Read as one, a model text ending in "<!--" or "<style>" took the
// program's sections with it, and the page showed the report without them
// (re-review 2026-10-07).
const PROGRAM_HEADINGS = {{ program_headings|tojson }};
function markdownParts(md) {
  const parts = [[]];
  for (const line of (md || '').split('\n')) {
    if (PROGRAM_HEADINGS.includes(line.trim()) && parts[parts.length - 1].length) parts.push([]);
    parts[parts.length - 1].push(line);
  }
  // Split on the raw text (the headings are matched whole), worded after.
  return parts.map(p => plainTerms(p.join('\n')));
}
// Step 2 is called Utsläppskällor on the page. Its prompt, and the prompts of
// the steps that read it, still say EMAP (no framework by that name exists;
// 2026-10-13), and so does the text the model writes. The prompts and
// the history stay as they are: the next step reads the field names, and a
// prompt change needs reference runs. What the person reads is put in words
// here instead, in everything drawn from model text and in the download.
// A table cell ("| BAU-trend") starts one too.
function startsSentence(before) { return /(^|\n|[.!?:]\s|\|\s)[\s#*>\d.)\-]*$/.test(before); }
function plainTerms(text) {
  const say = (word) => (m, ...rest) => {
    const whole = rest[rest.length - 1], at = rest[rest.length - 2];
    const w = typeof word === 'function' ? word(m, ...rest) : word;
    // Only the last stretch decides, so a long text costs nothing per hit.
    const before = (at > 80 ? 'x' : '') + whole.slice(Math.max(0, at - 80), at);
    return startsSentence(before) ? w.charAt(0).toUpperCase() + w.slice(1) : w;
  };
  return (text || '')
    .replace(/\bEMAP-ANALYS \(FÖRENKLAD VARIANT\)/g, 'Utsläppskällor')
    // The evidens step's opening line: "de godkända EMAP- och Baslinje & BAU-analyserna".
    .replace(/\bEMAP- och Baslinje(?: & BAU)?-analys(erna|er)\b/g, say((m, e) => 'analys' + e + ' av utsläppskällor och baslinje'))
    // The step's own heading: "EMAP-analys av åtgärd: Cykelbana".
    .replace(/\bEMAP-analys av åtgärd:/gi, say('utsläppskällor för åtgärd:'))
    // Singular on purpose: the sentence around it ("... är godkänd") was
    // written for a singular noun.
    .replace(/\bEMAP-analys(en|ens|er|erna)?(?![\wåäö])/gi, say((m, end) =>
      ({en: 'analysen av utsläppskällor', ens: 'utsläppsanalysens', er: 'analyser av utsläppskällor', erna: 'analyserna av utsläppskällor'})[(end || '').toLowerCase()] || 'analys av utsläppskällor'))
    .replace(/\bEMAP-(drivar(?:e|en|na|nas))(?![\wåäö])/gi, say((m, w) => w.toLowerCase()))
    .replace(/\bEMAP-kategorisering(en|ar)?(?![\wåäö])/gi, say((m, end) => 'klassning' + (end || '').toLowerCase()))
    .replace(/\bEMAP_([A-Za-zÅÄÖåäö])/g, '$1')
    // The prompt's own phrase ("hur åtgärden ser ut i EMAP-termer").
    .replace(/\b(i) EMAP-termer(?![\wåäö])/gi, '$1 analysen av utsläppskällor')
    .replace(/\bEMAP-steg(et|ets)?(?![\wåäö])/gi, say((m, end) => 'steget Utsläppskällor' + ((end || '').toLowerCase() === 'ets' ? 's' : '')))
    // Any other compound keeps its own word: "EMAP-bedömning" is a "bedömning".
    .replace(/\bEMAP-([a-zåäö]+)/g, say((m, w) => w))
    .replace(/\bEMAP(?!\w)/g, say('analysen av utsläppskällor'))
    .split(/(https?:\/\/[^\s)\]>]+)/).map((part, i) => i % 2 ? part : plainWords(part, say)).join('');
}
// The models write their working vocabulary into what the person reads: field
// names (Scenario_medel, ΔE_2030_total), parameter codes (TR_mode_share_car),
// BAU, A0, ΔA and numbers as 7,8e7. A miljöstrateg trying the tool stopped at
// every one of them (2026-10-13). They are put in words here, in what
// is shown and downloaded only: the history the next step reads keeps them, so
// no number and no prompt changes. Links are left alone (split above).
const PARAM_NAMES = {{ param_names|tojson }};
// The models write the codes in capitals too (TR_MEDIAN_TRIP_LENGTH_KM).
const PARAM_NAMES_ANY_CASE = Object.keys(PARAM_NAMES).reduce((o, k) => { o[k.toLowerCase()] = PARAM_NAMES[k]; return o; }, {});
// Each replacement is read in the sentence it lands in, so the order matters:
// the longer forms (BAU-EF, g_A-spannet, ΔE:s) go before the bare code, and a
// few cleanups after the words are in (two "utan åtgärden" in a row).
function plainWords(text, say) {
  const name = (n) => /^[A-ZÅÄÖ][a-zåäö]/.test(n) ? n.charAt(0).toLowerCase() + n.slice(1) : n;
  return readableNumbers(text
    // The calculation appendix numbers the drivers it computed and puts the
    // name after it, and the name already says "Drivare 4: ". The name's number
    // is the one the rest of the report uses.
    .replace(/\bDrivare \d+: (Drivare \d+: )/g, '$1')
    // A parameter code or a data file from the library, by its own name.
    .replace(/\b[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+\b/g, (m, ...rest) =>
      Object.prototype.hasOwnProperty.call(PARAM_NAMES_ANY_CASE, m.toLowerCase())
        ? say(name(PARAM_NAMES_ANY_CASE[m.toLowerCase()]))(m, ...rest) : m)
    // The report template's fields.
    .replace(/ΔE_kumulativt_till_m[åa]l[åa]r(?:_total)?/g, say('sammanlagd effekt till målåret'))
    .replace(/ΔE_(\d{4})(?:_total)?/g, say((m, y) => 'effekt ' + y))
    .replace(/\bScenario_medel\b/g, say('medelscenariot'))
    .replace(/\bScenario_min\b/g, say('det försiktiga scenariot'))
    .replace(/\bScenario_max\b/g, say('det optimistiska scenariot'))
    .replace(/\b(Kort tolkning)_(?:medel|min|max)\b/g, '$1')
    .replace(/\bTidsprofil_[Aa]tg[äa]rd\b/g, say('tidsprofil för åtgärden'))
    // The calculation's own names (the appendix, the QA).
    .replace(/\bEF_BAU\b/g, say('utsläppsfaktorn utan åtgärden'))
    .replace(/\bA_BAU\b/g, say('aktiviteten utan åtgärden'))
    .replace(/\bE_BAU\b/g, say('utsläppen utan åtgärden'))
    .replace(/\bE_[Åå]tgärd\b/g, say('utsläppen med åtgärden'))
    .replace(/(utan|med) åtgärden\(t\)/g, '$1 åtgärden år t')
    .replace(/\bBAU_hantering\b/g, say('hantering av läget utan åtgärden'))
    .replace(/\bBAU g_(?:A|EF)\b/g, say('trenden utan åtgärden'))
    .replace(/\bg_A-([a-zåäö]+)/g, say((m, w) => w + ' för aktivitetens trend'))
    .replace(/\bg_EF-([a-zåäö]+)/g, say((m, w) => w + ' för utsläppsfaktorns trend'))
    .replace(/\bg_A\b/g, say('aktivitetens trend'))
    .replace(/\bg_EF\b/g, say('utsläppsfaktorns trend'))
    .replace(/\bTerritoriell_faktor(n|er|erna)?\b/g, say((m, e) => 'territoriell faktor' + (e || '')))
    .replace(/\bKonsumtion_faktor(n|er|erna)?\b/g, say((m, e) => 'konsumtionsfaktor' + (e || '')))
    .replace(/\bOverlap_faktor(n|er|erna)?\b/g, say((m, e) => 'överlappsfaktor' + (e || '')))
    .replace(/[öo]verlapp_risk/g, say('risk för dubbelräkning'))
    .replace(/\bGas_typ\b/g, say('gastyp'))
    .replace(/\b(?:Ar_galler|År_gäller)\b/g, say('giltighetsår'))
    .replace(/ΔA_([a-zåäö]+(?:_[a-zåäö]+)*)/g, say((m, w) => 'ändrad aktivitet (' + w.replace(/_/g, ' ') + ')'))
    .replace(/\b(A|EF)_([a-zåäö]+)\b/g, say((m, c, w) => (c === 'A' ? 'aktivitet' : 'utsläppsfaktor') + ' (' + w + ')'))
    // Any other field name: its words.
    .replace(/\b([A-ZÅÄÖ]?[a-zåäö]+)((?:_[A-Za-zÅÄÖåäö]+)+)\b/g, (m, a, b) => a + b.replace(/_/g, ' '))
    // Brackets the template puts around a number: "[5 160 ton CO2e/år]".
    .replace(/\[(\d[^\[\]\n]*)\](?!\()/g, '$1')
    .replace(/\bCoVe[- ]QA\b|\bCoVe\b/g, say('kvalitetsgranskningen'))
    .replace(/\bBaslinje & BAU\b/g, 'Baslinje')
    .replace(/\btailpipe-EF\b/g, say('utsläppsfaktorn för avgaserna'))
    .replace(/\btailpipe\b/g, say('utsläpp från avgasröret'))
    .replace(/\bKOMM-([a-zåäö]+)/g, say((m, w) => w + ' för kommunikationsinsatser'))
    .replace(/\blocalContext\b/g, say('kommunens data'))
    // The models' word for a driver's block in the text, which reads as the
    // classifieds site.
    .replace(/\bBlocket\b/g, 'Drivaren')
    // The source tag: a tag after a value reads as "(antagande)", inside
    // the model's own parentheses as the word.
    .replace(/[\[(]ANTAGANDE[\])]/g, '(antagande)')
    .replace(/([^,(\s])\s+ANTAGANDE(?![\wåäö:)])/g, '$1 (antagande)')
    .replace(/\bANTAGANDE\b/g, say('antagande'))
    .replace(/\bBAU-EF\b/g, say('utsläppsfaktorn utan åtgärden'))
    .replace(/\bBAU-trend A\b/g, say('trend utan åtgärden för aktiviteten'))
    .replace(/\bBAU-trend \(?(?:aktivitetens|utsläppsfaktorns) trend\)?/g, say('trend utan åtgärden'))
    // A genitive does not take "utan åtgärden" after it: "baslinjetrendernas".
    .replace(/\bBAU-([a-zåäö]+(?:ens|ernas|arnas|ornas|ets|nas))\b/g, say((m, w) => 'baslinje' + w))
    .replace(/\bBAU- och ([a-zåäö]+)/g, say((m, w) => 'baslinje- och ' + w))
    .replace(/\bBAU-([a-zåäö]+)/g, say((m, w) => w + ' utan åtgärden'))
    .replace(/\b(ett|ett annat) BAU\b/g, say((m, d) => d + ' läge utan åtgärden'))
    .replace(/\bBAU\b/g, say('läget utan åtgärden'))
    .replace(/ΔE:s(?![\wåäö])/g, say('effektens'))
    // "Ett ΔA på −21,6 %", "samma ΔE", "ΔA-spann": the noun as the sentence needs it.
    .replace(/\b([Ee])tt ΔA(?![\wåäö])/g, '$1n ändrad aktivitet')
    .replace(/\b(samma|högre|lägre|större|mindre|ingen|en) ΔE(?![\wåäö])/g, '$1 effekt')
    .replace(/Δ(A|EF|E)-([a-zåäö]+)/g, say((m, c, w) => w + ' för ' + ({A: 'ändrad aktivitet', EF: 'ändrad utsläppsfaktor', E: 'effekten'})[c]))
    .replace(/ΔEF(?![\wåäö])/g, say('ändrad utsläppsfaktor'))
    .replace(/ΔA(?![\wåäö])/g, say('ändrad aktivitet'))
    .replace(/ΔE(?![\wåäö])/g, say('effekten'))
    // "aktivitet (A0) och emissionsfaktor (EF0)": the word is already there.
    .replace(/ \((?:A0|EF0)\)/g, '')
    // ...and "aktivitet A0 och emissionsfaktor EF0" without the brackets, which
    // read "aktivitet nulägesaktivitet och emissionsfaktor utsläppsfaktor i
    // nuläget" (2026-10-14).
    .replace(/\b(aktivitet(?:en|ens)?|emissionsfaktor(?:n|ns)?|utsläppsfaktor(?:n|ns)?) (?:A0|EF0)(?![\wåäö])/g, '$1')
    .replace(/\b(av|i|för|med) EF0(?![\wåäö])/g, '$1 utsläppsfaktorn i nuläget')
    .replace(/\b(av|i|för|med) A0(?![\wåäö])/g, '$1 nulägesaktiviteten')
    .replace(/\bEF0(?![\wåäö])/g, say('utsläppsfaktor i nuläget'))
    .replace(/\bA0(?![\wåäö])/g, say('nulägesaktivitet'))
    .replace(/\bEF:s(?![\wåäö])/g, say('utsläppsfaktorns'))
    .replace(/\bEF-(värde[a-zåäö]*)/g, (m, w) => w + ' på utsläppsfaktorn')
    .replace(/\bEF-([a-zåäö]+)/g, say((m, w) => 'utsläppsfaktor' + w))
    .replace(/\bdet ([a-zåäö]+e) EF(?![\wåäö])/g, say((m, a) => 'den ' + a + ' utsläppsfaktorn'))
    // "EF följer BAU", "ingår i EF": the factor. "privatbilens EF", "låg EF":
    // the noun alone.
    .replace(/\b(i|på|av|om|och|att|sänker|höjer|påverkar|ändrar) EF(?![\wåäö])/g, '$1 utsläppsfaktorn')
    .replace(/\bEF(?![\wåäö])/g, (m, at, whole) => startsSentence(whole.slice(Math.max(0, at - 80), at)) ? 'Utsläppsfaktorn' : 'utsläppsfaktor')
    .replace(/\b[Rr]each\b/g, say('räckvidd'))
    .replace(/\blocalData\b/g, say('kommunens data'))
    // Cleanups once the words are in.
    .replace(/utan åtgärden(?: utan åtgärden| \(utan åtgärd(?:en)?\))+/g, 'utan åtgärden')
    .replace(/(utsläpp från avgasröret|från avgasröret) \(utsläpp från avgasröret\)/g, '$1')
    .replace(/\bnivån utan åtgärden för A\b/g, 'aktivitetens nivå utan åtgärden')
    // The activity alone as a letter: "A ≈ 78 miljoner", "spann i A (0,8/1,0)".
    .replace(/\bA ≈/g, 'aktivitet ≈')
    .replace(/\bi A \(/g, 'i aktiviteten (')
    .replace(/\b([Dd]et försiktiga scenariot|[Dd]et optimistiska scenariot|[Mm]edelscenariot) \((?:försiktigt|optimistiskt|medel|min|max|troligt)\)/g, '$1')
    // A share written with a decimal point ("överlappet är 0.6"). Only 0.x and
    // 1.0: a "1.2" may be a section number.
    .replace(/([^#\s]\s|[(=\/≈~])([01])\.(\d+)(?!\d|\.\d)/g, (m, b, i, d) => i === '1' && /[^0]/.test(d) ? m : b + i + ',' + d));
}
function plainTermsDeep(v) {
  if (typeof v === 'string') return plainTerms(v);
  if (Array.isArray(v)) return v.map(plainTermsDeep);
  if (v && typeof v === 'object') { const o = {}; for (const k in v) o[k] = plainTermsDeep(v[k]); return o; }
  return v;
}
// marked reads the * _ ~ ` marks of one paragraph in a time that grows with
// the square of how many it leaves unmatched: 50 000 characters of lines that
// start with "_" took 30 s and froze the tab (security review S42; marked 14.1
// and 18.1 alike). A block between two blank lines with more than
// EMPHASIS_MARKS_MAX of them has them written as character references, which
// marked reads in linear time and the page shows as the same characters. A
// backslash escape is no cure: marked is slow on those too.
// The block is cut at blank lines only, the one boundary no paragraph, list
// item, cell or heading reaches across: cutting also at list items, table
// rows, headings or code fences means guessing which of them marked agrees
// are one, and each wrong guess ("|x" or "2." inside a paragraph, a fence
// inside a list item or an HTML block) let a hostile text through. The cost
// is that a code block over the limit shows the references as written. In
// 433 saved model texts from CAIA runs no block had more than 134, and only
// 4 had code at all. At 200 marked takes at most about 8 ms over a block, so
// 100 000 characters of blocks just under the limit take under a second.
// marked has one more square, without any marks: a list item whose lines run
// on with no blank line between (120 000 characters took 7.8 s, marked 18.1
// alike). A block of more than BLOCK_LINES_MAX lines gets a blank line after
// every BLOCK_LINES_MAX; the most in the 433 texts was 47.
const EMPHASIS_MARKS_MAX = 200;
const BLOCK_LINES_MAX = 300;
const MARK_REF = {'*': '&#42;', '_': '&#95;', '~': '&#126;', '`': '&#96;'};
const LIST_ITEM = /^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)/;
function tameMarkdown(md) {
  // marked reads \r\n and a lone \r as a line break; counted as one line, a
  // list item of 60 000 \r-lines took 13 s.
  md = md.replace(/\r\n?/g, '\n');
  // marked's own blank line: spaces and tabs only, not every \s.
  return md.split(/(\n[ \t]*\n)/).map(block => {
    let lines = block.split('\n');
    if ((block.match(/[*_~`]/g) || []).length > EMPHASIS_MARKS_MAX) lines = lines.map(line => {
      // A bullet stays a bullet; it is no emphasis mark to marked.
      const lead = (line.match(LIST_ITEM) || [''])[0];
      return lead + line.slice(lead.length).replace(/[*_~`]/g, m => MARK_REF[m]);
    });
    const chunks = [];
    for (let i = 0; i < lines.length; i += BLOCK_LINES_MAX) chunks.push(lines.slice(i, i + BLOCK_LINES_MAX).join('\n'));
    return chunks.join('\n\n');
  }).join('');
}
// The one place model text is sanitised; both renderers below go through it.
// A part the libraries cannot read (marked gives up on a few thousand nested
// quotes, DOMPurify returns nothing for a page that opens with <frameset>) is
// shown as the text it is: a throw here failed the whole step, and every new
// try cost the model calls again.
function sanitizedFragment(md) {
  const out = document.createDocumentFragment();
  for (const part of markdownParts(md)) {
    let frag = null;
    try {
      frag = DOMPurify.sanitize(marked.parse(tameMarkdown(part), {breaks: true}),
                                Object.assign({RETURN_DOM_FRAGMENT: true}, SANITIZE));
    } catch (e) { frag = null; }
    if (frag) { out.appendChild(markLinks(frag)); continue; }
    const plain = document.createElement('p');
    plain.style.whiteSpace = 'pre-wrap';
    plain.textContent = part;
    out.appendChild(plain);
  }
  return out;
}
function fragmentHtml(frag) { const d = document.createElement('div'); d.appendChild(frag); return d.innerHTML; }
function renderMarkdown(md) { return fragmentHtml(sanitizedFragment(md)); }
// A reply is read from its first line. The first reply after the user's last
// move (a message or an approval) is where reading starts, and until they move
// again the chat never scrolls its top out of view: a long answer used to land
// on its last line, and what follows it (a status line, a second reply) pushed
// it further up.
let readFrom = null;
function chatScrollTarget(c, anchor) {
  const bottom = Math.max(0, c.scrollHeight - c.clientHeight);
  if (!anchor || !c.contains(anchor)) return bottom;
  const top = anchor.getBoundingClientRect().top - c.getBoundingClientRect().top + c.scrollTop - 12;
  return Math.max(0, Math.min(bottom, top));
}
function scrollChat() { const c = document.getElementById('chatMessages'); c.scrollTop = chatScrollTarget(c, readFrom); }

function addUser(text) {
  const d = document.createElement('div'); d.className = 'msg-user';
  d.innerHTML = escapeHtml(text).replace(/\n/g,'<br>');
  readFrom = null;
  document.getElementById('chatMessages').appendChild(d); scrollChat();
}
function addVoice(md, agentTag) {
  const d = document.createElement('div'); d.className = 'voice-aida';
  // The tag is the step's key; step 2's key is still emap.
  const shown = agentTag === 'emap' ? 'utsläppskällor' : agentTag;
  const tag = shown ? ('<span class="agent">· ' + escapeHtml(shown) + '</span>') : '';
  d.innerHTML = '<div class="voice-label">CAIA ' + tag + '</div><div class="voice-body">' + renderMarkdown(md) + '</div>';
  const c = document.getElementById('chatMessages');
  c.appendChild(d);
  if (!readFrom || !c.contains(readFrom)) readFrom = d;
  scrollChat();
}
function addSystem(text, isErr) {
  const d = document.createElement('div'); d.className = 'msg-system' + (isErr ? ' err' : '');
  d.innerHTML = isErr ? escapeHtml(text) : ('<span class="check">✓</span> ' + escapeHtml(text));
  document.getElementById('chatMessages').appendChild(d); scrollChat();
}
function addSpinner(label) {
  const d = document.createElement('div'); d.className = 'spinner-container'; d.id = 'curSpinner';
  d.innerHTML = '<div class="spinner"></div><span class="spinner-label">' + label + '</span>';
  document.getElementById('chatMessages').appendChild(d); scrollChat();
}
function removeSpinner() { const s = document.getElementById('curSpinner'); if (s) s.remove(); }
function setInputEnabled(b) { document.getElementById('chatInput').disabled = !b; document.getElementById('btnSend').disabled = !b; }
function showApprove(b) { document.getElementById('approveArea').style.display = b ? '' : 'none'; }

function updateProgress(currentStep, done) {
  const curIdx = STEPS.indexOf(currentStep);
  document.querySelectorAll('.progress-step').forEach(el => {
    const idx = STEPS.indexOf(el.dataset.step);
    el.classList.remove('active','done');
    if (done && idx <= curIdx) el.classList.add('done');
    else if (idx < curIdx) el.classList.add('done');
    else if (idx === curIdx) el.classList.add('active');
  });
}

/* ---------- right panel: live analysis card ---------- */
// Steps that get a section in the right panel as they complete. intake/profile
// stay in chat (conversational); rapport renders as the report at the top.
const PANEL_STEPS = {
  emap:     { num: 2, title: 'Utsläppskällor' },
  baslinje: { num: 3, title: 'Baslinje' },
  evidens:  { num: 4, title: 'Antaganden & underlag' },
  kalkyl:   { num: 5, title: 'Kalkyl & tidsprofil' },
  qa:       { num: 6, title: 'QA-granskning' },
};

function showAnalysisCard() {
  document.getElementById('resultsEmpty').style.display = 'none';
  document.getElementById('analysisCard').style.display = '';
}

// Turn "Källa: X" / "(antagande)" tokens into chips, like the åtgärdskort mockup.
// Done on the sanitised DOM, text node by text node, and the chips are built
// with textContent: rewriting the HTML string after sanitising (as this used
// to) put markup back into text the sanitiser had already passed (S14). A
// text node holds no tags, so a match cannot reach into one; the source
// stops at a clause boundary (.,;) or a line break, so "Källa: X. Nästa
// mening." does not swallow the next sentence.
const CHIP_RULES = [
  [/(?:KÄLLA|Källa|KALLA)\s*:\s*([^\n;.,]{2,45})/g, 'kalla-chip', m => 'Källa: ' + m[1].trim()],
  [/\((antagande|antaganden|schablon|standardvärde)\)/gi, 'kalla-chip antag', m => m[1]],
];
function chipify(root) {
  CHIP_RULES.forEach(([re, cls, label]) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      // Text already turned into a chip stays as it is.
      if (node.parentNode.classList && node.parentNode.classList.contains('kalla-chip')) return;
      const text = node.nodeValue;
      re.lastIndex = 0;
      let last = 0, m, out = null;
      while ((m = re.exec(text)) !== null) {
        out = out || document.createDocumentFragment();
        out.appendChild(document.createTextNode(text.slice(last, m.index)));
        const chip = document.createElement('span');
        chip.className = cls;
        chip.textContent = label(m);
        out.appendChild(chip);
        last = m.index + m[0].length;
      }
      if (!out) return;
      out.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(out, node);
    });
  });
  return root;
}
function renderMarkdownWithChips(md) { return fragmentHtml(chipify(sanitizedFragment(md))); }

function panelSection(step) { return document.querySelector('.step-sec[data-pstep="' + step + '"]'); }

function panelStepStart(step) {
  const cfg = PANEL_STEPS[step]; if (!cfg) return;
  showAnalysisCard();
  let sec = panelSection(step);
  if (!sec) {
    sec = document.createElement('div');
    sec.dataset.pstep = step;
    document.getElementById('analysisFeed').appendChild(sec);
  }
  sec.className = 'step-sec running';
  sec.innerHTML =
    '<div class="step-sec-head"><span class="step-sec-num">' + cfg.num + '</span>' +
    '<span class="step-sec-title">' + cfg.title + '</span>' +
    '<span class="step-sec-status"><span class="mini-spin"></span>räknar...</span>' +
    '<span class="step-sec-time">0:00</span></div>' +
    '<div class="step-sec-body"><div class="shimmer w90"></div><div class="shimmer w70"></div><div class="shimmer w50"></div></div>';
  sec.dataset.started = Date.now();
  sec.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

// The steps write for the next agent as much as for the person reading, so
// their text carries field names (A0, EF0_enhet, BAU_trend_A) and numbers in
// the form 1,36e6. The history keeps that text as it is; only what is drawn
// is made readable (2026-10-13: the numbers were hard to read).
function readableNumber(mantissa, exponent) {
  const v = parseFloat(mantissa.replace(',', '.')) * Math.pow(10, parseInt(exponent, 10));
  if (!isFinite(v)) return null;
  const a = Math.abs(v);
  // Four digits: the panel must not round away what the model wrote.
  const sv = (x) => x.toLocaleString('sv-SE', {maximumSignificantDigits: 4});
  if (a >= 1e15) return null;
  if (a >= 1e9) return sv(v / 1e9) + (a === 1e9 ? ' miljard' : ' miljarder');
  if (a >= 1e6) return sv(v / 1e6) + (a === 1e6 ? ' miljon' : ' miljoner');
  if (a >= 1e-6) return v.toLocaleString('sv-SE', {maximumSignificantDigits: 4});
  return null;
}
function readableNumbers(text) {
  // No lookbehind: Safari before 16.4 cannot parse one, and one regex it
  // cannot parse stops the whole page script.
  return text.replace(/(^|[^\w.,])(\d+(?:[.,]\d+)?)[eE]([+-]?\d{1,2})(?![\w])/g,
    (m, before, mant, exp) => { const r = readableNumber(mant, exp); return r ? before + r : m; });
}

const FIELD_LABELS = [
  [/^Nuläge_år$/, 'Nulägesår'],
  [/^A0$/, 'Aktivitet i dag'],
  [/^A0_enhet$/, 'Aktiviteten mäts i'],
  [/^EF0$/, 'Utsläpp per enhet i dag'],
  [/^EF0_enhet$/, 'Utsläppen per enhet mäts i'],
  [/^Källor_nuläge$/, 'Källor'],
  [/^Kommentar_nuläge$/, 'Kommentar'],
  [/^BAU_Tier$/, 'Prognosmetod'],
  [/^BAU_motivering$/, 'Varför'],
  [/^BAU_trend_A(\s*\(g_A\))?$/, 'Aktivitetens förändring per år utan åtgärden'],
  [/^BAU_trend_EF(\s*\(g_EF\))?$/, 'Utsläppen per enhet, förändring per år utan åtgärden'],
  [/^BAU_årpunkter$/, 'Prognosår'],
  [/^Kommentar_BAU$/, 'Kommentar'],
  // EMAP's driver fields, for when its text cannot be drawn as the EMAP view.
  [/^aktivitet_matt$/, 'Aktivitet som mäts'],
  [/^EF_enhet$/, 'Utsläpp per enhet mäts i'],
  [/^utsläppstyp$/, 'Slag av utsläpp'],
  [/^locus$/, 'Var utsläppen uppstår'],
  [/^sektor$/, 'Sektor'],
  [/^aktivitetsförändring$/, 'Aktivitetsförändring enligt DIN SPEC 91637'],
  [/^overlapp_risk$/, 'Risk för dubbelräkning'],
];
// The three tiers as the baslinje prompt defines them (agents/baslinje_bau.py).
const TIER_SAYS = {
  '0': 'nuläget hålls oförändrat',
  '1': 'trend ur de senaste årens data',
  '2': 'kända trender och beslutade styrmedel',
};
function readableFields(md) {
  return md.split('\n').map(line => {
    // "Drivare 2: Avfall till förbränning" opens a block; it reads as one.
    const d = line.match(/^\s*(?:#{1,6}\s*)?(?:\*\*)?(Drivare\s+\d+\s*:[^*\n]+?)(?:\*\*)?\s*$/);
    if (d) return '\n**' + d[1] + '**';
    const f = line.match(/^(\s*)([A-Za-zÅÄÖåäö0-9_]+(?:\s*\(g_(?:A|EF)\))?)\s*:\s*(.*)$/);
    if (!f) return line;
    const hit = FIELD_LABELS.find(([re]) => re.test(f[2]));
    if (!hit) return line;
    let value = f[3];
    const tier = hit[1] === 'Prognosmetod' && value.match(/^\[?([012])\]?\s*$/);
    if (tier) value = tier[1] + ' (' + TIER_SAYS[tier[1]] + ')';
    return f[1] + '**' + hit[1] + ':** ' + value;
  }).join('\n');
}

// A heading line in whatever form the model wrote it ("## X", "### 6) X",
// "**X**", "**X:**"), as its bare text, or null.
function headingText(line) {
  const m = line.match(/^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/) || line.match(/^\s*\*\*([^*]+?)\*\*\s*:?\s*$/);
  return m ? m[1].replace(/^\d+[).]\s*/, '').replace(/[:\s]+$/, '') : null;
}
const QUESTIONS_RE = /^Frågor till (miljöstrateg(en)?|användaren|dig)( för detta steg)?$/i;

// The parts of a step's text that talk to the person rather than analyse:
// what the step does, the gaps in the data, the questions it has. They go to
// the chat, where the person answers; the panel keeps the analysis
// (2026-10-13). Only baslinje is split today: EMAP's prompt asks for neither
// gaps nor questions, and evidens draws its own structured view.
const CHAT_SECTIONS = {
  baslinje: [
    [/^Kort om detta steg$/i, 'intro'],
    [/^Underlag från EMAP$/i, 'intro'],
    [/^Dataluckor( för detta steg)?$/i, 'gaps'],
    [QUESTIONS_RE, 'questions'],
  ],
};
const BACK_TO_PANEL = /^\s*(\*\*)?\s*(\d+[).]\s*)?(Drivare\s+\d+\s*:|Nulägesbaslinje per drivare|BAU-scenario per drivare)/i;
const DRIVER_LINE = /^\s*(#{1,6}\s*)?(\*\*)?\s*Drivare\s+\d+\s*:/m;
function isRule(line) { return /^\s*([-*_])(\s*\1){2,}\s*$/.test(line); }
function trimBlock(lines) {
  const out = lines.slice();
  while (out.length && (!out[0].trim() || isRule(out[0]))) out.shift();
  while (out.length && (!out[out.length - 1].trim() || isRule(out[out.length - 1]))) out.pop();
  return out.join('\n');
}
// The baslinje prompt names its sections (agents/baslinje_bau.py). The model
// writes them as "## X", as "**X**" or as a bare line, and a bare line was
// drawn as prose, run together with the paragraph under it, while the split
// below never found "Kort om detta steg" to send it to the chat
// (2026-10-14, the morning of the demo). Whatever the form, the page gets the
// same headings: the title line as one, the sections as the next level. A
// line already written as a heading, a driver's block and anything in a list
// are left as written.
const BASLINJE_TITLE = /^Baslinje(?: & BAU)?-analys för åtgärd\s*:\s*\S/i;
const BASLINJE_SECTIONS = [
  /^Kort om detta steg$/i,
  /^Underlag från EMAP$/i,
  /^Nulägesbaslinje per drivare$/i,
  /^BAU-scenario per drivare$/i,
  /^Dataluckor( för detta steg)?$/i,
  QUESTIONS_RE,
];
function baslinjeHeadings(md) {
  return (md || '').split('\n').map(line => {
    if (/^\s{0,3}#/.test(line)) return line;
    const bare = line.trim().replace(/^\*\*(.*?)\*\*\s*:?$/, '$1').replace(/^\d+[).]\s*/, '').replace(/[:\s]+$/, '').trim();
    if (!bare) return line;
    if (BASLINJE_TITLE.test(bare)) return '# ' + bare;
    if (BASLINJE_SECTIONS.some(re => re.test(bare))) return '## ' + bare;
    return line;
  }).join('\n');
}
function stepParts(step, md) {
  const text = step === 'baslinje' ? baslinjeHeadings(md) : (md || '');
  if (step === 'emap') {
    const emap = parseEmap(text);
    if (!emap) return {panel: text, chat: '', followUp: ''};
    const helps = emap.profiles.flatMap(p => p.helps);
    const followUp = helps.length
      ? '**Underlag som skulle göra bedömningen säkrare**\n\nHar du något av det här? Skriv det i chatten.\n\n'
        + helps.map(h => '- ' + h).join('\n')
      : '';
    return {panel: text, emap, chat: [emap.preamble, followUp].filter(Boolean).join('\n\n'), followUp};
  }
  const rules = CHAT_SECTIONS[step];
  if (!rules) return {panel: text, chat: '', followUp: ''};
  const panel = [], found = {intro: [], gaps: [], questions: []};
  let into = panel;
  text.split('\n').forEach(line => {
    // The analysis starts again at its own sections and at a driver's block,
    // also when the model wrote them as plain lines: without this, a
    // "4) Nulägesbaslinje per drivare" with no ## sent every driver to the chat.
    const h = headingText(line) ?? (BACK_TO_PANEL.test(line) ? line.trim() : null);
    if (h !== null) {
      const hit = rules.find(([re]) => re.test(h));
      // Each section is its own block, so two of them in the same part do
      // not run together over the rule that stood between them.
      if (hit) { into = []; found[hit[1]].push(into); return; }
      into = panel;
    }
    into.push(line);
  });
  // Nothing found, or nothing left to analyse: the text stays as it was.
  const left = trimBlock(panel).split('\n').filter(l => l.trim() && !isRule(l));
  // ...and a split that took a driver's block out of the panel is not used.
  const lostDrivers = DRIVER_LINE.test(text) && !DRIVER_LINE.test(panel.join('\n'));
  if (!(found.intro.length || found.gaps.length || found.questions.length) || left.length < 2 || lostDrivers) {
    return {panel: text, chat: '', followUp: ''};
  }
  // A rule left between two sections that are gone would draw two in a row.
  const kept = [];
  panel.forEach(line => {
    const last = kept.filter(l => l.trim()).pop();
    if (isRule(line) && (!last || isRule(last))) return;
    kept.push(line);
  });
  const join = (blocks) => blocks.map(trimBlock).filter(Boolean).join('\n\n');
  const intro = join(found.intro), gaps = join(found.gaps), questions = join(found.questions);
  const followUp = [
    gaps ? '**Dataluckor**\n\n' + gaps : '',
    questions ? '**Frågor till dig**\n\n' + questions : '',
  ].filter(Boolean).join('\n\n');
  return {
    panel: trimBlock(kept),
    chat: readableNumbers([intro, followUp].filter(Boolean).join('\n\n')),
    followUp: readableNumbers(followUp),
  };
}

// What the panel draws of a step's text: readable names and numbers, and the
// questions addressed to the person reading rather than to a job title.
function readablePanel(md, step) {
  return readableNumbers(step === 'baslinje' || step === 'emap' ? readableFields(md) : md).split('\n').map(line => {
    const h = headingText(line);
    return h !== null && QUESTIONS_RE.test(h) ? line.replace(/Frågor till [^*#\n]*?(?=\s*[*#:]|\s*$)/i, 'Frågor till dig') : line;
  }).join('\n');
}

// ---------- EMAP as a view, not as the agent's text ----------
// The EMAP agent writes for the next agent: numbered sections, "2.1
// EMAP_Åtgärdstyp", driver fields like aktivitet_matt (agents/emap.py). That
// text stays in the history as it is. What the person at the gate needs is
// another order: what the measure is, which emissions it touches, how it was
// classified and why, what is uncertain (2026-10-13: the step's
// text was hard to read). parseEmap reads the text into that shape; anything it does not
// recognise is kept and drawn under the section it stood in, and a text it
// cannot read at all is drawn as text.
const EMAP_CLASS_LABELS = [
  [/åtgärdstyp/i, 'Typ av åtgärd'],
  [/mekanism/i, 'Mekanism'],
  [/nivå/i, 'Nivå'],
  [/tidsprofil/i, 'När effekten kommer'],
  [/mognad/i, 'Mognad'],
  [/effektkategori/i, 'Typ av effekt'],
];
const EMAP_MECHANISM = {avoid: 'Undvika (Avoid)', shift: 'Byta (Shift)', improve: 'Förbättra (Improve)'};
const EMAP_DRIVER_FIELDS = ['aktivitet_matt', 'EF_enhet', 'utsläppstyp', 'locus', 'sektor', 'mekanism', 'aktivitetsförändring', 'overlapp_risk'];
// Since 2026-10-13 the mechanism is given per driver ("Shift, ΔA: ..."); a
// saved report from before has one for the whole measure, among the classes.
function emapMechanism(text) {
  const t = (text || '').replace(/\*\*/g, '').trim();
  const m = t.match(/^(Avoid|Shift|Improve)\b\s*[,:;–-]?\s*(?:(ΔA|ΔEF|Δ\s*A|Δ\s*EF|ändrad aktivitet|ändrad utsläppsfaktor)(?![\wåäö])\s*[,:;–-]?\s*)?(.*)$/i);
  if (!m) return {name: '', what: '', rest: t};
  const what = !m[2] ? '' : /EF|utsläppsfaktor/i.test(m[2]) ? 'utsläppen per enhet' : 'mängden';
  return {name: EMAP_MECHANISM[m[1].toLowerCase()], what, rest: m[3].trim()};
}

function emapBare(line) {
  return line.trim().replace(/^#{1,6}\s*/, '').replace(/^\*\*(.*?)\*\*:?$/, '$1').replace(/\*\*/g, '').trim();
}
function parseEmap(md) {
  const view = {preamble: [], profiles: []};
  let profile = null, section = null, cls = null, driver = null, list = null;
  const newProfile = (title) => {
    profile = {title: title.trim(), summary: [], classes: [], drivers: [], unsure: [], helps: [], extras: []};
    view.profiles.push(profile);
    section = null; cls = null; driver = null; list = null;
  };
  const extra = (title) => { section = {kind: 'extra', title, lines: []}; profile.extras.push(section); cls = driver = list = null; };
  (md || '').split('\n').forEach(raw => {
    const bare = emapBare(raw);
    if (!bare) {
      // Paragraph breaks are kept where the text is drawn as markdown.
      if (section && section.kind === 'summary') profile.summary.push('');
      else if (section && section.kind === 'extra') section.lines.push('');
      return;
    }
    if (isRule(raw) || /^EMAP-ANALYS \(FÖRENKLAD VARIANT\)$/i.test(bare)) return;
    const start = bare.match(/^EMAP-analys av åtgärd\s*:\s*(.+)$/i) || bare.match(/^Åtgärd\s+\d+\s*:\s*(.+)$/i);
    if (start) { newProfile(start[1]); return; }
    if (!profile) { view.preamble.push(raw.trim()); return; }

    // A numbered line is a heading only where the format puts one: flush
    // left, and either written as a heading or named like one of the format's
    // sections. A numbered list item ("1. Osäkerheter kring tidsprofilen är
    // stora.") or a wrapped "1.5 gånger" is text.
    const flush = raw.search(/\S/) === 0 || /^\s*(#|\*\*)/.test(raw);
    const marked = /^\s*(#|\*\*)/.test(raw);
    const sub = flush && bare.match(/^\d+\.\d+\.?\s+(.+)$/);
    const subOk = sub && (marked || /EMAP_|åtgärdstyp|mekanism|nivå|tidsprofil|mognad|effektkategori/i.test(sub[1]));
    const topM = !sub && flush && bare.match(/^\d+[.)]?\s+(.+)$/);
    const known = (t) => /^(sammanfattning|emap-kategorisering|kategorisering|osäkerheter|emap-drivare|drivare)\b/i.test(t)
      && t.length <= 40 && !/[.!?]$/.test(t);
    const headName = topM ? topM[1] : (marked ? bare : null);
    const top = headName !== null && (known(headName) || (topM && marked && /^\d+[.)]/.test(bare))) ? [null, headName] : null;
    if (subOk && section && section.kind === 'classes') {
      const name = sub[1];
      const hit = EMAP_CLASS_LABELS.find(([re]) => re.test(name));
      cls = {label: hit ? hit[1] : name.replace(/^EMAP_/, '').replace(/_/g, ' '), value: '', why: [], wantValue: false};
      profile.classes.push(cls);
      return;
    }
    if (top) {
      const name = top[1];
      cls = driver = list = null;
      if (/sammanfattning/i.test(name)) section = {kind: 'summary'};
      else if (/kategorisering/i.test(name)) section = {kind: 'classes'};
      else if (/osäkerhet/i.test(name)) section = {kind: 'unsure'};
      else if (/drivare/i.test(name)) section = {kind: 'drivers'};
      else extra(name);
      return;
    }
    const d = bare.match(/^Drivare\s+(\d+)\s*:\s*(.+)$/i);
    // "Drivare N:" is unambiguous wherever it stands: a block that missed its
    // "4. EMAP-drivare" heading is still a driver, not an uncertainty.
    if (d && !(section && section.kind === 'classes' && cls)) {
      if (!section || section.kind !== 'drivers') section = {kind: 'drivers'};
      driver = {num: d[1], name: d[2].trim(), fields: {}, rest: []};
      profile.drivers.push(driver);
      return;
    }
    // A bold line of its own that is not one of the above opens a section the
    // format does not name ("Notering om samband mellan åtgärderna").
    // Not inside a classification or the summary, where a bold line is a
    // value or an emphasis, not a heading.
    const inClass = section && section.kind === 'classes' && cls;
    if (/^\s*\*\*[^*]+\*\*:?\s*$/.test(raw) && !inClass && !(section && section.kind === 'summary')) {
      extra(bare.replace(/:$/, '')); return;
    }

    // Text between the title and "1. Sammanfattning" belongs to the summary.
    if (!section) section = {kind: 'summary'};
    if (section.kind === 'summary') { profile.summary.push(raw.trim()); return; }
    if (section.kind === 'classes' && cls) {
      const item = bare.replace(/^[-*]\s+/, '');
      const v = item.match(/^Vald [^:(]*(\([^)]*\))?\s*:\s*(.*)$/i);
      if (v) { cls.value = v[2].trim(); cls.wantValue = !cls.value; return; }
      const m = item.match(/^Kort motivering\s*:\s*(.*)$/i);
      if (m) { cls.wantValue = false; if (m[1].trim()) cls.why.push(m[1].trim()); return; }
      if (cls.wantValue) { cls.value = item; cls.wantValue = false; return; }
      cls.why.push(item);
      return;
    }
    if (section.kind === 'unsure') {
      const item = bare.replace(/^[-*]\s+/, '');
      const lead = raw.search(/\S/) < 2 && item.match(/^(Viktigaste osäkerheter|Vilken typ av underlag)[^:]*:\s*(.*)$/i);
      if (lead) {
        list = /underlag/i.test(lead[1]) ? profile.helps : profile.unsure;
        if (lead[2].trim()) list.push(lead[2].trim());
        return;
      }
      (list || profile.unsure).push(item);
      return;
    }
    if (section.kind === 'drivers' && driver) {
      const f = bare.replace(/^[-*]\s+/, '').match(/^([A-Za-zÅÄÖåäö_]+)\s*:\s*(.*)$/);
      if (f && EMAP_DRIVER_FIELDS.includes(f[1])) { driver.fields[f[1]] = f[2].trim(); return; }
      driver.rest.push(raw.trim());
      return;
    }
    if (section.kind === 'extra') { section.lines.push(raw); return; }
    // Text in a section with nothing open yet to hold it (a sentence before
    // the first 2.x, before the first driver): kept, under its own heading.
    extra('');
    section.lines.push(raw);
  });
  view.preamble = view.preamble.join('\n').trim();
  const drivers = view.profiles.reduce((n, p) => n + p.drivers.length, 0);
  const usable = view.profiles.length && view.profiles.every(p => p.drivers.length || p.classes.length)
    && !(DRIVER_LINE.test(md || '') && !drivers);
  // Drawn mostly as escaped text, which sanitizedFragment never sees.
  return usable ? plainTermsDeep(view) : null;
}

function emapValue(cls) {
  const v = cls.value.replace(/\*\*/g, '').trim();
  const mech = cls.label === 'Mekanism' && v.match(/^(Avoid|Shift|Improve)\b(.*)$/i);
  return mech ? EMAP_MECHANISM[mech[1].toLowerCase()] + mech[2] : v;
}
function emapRisk(text) {
  const m = (text || '').match(/^\s*(låg|medel|hög)\b[\s.,:;–-]*(.*)$/i);
  if (!m) return text ? '<p class="em-overlap">' + escapeHtml(text) + '</p>' : '';
  const level = m[1].toLowerCase();
  const cls = {låg: 'lag', medel: 'medel', hög: 'hog'}[level];
  return '<p class="em-overlap"><span class="em-risk ' + cls + '">' +
    escapeHtml(level.charAt(0).toUpperCase() + level.slice(1)) + ' risk för dubbelräkning.</span> ' +
    escapeHtml(capitalized(m[2].trim())) + '</p>';
}
function emapDriverHtml(d) {
  const f = d.fields;
  const enabler = /enabler|ingen direkt/i.test(f.utsläppstyp || '');
  const term = (label, value) =>
    '<div class="em-term"><div class="em-term-lab">' + label + '</div><div class="em-term-val">' + escapeHtml(value || '–') + '</div></div>';
  const where = [f.utsläppstyp ? capitalized(f.utsläppstyp) + (enabler ? '' : ' utsläpp') : '',
                 f.locus ? (enabler ? '' : 'som uppstår ') + f.locus.replace(/^båda$/i, 'både inom och utanför kommunen') : ''].filter(Boolean).join(', ');
  const mech = f.mekanism ? emapMechanism(f.mekanism) : null;
  const mechHtml = !mech ? '' : '<p class="em-sector">' + (mech.name
    ? 'Så påverkas den: ' + escapeHtml(mech.name) + (mech.what ? ', ändrar ' + mech.what : '') + (mech.rest ? '. ' + escapeHtml(capitalized(mech.rest)) : '')
    : 'Så påverkas den: ' + escapeHtml(mech.rest)) + '</p>';
  const eq = enabler
    ? '<p class="em-enabler">Har inga egna utsläpp här. Effekten räknas i en annan del av analysen.' +
      (f.aktivitet_matt ? ' Mäts som ' + escapeHtml(f.aktivitet_matt) + '.' : '') + '</p>'
    : '<div class="em-eq">' + term('Aktivitet', f.aktivitet_matt) +
      '<span class="em-op" aria-label="gånger">×</span>' + term('Utsläpp per enhet', f.EF_enhet) +
      '<span class="em-op" aria-label="ger">=</span>' + term('Utsläpp', where) + '</div>';
  return '<li class="em-driver"><div class="em-dname"><span class="em-dnum">' + escapeHtml(d.num) + '</span>' +
    '<span>' + escapeHtml(d.name) + '</span></div>' + eq + mechHtml +
    (f.sektor ? '<p class="em-sector">Sektor: ' + escapeHtml(f.sektor) + '</p>' : '') +
    // DIN SPEC 91637 annex C, since 1.1 (agents/emap.py).
    (f['aktivitetsförändring'] ? '<p class="em-sector">Aktivitetsförändring enligt DIN SPEC 91637: ' +
      escapeHtml(f['aktivitetsförändring']) + '</p>' : '') +
    emapRisk(f.overlapp_risk) +
    (d.rest.length ? '<div class="em-rest">' + renderMarkdownWithChips(d.rest.join('\n')) + '</div>' : '') +
    '</li>';
}
function emapProfileHtml(p) {
  const classes = p.classes.map(c =>
    '<div class="em-class"><dt>' + escapeHtml(c.label) + '</dt><dd>' +
    (c.why.length
      ? '<details><summary><span class="em-val">' + escapeHtml(emapValue(c) || '–') + '</span><span class="em-why-btn">Varför?</span></summary>' +
        '<div class="em-why">' + renderMarkdownWithChips(c.why.join('\n')) + '</div></details>'
      : '<span class="em-val">' + escapeHtml(emapValue(c) || '–') + '</span>') +
    '</dd></div>').join('');
  const extras = p.extras.filter(x => x.lines.some(l => l.trim())).map(x =>
    (x.title ? '<h4 class="em-h">' + escapeHtml(x.title) + '</h4>' : '') +
    '<div class="em-text">' + renderMarkdownWithChips(x.lines.join('\n')) + '</div>').join('');
  return '<section class="em-profile">' +
    '<h3 class="em-title">' + escapeHtml(p.title) + '</h3>' +
    (p.summary.length ? '<div class="em-summary">' + renderMarkdownWithChips(p.summary.join('\n')) + '</div>' : '') +
    (p.drivers.length ? '<h4 class="em-h">Utsläpp som åtgärden påverkar</h4><ol class="em-drivers">' +
      p.drivers.map(emapDriverHtml).join('') + '</ol>' : '') +
    (classes ? '<h4 class="em-h">' + (p.classes.length === 1 && p.classes[0].label === 'Typ av effekt'
      ? 'Så räknas effekten' : 'Så klassas åtgärden') + '</h4><dl class="em-classes">' + classes + '</dl>' : '') +
    (p.unsure.length ? '<h4 class="em-h">Det som är osäkert</h4><ul class="em-list">' +
      p.unsure.map(u => '<li>' + escapeHtml(u) + '</li>').join('') + '</ul>' : '') +
    extras + '</section>';
}
function renderEmap(view) {
  const cfg = PANEL_STEPS.emap;
  let sec = panelSection('emap');
  if (!sec) { panelStepStart('emap'); sec = panelSection('emap'); }
  if (!sec) return;
  const n = view.profiles.reduce((k, p) => k + p.drivers.length, 0);
  sec.className = 'step-sec emap done';
  sec.innerHTML =
    '<div class="step-sec-head"><span class="step-sec-num">✓</span>' +
    '<span class="step-sec-title">' + cfg.title + '</span>' +
    '<span class="step-sec-status">' + (n ? n + ' drivare' : 'klar') + '</span></div>' +
    '<div class="step-sec-body">' + keyPointsSafely(() => keyPointsHtml(emapKeyPoints(view))) + view.profiles.map(emapProfileHtml).join('') + '</div>';
}

function panelStepDone(step, markdown, keyPoints) {
  const cfg = PANEL_STEPS[step]; if (!cfg) return;
  let sec = panelSection(step);
  if (!sec) { panelStepStart(step); sec = panelSection(step); }
  sec.className = 'step-sec done';
  sec.innerHTML =
    '<div class="step-sec-head"><span class="step-sec-num">✓</span>' +
    '<span class="step-sec-title">' + cfg.title + '</span>' +
    '<span class="step-sec-status">klar</span></div>' +
    '<div class="step-sec-body">' + (keyPoints || '') +
    renderMarkdownWithChips(readablePanel(cleanOutput(markdown), step)) + '</div>';
}

// ---------- "Det viktigaste" at the top of each step ----------
// Each step opens with what the person at the gate should know before reading
// the rest (2026-10-13: a lot of information and assumptions to judge;
// they stay, but a summary comes first). The points are
// read out of what the step already produced, not written by a model: the
// prompts are unchanged, so nothing the next step reads moves. A step whose
// text cannot be read into points gets no box, never a wrong one.
// points: [{text, warn}] or strings. tone: '', 'warn' or 'ok'.
function keyPointsHtml(points, tone) {
  const list = (points || []).map(p => typeof p === 'string' ? {text: p} : p).filter(p => p && p.text);
  if (!list.length) return '';
  return '<div class="key-points' + (tone ? ' ' + tone : '') + '"><h4>Det viktigaste</h4><ul>' +
    list.map(p => '<li' + (p.warn ? ' class="warn"' : '') + '>' + escapeHtml(plainTerms(p.text).replace(/…\./g, '…')) + '</li>').join('') +
    '</ul></div>';
}
// A summary that cannot be read must never cost the step its panel.
function keyPointsSafely(build) { try { return build(); } catch (e) { return ''; } }
function namesList(names) {
  if (names.length <= 1) return names.join('');
  return names.slice(0, -1).join(', ') + ' och ' + names[names.length - 1];
}
// Cut at a word, not inside one.
function wordsUpTo(text, max) {
  const t = (text || '').trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max - 1);
  return (cut.lastIndexOf(' ') > max / 2 ? cut.slice(0, cut.lastIndexOf(' ')) : cut).replace(/[\s,:;–-]+$/, '') + '…';
}
function shortValue(text, max) {
  let t = (text || '').replace(/\*\*/g, '').replace(/^\[|\]$/g, '').trim();
  // The first clause carries the value; the reasoning after it is in the panel.
  t = t.split(/\s+\(|;|\.\s/)[0].trim().replace(/[.,:]$/, '');
  t = readableNumbers(t);
  return t.length > (max || 60) ? t.slice(0, (max || 60) - 1).trimEnd() + '…' : t;
}

function emapKeyPoints(view) {
  const drivers = view.profiles.flatMap(p => p.drivers);
  const points = [];
  if (drivers.length) {
    const names = drivers.map(d => wordsUpTo(d.name.replace(/\*\*/g, ''), 60));
    points.push(drivers.length === 1
      ? 'Åtgärden påverkar en utsläppskälla: ' + names[0] + '.'
      : 'Åtgärden påverkar ' + drivers.length + ' utsläppskällor: ' + namesList(names) + '.');
  }
  const perDriver = drivers.map(d => emapMechanism(d.fields.mekanism).name).filter(Boolean);
  if (perDriver.length) {
    const kinds = [...new Set(perDriver)];
    points.push('Sätt att minska utsläppen: ' + namesList(kinds.map(k => kinds.length > 1 ? k.toLowerCase() : k)) + '.');
  } else {
    const mechs = view.profiles.flatMap(p => p.classes).filter(c => c.label === 'Mekanism' && emapValue(c));
    const mech = mechs.length && mechs.every(c => emapValue(c) === emapValue(mechs[0])) ? mechs[0] : null;
    if (mech) {
      // "Byta (Shift)" keeps its parenthesis; the reasoning after a dash does not.
      const v = emapValue(mech).replace(/\*\*/g, '').split(/\.\s|;|\s[–-]\s/)[0].trim().replace(/[.,:]$/, '');
      points.push('Sätt att minska utsläppen: ' + (v.length > 70 ? v.slice(0, 69).trimEnd() + '…' : v) + '.');
    }
  }
  // How the effect will be counted, said here rather than discovered at step 5.
  const kinds = view.profiles.flatMap(p => p.classes).filter(c => c.label === 'Typ av effekt').map(c => emapValue(c).toLowerCase());
  if (kinds.some(k => /indirekt|möjliggör|enabler/.test(k)))
    points.push('Effekten räknas som en kedja: hur många som nås, hur många som ändrar sig, hur mycket, och hur mycket av det som är åtgärdens förtjänst.');
  if (kinds.some(k => /stödjande|styrning/.test(k)))
    points.push({warn: true, text: 'En del av åtgärden stödjer andra åtgärder och får inget eget tal.'});
  const risky = drivers.filter(d => /^\s*hög\b/i.test(d.fields.overlapp_risk || ''));
  if (risky.length) points.push({warn: true, text: 'Hög risk för dubbelräkning: ' +
    namesList(risky.map(d => wordsUpTo(d.name.replace(/\*\*/g, ''), 60))) + '.'});
  const unsure = view.profiles.reduce((n, p) => n + p.unsure.length, 0);
  if (unsure) points.push(unsure === 1 ? 'En sak är osäker, se Det som är osäkert.'
    : unsure + ' saker är osäkra, se Det som är osäkert.');
  if (view.profiles.some(p => p.helps.length)) points.push('Har du underlag som gör bedömningen säkrare? Frågan står i chatten.');
  return points;
}

// The baseline blocks, by driver: "Drivare 1: Namn" and the fields under it.
// The same driver appears under Nuläge and under BAU; its fields are merged.
function baselineDrivers(md) {
  const byNum = {}, order = [];
  let cur = null, lastKey = null;
  (md || '').split('\n').forEach(line => {
    const d = line.match(/^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\*\*)?Drivare\s+(\d+)\s*:\s*([^*\n]+?)(?:\*\*)?\s*$/);
    if (d) {
      if (!byNum[d[1]]) { byNum[d[1]] = {num: d[1], name: d[2].trim(), f: {}}; order.push(d[1]); }
      cur = byNum[d[1]]; lastKey = null;
      return;
    }
    const h = headingText(line);
    if (h !== null && !/^Drivare/i.test(h)) { cur = null; lastKey = null; return; }
    if (!cur) return;
    // A trend given per scenario: "  - medel: -5 %/år. ..." under its field.
    const level = lastKey && line.match(/^\s*[-*]\s*(?:\*\*)?(låg|medel|hög)(?:\*\*)?\s*:\s*(.*)$/i);
    if (level) { cur.f[lastKey + ':' + level[1].toLowerCase()] = level[2].trim(); return; }
    const f = line.match(/^\s*(?:[-*]\s*)?(?:\*\*)?([A-Za-zÅÄÖåäö0-9_]+)(?:\s*\(g_(?:A|EF)\))?(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$/);
    if (f) { lastKey = f[1]; if (!(f[1] in cur.f)) cur.f[f[1]] = f[2].trim(); }
  });
  return order.map(n => byNum[n]);
}
// A yearly trend as the model writes it ("-0,02", "−2 %", "0,01 (1 %/år)") in
// words, or '' when it cannot be read with confidence.
function trendWords(value) {
  const v = (value || '').replace(/−/g, '-');
  // "-5 %/år", "-5 % per år": percent. A range ("0,5 till 1 %") is not read.
  const pc = v.match(/^\s*\[?\s*([+-]?\d+(?:[.,]\d+)?)\s*%/);
  // A bare share ("-0,02", "0,01 (1 %/år)") only when it stands alone.
  const fr = !pc && v.match(/^\s*\[?\s*([+-]?\d+[.,]\d+|0)\s*\]?\s*(?:\(|$|\.\s)/);
  if (!pc && !fr) return '';
  let pct = parseFloat((pc || fr)[1].replace(',', '.'));
  if (!isFinite(pct)) return '';
  if (fr) { if (Math.abs(pct) >= 1) return ''; pct *= 100; }
  const r = Math.round(pct * 10) / 10;
  if (r === 0) return 'oförändrad';
  return (r > 0 ? 'ökar ' : 'minskar ') + Math.abs(r).toLocaleString('sv-SE') + ' % per år';
}
function baselineKeyPoints(md, followUp) {
  // A driver with no level of its own (an enabler, A0 0) is counted on another.
  const level = (v) => { const m = (v || '').match(/\d+(?:[.,]\d+)?/); return m ? parseFloat(m[0].replace(',', '.')) : 0; };
  const drivers = baselineDrivers(md).filter(d => level(d.f.A0) !== 0);
  if (!drivers.length) return [];
  const points = drivers.slice(0, 4).map(d => {
    // "ca 40 %" with the unit "% av cirkulära köp" is one percent sign, not two.
    // The unit's own sign is the one kept: "%/år" and "%-enheter" start with it.
    const withUnit = (value, n, unit) => {
      const v = shortValue(value, n), u = unit ? shortValue(unit, 24) : '';
      if (/%$/.test(v) && /^%/.test(u)) return v.replace(/\s*%$/, '') + ' ' + u;
      return v + (u ? ' ' + u : '');
    };
    // shortValue drops the "(ANTAGANDE: ...)" after the number, so an assumed
    // level would read as a known one. 2026-10-15: an amount the user
    // could not give is assumed, and the analysis must show it.
    const assumed = /ANTAGANDE/i.test(d.f.A0 || '') ? ' (antaget)' : '';
    const today = withUnit(d.f.A0, 30, d.f.A0_enhet) + assumed + ' med ' + withUnit(d.f.EF0, 20, d.f.EF0_enhet);
    const trend = (key) => trendWords(d.f[key] || d.f[key + ':medel']);
    const a = trend('BAU_trend_A'), ef = trend('BAU_trend_EF');
    const bau = [a ? 'aktiviteten ' + a : '', ef ? 'utsläppen per enhet ' + ef : ''].filter(Boolean).join(', ');
    return d.name + ': i dag ' + today + '.' + (bau ? ' Utan åtgärden: ' + bau + '.' : '');
  });
  if (drivers.length > 4) points.push('Och ' + (drivers.length - 4) + ' utsläppskällor till, se nedan.');
  if (followUp) points.push('Dataluckor och frågor till dig står i chatten.');
  return points;
}

function evidenceKeyPoints(drivers) {
  const params = drivers.flatMap(d => (d.parameters || []).map(p => ({p, d})));
  const points = [];
  const weak = params.filter(({p}) => /^l[åa]g/i.test((p.kvalitet || '').trim()));
  params.slice(0, 4).forEach(({p}) => {
    if (!p.med) return;
    // A share reads as percent, as the factors above it do (2026-10-13).
    const bare = (v) => {
      const n = shortValue(v, 20).replace(/−/g, '-').match(/^\s*(-?\d+(?:[.,]\d+)?)\s*$/);
      return n ? parseFloat(n[1].replace(',', '.')) : null;
    };
    // A share given as 0 to 1 reads as percent, as the factors above it do
    // (2026-10-13); all three values, or none of them.
    const nums = [p.med, p.min, p.max].filter(Boolean).map(bare);
    const share = /^\s*andel/i.test(p.enhet || '') && !/%|procent/i.test(p.enhet || '')
      && nums.every(x => x != null && Math.abs(x) <= 1);
    const val = (v) => share ? (bare(v) * 100).toLocaleString('sv-SE', {maximumFractionDigits: 1}) + ' %' : shortValue(v, 20);
    const unitText = shortValue(p.enhet, 40);
    const unit = share || !unitText ? '' : /%|procent/i.test(unitText) ? ' %' : unitText.length > 18 ? '' : ' ' + unitText;
    const span = p.min && p.max ? ' (spann ' + val(p.min) + ' till ' + val(p.max) + ')' : '';
    const low = weak.some(w => w.p === p);
    points.push({warn: low, text: capitalized(wordsUpTo(paramTitle(p).replace(/\*\*/g, ''), 90)) + ': troligt ' + val(p.med) +
      unit + span + (low ? '. Svagt underlag.' : '.')});
  });
  if (params.length > 4) points.push('Och ' + (params.length - 4) + ' antaganden till, se nedan.');
  if (weak.length > 1) points.push({warn: true, text: weak.length + ' antaganden har svagt underlag. Har du bättre siffror, skriv dem i chatten.'});
  return points.length ? [(drivers.length === 1 ? 'Åtgärden påverkar en utsläppskälla.' : 'Åtgärden påverkar ' + drivers.length + ' utsläppskällor.') +
    ' Resultatet hänger på antagandena nedan; godkänn dem, eller rätta dem i chatten.'].concat(points) : [];
}

function kalkylKeyPoints(headline, span, warnings) {
  if (!headline) return [];
  const mid = headline.net != null ? headline.net : (headline.cons != null ? headline.cons : headline.terr);
  if (mid == null) return [];
  const w = (span && span.window) || (state.mode === 'uppfoljning' ? null : AVG_WINDOW);
  const points = [];
  // A negative number is an increase. "Minskar med -50 ton" said the opposite
  // of the calculation (2026-10-13, the tjänstebilar package).
  const change = (x) => (x < 0 ? 'en ökning på ' : 'en minskning på ') + fmt(Math.abs(x)) + ' ton';
  if (headline.year) {
    points.push('Troligt resultat: utsläppen ' + (mid < 0 ? 'ökar med ' + fmt(-mid) : 'minskar med ' + fmt(mid)) +
      ' ton CO₂e år ' + headline.year + '.');
    if (span && span.net_lo != null && span.net_hi != null) {
      points.push('Med försiktiga och optimistiska antaganden: ' + (span.net_lo < 0 || span.net_hi < 0
        ? 'från ' + change(span.net_lo) + ' till ' + change(span.net_hi)
        : fmt(span.net_lo) + ' till ' + fmt(span.net_hi) + ' ton') + ' samma år.');
    }
    if (span && span.avg_net != null && w) points.push('I snitt per år ' + w[0] + '–' + w[1] + ': ' +
      (span.avg_net < 0 ? change(span.avg_net) : fmt(span.avg_net) + ' ton') + ' CO₂e.');
  } else {
    points.push('Troligt resultat: ' + fmt(mid) + ' ton CO₂e per år' + (w ? ' i snitt ' + w[0] + '–' + w[1] : '') + '.');
    if (span && span.net_lo != null && span.net_hi != null) {
      points.push('Med försiktiga och optimistiska antaganden: ' + fmt(span.net_lo) + ' till ' + fmt(span.net_hi) + ' ton per år.');
    }
  }
  if (span && span.cum_net != null) points.push('Sammanlagt till ' + (span.target_year || 'målåret') + ': ' +
    (headline.year && span.cum_net < 0 ? change(span.cum_net) : fmt(span.cum_net) + ' ton') + ' CO₂e.');
  // What the change is in the activity's own unit, written by the engine
  // (calc.engine.activity_changes), largest drivers first.
  const act = span && span.activity;
  if (act && act.rows && act.rows.length) {
    act.rows.slice(0, 3).forEach(r => points.push(wordsUpTo(r.driver, 70) + ': ' + r.text + '.'));
    if (act.rows.length > 3) points.push('Och ' + (act.rows.length - 3) +
      (act.rows.length - 3 === 1 ? ' utsläppskälla' : ' utsläppskällor') + ' till under Vad åtgärden ändrar i verksamheten.');
  }
  (warnings || []).forEach(t => points.push({warn: true, text: t}));
  return points;
}

// The QA step ends with "QA-status: ok|varning", "QA-anmärkningar:" and
// "QA-åtgärdsförslag:" in a fixed form (agents/cove_qa.py, section 7). Read
// the status, the remarks and the suggestions.
function qaVerdict(md) {
  const lines = (md || '').split('\n');
  let status = null, into = null;
  const remarks = [], suggestions = [];
  lines.forEach(line => {
    const bare = line.replace(/\*\*/g, '').trim();
    const s = bare.match(/^QA-status\s*:\s*\[?\s*(ok|varning)\b(.*)$/i);
    // "ok (med smärre varningar)" is not a clean ok.
    if (s) { status = /varning/i.test(s[0].replace(/^QA-status/i, '')) ? 'varning' : s[1].toLowerCase(); into = null; return; }
    const list = bare.match(/^QA-(anmärkningar|åtgärdsförslag)\s*:?\s*(.*)$/i);
    if (list) {
      into = /^anm/i.test(list[1]) ? remarks : suggestions;
      const rest = list[2].trim();
      if (rest && !/^(inga|-|–)\.?$/i.test(rest)) into.push(rest);
      return;
    }
    if (into && (/^QA-/i.test(bare) || /^Frågor till/i.test(bare) || headingText(line) !== null)) { into = null; return; }
    // Top-level bullets only; a sub-point belongs to the remark above it.
    const item = line.search(/\S/) < 4 && bare.match(/^[-*•]\s+(.+)$/);
    if (into && item) into.push(item[1].replace(/^"|"$/g, '').trim());
  });
  return status ? {status, remarks, suggestions} : null;
}
function qaKeyPoints(verdict) {
  if (!verdict) return [];
  const points = [verdict.status === 'ok'
    ? 'Granskningen godkände analysen (status ok).'
    : {warn: true, text: 'Granskningen varnar. Läs anmärkningarna innan du använder resultatet.'}];
  verdict.remarks.slice(0, 2).forEach(r => points.push(wordsUpTo(readableNumbers(r), 160)));
  if (verdict.remarks.length > 2) points.push('Och ' + (verdict.remarks.length - 2) + ' anmärkningar till, se nedan.');
  return points;
}
// ---------- recalculate with QA's remarks ----------
// When QA warns, or the calculation warns about itself (units that do not fit
// together), the user can have the calculation redone on the same approved
// assumptions with the remarks as a correction (2026-10-13: the quality
// review should be able to have at least the calculation redone). It is a button,
// not automatic: QA is a model and can be wrong, and an automatic re-run
// would change numbers the user approved without them seeing it, and could
// loop. Only the reading of the assumptions into the calculation is redone;
// the assumptions themselves stay as approved.
function recalcReasons() {
  const v = state.qaVerdict;
  const qa = v && v.status === 'varning' ? v.remarks : [];
  return qa.concat((state.lastKalkyl && state.lastKalkyl.warnings) || []);
}
function recalcTurn(reasons) {
  return BRIDGE.evidens + '\n\n' +
    'Kalkylen har redan räknats en gång. Kvalitetsgranskningen och beräkningens egna kontroller anmärkte då:\n' +
    reasons.map(r => '- ' + r).join('\n') + '\n\n' +
    'Räkna om kalkylen. Rätta det som anmärkningarna visar är fel i hur antagandena har lästs in i ' +
    'beräkningen, till exempel en enhet (ton mot kg), ett tal som hamnat på fel ställe eller en andel ' +
    'som egentligen är en mängd. Antagandena ovan är godkända av användaren: ändra dem inte för att en ' +
    'anmärkning ifrågasätter dem, utan läs in dem rätt. En andelsförändring kan aldrig vara mindre ' +
    'än -1 (-100 %): skiljer sig en mängd så mycket mellan scenarierna att andelen skulle hamna där, ' +
    'sätt utgångsvärdet till den största mängden och låt andelarna i de andra scenarierna vara mindre ' +
    'delar av den.';
}
function offerRecalc() {
  const warn = document.getElementById('heroWarn');
  if (!warn) return;
  warn.querySelectorAll('.recalc, .qa-recalc-why').forEach(el => el.remove());
  if (state.phase !== 'done' || state.calcMark == null || !recalcReasons().length) return;
  // Under "Läs mer": what the button can correct and what it cannot.
  const more = warn.querySelector('.qa-more');
  if (more) {
    const why = document.createElement('p');
    why.className = 'qa-recalc-why';
    why.textContent = 'Knappen nedan räknar om kalkylen med anmärkningarna som rättelse. Den läser in de ' +
      'antaganden du godkände en gång till och rättar fel i hur talen har lästs in, till exempel en enhet ' +
      'eller ett tal på fel ställe. Antagandena själva ändras inte. Gäller ett förslag själva antagandena, ' +
      'gör en ny analys och ändra dem när de visas för godkännande.';
    more.insertBefore(why, more.querySelector('.qa-open-step'));
  }
  const box = document.createElement('div');
  box.className = 'recalc';
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = 'Räkna om kalkylen med anmärkningarna';
  btn.addEventListener('click', recalcWithQa);
  const note = document.createElement('span');
  note.textContent = 'Samma godkända antaganden, med anmärkningarna som rättelse.';
  box.appendChild(btn); box.appendChild(note);
  warn.appendChild(box);
  warn.style.display = '';
}
async function recalcWithQa() {
  if (state.running || state.phase !== 'done' || state.calcMark == null) return;
  const reasons = recalcReasons();
  if (!reasons.length) return;
  document.querySelectorAll('.recalc button').forEach(b => { b.disabled = true; });
  const before = {history: state.history, headline: state.headline, kallmarkeringMd: state.kallmarkeringMd,
                  lastKalkyl: state.lastKalkyl, qaVerdict: state.qaVerdict, reportMarkdown: state.reportMarkdown,
                  kalkyl: panelSnapshot('kalkyl'), qa: panelSnapshot('qa')};
  const was = state.headline;
  state.running = true; state.phase = 'running';
  setInputEnabled(false);
  // The trail is folded away under the report; the steps redrawn are shown.
  const feed = document.getElementById('analysisFeed');
  if (feed && feed.style.display === 'none') toggleTrail();
  addSystem('Räknar om kalkylen med anmärkningarna. Antagandena är desamma som du godkände.');
  state.history = state.history.slice(0, state.calcMark).concat([{role: 'user', content: recalcTurn(reasons)}]);
  const token = runToken;
  const ok = await runStages(['kalkyl', 'qa', 'rapport']);
  if (token !== runToken) return;
  state.running = false;
  setInputEnabled(true);
  if (!ok) {
    // The calculation on screen and in the report is the one from before.
    Object.assign(state, {history: before.history, headline: before.headline, kallmarkeringMd: before.kallmarkeringMd,
                          lastKalkyl: before.lastKalkyl, qaVerdict: before.qaVerdict, reportMarkdown: before.reportMarkdown});
    panelStepPutBack('kalkyl', before.kalkyl);
    panelStepPutBack('qa', before.qa);
    const k = before.lastKalkyl;
    if (k && k.headline) renderKalkylHero(k.headline, k.span, k.warnings);
    markHeroWithQa(before.qaVerdict);
    state.phase = 'done';
    addSystem('Omräkningen gick inte igenom. Den förra beräkningen gäller.', true);
    offerRecalc();
    return;
  }
  state.phase = 'done';
  updateProgress('rapport', true);
  // A calculation that fell back to the language model has no number of the
  // program's own; the old one must not stand above the new report.
  if (!state.headline) document.getElementById('heroCard').style.display = 'none';
  addSystem(recalcOutcome(was, state.headline));
  offerRecalc();
}
function headlineValue(h) {
  if (!h) return null;
  return h.net != null ? h.net : (h.cons != null ? h.cons : h.terr);
}
function recalcOutcome(was, now) {
  const a = headlineValue(was), b = headlineValue(now);
  if (b == null) return 'Kalkylen är omräknad, men programmet kunde inte räkna den den här gången. ' +
    'Rapportens siffror är språkmodellens egna. Läs dem med försiktighet.';
  if (a == null) return 'Kalkylen är omräknad, och rapporten är uppdaterad.';
  const unit = now.year ? ' ton CO₂e år ' + now.year : ' ton CO₂e per år';
  if (fmt(a) === fmt(b)) return 'Kalkylen är omräknad och gav samma resultat, ' + fmt(b) + unit + '. ' +
    'Anmärkningarna gällde alltså inte hur antagandena lästes in. Vill du ändra ett antagande, gör en ny analys med det ändrat.';
  return 'Kalkylen är omräknad: ' + fmt(a) + ' blev ' + fmt(b) + unit + '. Rapporten är uppdaterad. ' +
    'Läs det viktigaste i kalkylen och i QA-granskningen för att se vad som ändrades.';
}

// QA runs after the headline is drawn. A warning from it belongs next to the
// number it is about, or a result QA doubts reads as settled (2026-10-13: a
// 0,1-ton result QA had flagged stood unmarked above it).
function markHeroWithQa(verdict) {
  const warn = document.getElementById('heroWarn');
  if (!warn) return;
  // A re-run that no longer warns takes the old warning away with it.
  warn.querySelectorAll('.qa-warn').forEach(el => el.remove());
  if (!warn.children.length) warn.style.display = 'none';
  if (!verdict || verdict.status !== 'varning') return;
  if (document.getElementById('heroCard').style.display === 'none') return;
  warn.appendChild(qaWarnBox(verdict));
  warn.style.display = '';
}
// One short line that is never cut, everything else behind "Läs mer"
// (2026-10-15: the remark cut at 160 characters and "Se steg 6" read as
// broken and pointed nowhere a reader could find).
const QA_GIST_MAX = 150;
function qaGist(remark) {
  const text = plainTerms(readableNumbers(remark || '')).trim();
  // The first sentence: up to a full stop followed by a capital or the end, so
  // "t.ex." and "ca." do not end it.
  const m = text.match(/^.+?[.!?](?=\s+[A-ZÅÄÖ]|\s*$)/);
  const first = (m ? m[0] : text).trim();
  return first.length <= QA_GIST_MAX ? first : '';
}
function qaList(items) {
  const ul = document.createElement('ul');
  items.forEach(t => {
    const li = document.createElement('li');
    li.textContent = plainTerms(readableNumbers(t));
    ul.appendChild(li);
  });
  return ul;
}
function qaWarnBox(verdict) {
  const box = document.createElement('div');
  box.className = 'qa-warn';
  const line = document.createElement('p');
  const head = document.createElement('span');
  head.className = 'qa-warn-head';
  head.textContent = 'Kvalitetsgranskningen varnar för resultatet.';
  line.appendChild(head);
  const gist = qaGist(verdict.remarks[0]);
  if (gist) line.appendChild(document.createTextNode(' ' + gist));
  else if (verdict.remarks.length > 1) line.appendChild(document.createTextNode(' Den har ' + verdict.remarks.length + ' anmärkningar.'));
  box.appendChild(line);
  const suggestions = verdict.suggestions || [];
  const step = panelSection('qa');
  // Nothing more to show than the line itself: no "Läs mer" that opens on nothing.
  const hidden = verdict.remarks.length > (gist ? 1 : 0) || suggestions.length || step;
  if (!hidden) return box;
  const more = document.createElement('details');
  more.innerHTML = '<summary><span class="when-closed">Läs mer</span><span class="when-open">Visa mindre</span></summary>';
  const body = document.createElement('div');
  body.className = 'qa-more';
  if (verdict.remarks.length) {
    const p = document.createElement('p');
    p.textContent = verdict.remarks.length === 1 ? 'Granskningens anmärkning:' : 'Granskningens anmärkningar:';
    body.appendChild(p); body.appendChild(qaList(verdict.remarks));
  }
  if (suggestions.length) {
    const p = document.createElement('p');
    p.textContent = 'Det granskningen föreslår:';
    body.appendChild(p); body.appendChild(qaList(suggestions));
  }
  if (step) {
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'qa-open-step';
    open.textContent = 'Öppna hela kvalitetsgranskningen';
    open.addEventListener('click', showQaStep);
    body.appendChild(open);
  }
  more.appendChild(body);
  box.appendChild(more);
  return box;
}
// The step sits in the folded-away trail under the report.
function showQaStep() {
  const feed = document.getElementById('analysisFeed');
  if (feed && feed.style.display === 'none') toggleTrail();
  const sec = panelSection('qa');
  if (sec) sec.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function panelStepError(step, msg) {
  let sec = panelSection(step);
  if (!sec) { panelStepStart(step); sec = panelSection(step); }
  if (!sec) return;
  sec.className = 'step-sec';
  const st = sec.querySelector('.step-sec-status');
  if (st) st.innerHTML = '<span style="color:var(--kk-red)">fel</span>';
  const body = sec.querySelector('.step-sec-body');
  if (body) body.innerHTML = '<div style="color:var(--kk-red);font-size:12.5px">' + escapeHtml(msg || 'Steget misslyckades') + '</div>';
}

// What a step's section shows right now, so a failed re-run can put it back.
// The nodes are kept, not their HTML: the chips and toggles in them keep
// their listeners and whatever the user had opened. A note left by an earlier
// failed re-run is dropped first, so two failures do not stack two notes.
function panelSnapshot(step) {
  const sec = panelSection(step);
  if (!sec) return null;
  clearStepNote(step);
  return {className: sec.className, nodes: Array.from(sec.childNodes)};
}

// The version taken by panelSnapshot, back on screen as it was.
function panelStepPutBack(step, snapshot) {
  const sec = panelSection(step);
  if (!sec || !snapshot) return false;
  sec.className = snapshot.className;
  sec.replaceChildren(...snapshot.nodes);
  return true;
}

// A comment at a gate re-runs the step. The version stays on screen, dimmed,
// until the new one is drawn: the user is reading it, and the comment is
// about it (2026-10-13: the analysis used to vanish behind a
// spinner). The line saying so is a node of its own, so putting the snapshot
// back takes it away with everything else.
function panelStepUpdating(step) {
  const sec = panelSection(step);
  const body = sec && sec.querySelector('.step-sec-body');
  if (!body) { panelStepStart(step); return; }
  sec.classList.add('updating');
  const line = document.createElement('div');
  line.className = 'step-sec-updating';
  line.innerHTML = '<span class="mini-spin"></span>Uppdaterar efter din kommentar...';
  sec.insertBefore(line, body);
}

function clearStepNote(step) {
  const sec = panelSection(step);
  if (sec) sec.querySelectorAll('.step-sec-note').forEach(n => n.remove());
}

// A re-run from a gate failed. The approve button comes back and approves the
// previous version, so that is what the section has to show: panelStepError
// put the error text where the version was, and the user approved something
// no longer on screen. The previous content goes back, and the error is said
// in a note above it. Returns whether there was a version to put back.
function panelStepRestore(step, snapshot, msg) {
  if (!panelStepPutBack(step, snapshot)) { panelStepError(step, msg); return false; }
  const sec = panelSection(step);
  const note = document.createElement('div');
  note.className = 'step-sec-note';
  const head = document.createElement('div');
  head.className = 'step-sec-note-head';
  head.textContent = 'Ändringen gick inte igenom. Det här är den tidigare versionen, och det är den du godkänner.';
  const why = document.createElement('div');
  why.className = 'step-sec-note-why';
  why.textContent = msg || 'Steget misslyckades';
  note.appendChild(head); note.appendChild(why);
  sec.insertBefore(note, sec.querySelector('.step-sec-body'));
  note.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  return true;
}

// Hero + scenario range from the deterministic kalkyl result (before the report).
// The label names what the number is and the years it averages over, which
// in follow-up mode run from the first grant year rather than 2026. Without
// the calc's window (a saved report, the LLM fallback) a follow-up label
// names no years rather than the wrong ones.
// Since 2026-10-13 a potential-mode headline is the reduction in the target
// year, and says so; a headline without a year is an
// average, as follow-ups, the LLM fallback and reports saved before are.
function setHeroLabel(modeName, win, year) {
  const m = MODES[modeName] || MODES.potential;
  if (year) { document.getElementById('heroLabel').textContent = m.hero + ' år ' + year; return; }
  const w = win || (modeName === 'uppfoljning' ? null : AVG_WINDOW);
  document.getElementById('heroLabel').textContent =
    m.hero + ', medel per år' + (w ? ' ' + w[0] + '–' + w[1] : '');
}
function yearSpan(a, b) { return a === b ? String(a) : a + '–' + b; }

/* ---------- right panel: year-by-year chart ---------- */
// How the headline is built: the benefit per year in the middle scenario, the
// low-to-high band, the years "medel per år" averages over, the target year.
// Drawn at the width it gets, so the text keeps its size on a phone and on a
// projector alike. Inline SVG, no chart library.
let heroChartData = null;
function chartSeriesOk(s) {
  return !!(s && Array.isArray(s.years) && s.years.length >= 2
    && ['min', 'med', 'max'].every(k => Array.isArray(s[k]) && s[k].length === s.years.length
      && s[k].every(v => typeof v === 'number' && isFinite(v))));
}
function renderHeroChart(span, headlineValue, targetValue) {
  const fig = document.getElementById('heroChart');
  const track = document.getElementById('scenTrack');
  const s = span && span.series;
  if (!chartSeriesOk(s) || [].concat(s.min, s.med, s.max).every(v => v === 0)) {
    heroChartData = null;
    fig.style.display = 'none';
    track.style.display = '';
    return;
  }
  heroChartData = Object.assign({}, span, {headlineValue, targetValue});
  fig.style.display = '';
  track.style.display = 'none';
  drawHeroChart(heroChartData, true);
}
function drawHeroChart(span, animate) {
  const s = span.series, years = s.years, n = years.length;
  const box = document.getElementById('heroChartSvg');
  const W = Math.max(280, Math.round(box.clientWidth || 600)), H = 150;
  const padL = 10, padR = 10, padT = 24, padB = 24;
  const all = [].concat(s.min, s.med, s.max);
  const lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  const step = (W - padL - padR) / (n - 1);
  const X = i => padL + step * i;
  const Y = v => padT + (H - padT - padB) * (hi - v) / ((hi - lo) || 1);
  const r1 = v => Math.round(v * 10) / 10;
  const at = (k, yr) => s[k][years.indexOf(yr)];
  const parts = [];
  // The averaging window, or in a follow-up the years already done.
  const win = span.window || [];
  const inRange = yr => years.indexOf(yr) >= 0;
  let avg = null;
  if (win.length === 2 && inRange(win[0]) && inRange(win[1])) {
    const i0 = years.indexOf(win[0]), i1 = years.indexOf(win[1]);
    const shadeTo = span.followup ? Math.min(years.indexOf(Math.max(win[0], Math.min(span.followup.year, win[1]))), i1) : i1;
    if (!span.followup || span.followup.year >= win[0]) {
      const xa = Math.max(padL, X(i0) - step / 2), xb = Math.min(W - padR, X(shadeTo) + step / 2);
      parts.push('<rect class="chart-window" x="' + r1(xa) + '" y="' + padT + '" width="' + r1(xb - xa) + '" height="' + (H - padT - padB) + '" rx="3"/>');
    }
    const ys = s.med.slice(i0, i1 + 1);
    avg = ys.reduce((a, b) => a + b, 0) / ys.length;
  }
  // The number written is the headline as the card shows it. The mean of the
  // series is the same number unrounded, and rounding it a second time could
  // put 412 under a headline of 413. The mean only places the dashed line.
  const shownAvg = typeof span.headlineValue === 'number' ? span.headlineValue : Math.round(avg * 10) / 10;
  parts.push('<line class="chart-zero" x1="' + padL + '" x2="' + (W - padR) + '" y1="' + r1(Y(0)) + '" y2="' + r1(Y(0)) + '"/>');
  const upper = years.map((_, i) => r1(X(i)) + ',' + r1(Y(Math.max(s.min[i], s.max[i]))));
  const lower = years.map((_, i) => r1(X(i)) + ',' + r1(Y(Math.min(s.min[i], s.max[i])))).reverse();
  parts.push('<polygon class="chart-band" points="' + upper.concat(lower).join(' ') + '"/>');
  // The average on top of the band, named where it starts.
  if (avg != null) {
    const xa = X(years.indexOf(win[0])), xb = X(years.indexOf(win[1])), ya = Y(avg);
    parts.push('<line class="chart-avg" x1="' + r1(xa) + '" x2="' + r1(xb) + '" y1="' + r1(ya) + '" y2="' + r1(ya) + '"/>');
    const ty0 = ya - 6 < 12 ? ya + 15 : ya - 6;
    parts.push('<text class="chart-text avg" x="' + r1(xa + 4) + '" y="' + r1(ty0) + '">medel ' + escapeHtml(fmt(shownAvg)) + '</text>');
  }
  parts.push('<polyline class="chart-line" points="' + years.map((_, i) => r1(X(i)) + ',' + r1(Y(s.med[i]))).join(' ') + '"/>');
  // The target year: a dot and its value.
  const ty = span.target_year, ti = years.indexOf(ty);
  // The target year's value as the card shows it, when the card shows it.
  const tyValue = typeof span.targetValue === 'number' ? span.targetValue : (ti >= 0 ? s.med[ti] : null);
  if (ti >= 0) {
    const cx = X(ti), cy = Y(s.med[ti]);
    const anchor = cx > W - 70 ? 'end' : (cx < 70 ? 'start' : 'middle');
    const ly = cy - 10 < 12 ? cy + 20 : cy - 10;
    parts.push('<circle class="chart-dot" cx="' + r1(cx) + '" cy="' + r1(cy) + '" r="5"/>');
    parts.push('<text class="chart-text strong" x="' + r1(cx) + '" y="' + r1(ly) + '" text-anchor="' + anchor + '">' + escapeHtml(fmt(tyValue)) + '</text>');
  }
  // Year labels, never on top of each other: the window and the target year
  // first, then the ends, then (when there is room) every year.
  const anchorOf = i => i === 0 ? 'start' : (i === n - 1 ? 'end' : 'middle');
  const extent = i => {  // a year label is about 30 px wide at 12 px
    const x = X(i), a = anchorOf(i);
    return a === 'start' ? [x, x + 30] : (a === 'end' ? [x - 30, x] : [x - 15, x + 15]);
  };
  const placed = [];
  [win[0], win[1], ty, years[0], years[n - 1]].concat(years).forEach(yr => {
    if (!inRange(yr) || placed.indexOf(yr) >= 0) return;
    const e = extent(years.indexOf(yr));
    if (placed.some(p => { const o = extent(years.indexOf(p)); return e[0] < o[1] + 8 && o[0] < e[1] + 8; })) return;
    placed.push(yr);
  });
  placed.forEach(yr => {
    const i = years.indexOf(yr), x = X(i);
    const anchor = anchorOf(i);
    parts.push('<text class="chart-text" x="' + r1(x) + '" y="' + (H - 6) + '" text-anchor="' + anchor + '">' + yr + '</text>');
  });
  // The caption says in words what the chart shows, and is its text alternative.
  const unit = ' ton CO₂e/år';
  const sentences = [];
  const byYear = span.headline_year != null && span.headline_year === ty && ti >= 0;
  if (byYear) {
    sentences.push('Rubriksiffran är år ' + ty + ' (punkten): <b>' + fmt(tyValue) + '</b>' + unit + '.');
    if (avg != null) sentences.push('Medel för ' + yearSpan(win[0], win[1]) + ' (grått fält) är <b>' + fmt(shownAvg) + '</b>' + unit + '.');
  } else {
    if (avg != null) sentences.push('Rubriksiffran är medel för ' + yearSpan(win[0], win[1]) + (span.followup ? '' : ' (grått fält)') + ': <b>' + fmt(shownAvg) + '</b>' + unit + '.');
    if (ti >= 0) sentences.push('År ' + ty + ' ger åtgärden <b>' + fmt(tyValue) + '</b>' + unit + '.');
  }
  sentences.push('Det ljusa bandet går från lågt till högt scenario.');
  const caption = sentences.join(' ');
  document.getElementById('heroChartCaption').innerHTML = caption;
  const label = caption.replace(/<[^>]+>/g, '');
  box.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="' + escapeHtml(label).replace(/"/g, '&quot;') + '">' + parts.join('') + '</svg>';
  const line = box.querySelector('.chart-line');
  if (animate && line && line.getTotalLength) {
    const len = Math.ceil(line.getTotalLength());
    line.style.strokeDasharray = len;
    line.style.setProperty('--len', len);
    line.classList.add('draw');
  }
}
let chartResizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(chartResizeTimer);
  chartResizeTimer = setTimeout(() => {
    try { if (heroChartData && document.getElementById('heroChart').offsetParent) drawHeroChart(heroChartData, false); }
    catch (e) { /* keep the last drawing */ }
  }, 150);
});

// The numbers under the headline, each with its range: the headline year's
// low to high, the average per year and the total to the target year. A saved
// analysis from before the ranges were sent shows what it has.
function rangeText(lo, hi) {
  if (lo == null || hi == null) return '';
  const a = Math.min(lo, hi), b = Math.max(lo, hi);
  return a < 0 ? fmt(a) + ' till ' + fmt(b) : fmt(a) + '–' + fmt(b);
}
function heroFigures(headline, span, lo, hi, win) {
  const fig = (label, value, unit, note) => '<div class="fig"><div class="fig-label">' + label + '</div>' +
    '<div class="fig-value">' + value + ' <small>' + unit + '</small></div>' +
    (note ? '<div class="fig-note">' + note + '</div>' : '') + '</div>';
  const out = [];
  out.push(fig(headline.year ? 'Spann ' + headline.year : 'Spann', rangeText(lo, hi), 'ton CO₂e/år',
               'försiktigt till optimistiskt'));
  if (headline.year && span.avg_net != null && win.length === 2) {
    const r = rangeText(span.avg_lo, span.avg_hi);
    out.push(fig('Snitt per år ' + yearSpan(win[0], win[1]), fmt(span.avg_net), 'ton CO₂e/år', r ? 'spann ' + r : ''));
  }
  if (span.cum_net != null) {
    const r = rangeText(span.cum_lo, span.cum_hi);
    out.push(fig('Sammanlagt till ' + (span.target_year || 'målåret'), fmt(span.cum_net), 'ton CO₂e', r ? 'spann ' + r : ''));
  }
  return out.length > 1 ? out.join('') : '';
}

function renderKalkylHero(headline, span, warnings) {
  if (!headline) return;
  showAnalysisCard();
  updateHero(headline);
  setHeroLabel((span && span.mode) || state.mode, span && span.window, headline.year);
  // A new number: the last report's interpretation was about the old one.
  setHeroInterpretation('');
  // The calc's own warnings (a negative result, an effect outside the years the
  // average covers, no effect at all) belong next to the number they qualify.
  const warn = document.getElementById('heroWarn');
  if (warnings && warnings.length) {
    warn.innerHTML = warnings.map(w => '<div>' + escapeHtml(w) + '</div>').join('');
    warn.style.display = '';
  } else { warn.innerHTML = ''; warn.style.display = 'none'; }
  const el = document.getElementById('heroScenario');
  if (span && span.net_lo != null && span.net_hi != null) {
    const lo = span.net_lo, hi = span.net_hi;
    const mid = headline.net != null ? headline.net : (headline.cons != null ? headline.cons : headline.terr);
    document.getElementById('scenLo').innerHTML = 'Låg <b>' + fmt(lo) + '</b>';
    document.getElementById('scenHi').innerHTML = 'Hög <b>' + fmt(hi) + '</b>';
    let pct = 50;
    if (hi > lo && mid != null) pct = Math.max(4, Math.min(96, (mid - lo) / (hi - lo) * 100));
    document.getElementById('scenMarker').style.left = pct + '%';
    const cum = document.getElementById('scenCum');
    cum.innerHTML = '';
    const win = span.window || [];
    const figs = heroFigures(headline, span, lo, hi, win);
    const figBox = document.getElementById('heroFigures');
    figBox.innerHTML = figs;
    figBox.style.display = figs ? '' : 'none';
    document.querySelector('#heroScenario .scenario-ends').style.display = figs ? 'none' : '';
    if (!figs) {
      // Under a target-year headline, the average per year it used to be.
      if (headline.year && span.avg_net != null && win.length === 2) {
        cum.innerHTML += '<div>Medel per år ' + yearSpan(win[0], win[1]) + ': <b>' + fmt(span.avg_net) + ' ton CO₂e/år</b></div>';
      }
      if (span.cum_net != null) cum.innerHTML += '<div>Ackumulerat till ' + (span.target_year || 'målår') + ': <b>' + fmt(span.cum_net) + ' ton CO₂e</b></div>';
    }
    // Follow-up: what has happened and what is still expected, medel scenario.
    // Same clamping as the calc text (calc.engine._followup_lines).
    const f = span.followup;
    const w0 = (span.window || [])[0], w1 = span.target_year;
    if (f && f.realised && f.remaining && w0 != null && w1 != null) {
      const parts = [];
      if (f.year >= w0) parts.push('Realiserat ' + yearSpan(w0, Math.min(f.year, w1)) + ': <b>' + fmt(f.realised.med) + ' ton CO₂e</b>');
      if (f.year < w1) parts.push((parts.length ? 'återstår ' : 'Återstår ') + yearSpan(Math.max(f.year + 1, w0), w1) + ': <b>' + fmt(f.remaining.med) + ' ton CO₂e</b>');
      cum.innerHTML += '<div>' + parts.join(', ') + '</div>';
    }
    el.style.display = '';
    // After display: it is drawn at the width it gets. A chart that cannot be
    // drawn falls back to the range bar; it must never fail the kalkyl step.
    // The chart writes the average on its dashed line: the headline itself
    // only when the headline is the average.
    try { renderHeroChart(span, headline.year ? span.avg_net : mid, headline.year ? mid : undefined); }
    catch (e) {
      heroChartData = null;
      document.getElementById('heroChart').style.display = 'none';
      document.getElementById('scenTrack').style.display = '';
    }
  } else {
    el.style.display = 'none';
    heroChartData = null;
  }
}

/* ---------- right panel: åtgärdsprofil (step 1) ---------- */
// The profile is what the whole analysis is about, so it sits first in the feed
// and stays there while the later steps build under it. It is rendered from
// parsed fields rather than raw markdown so assumptions can be marked per field.
function profileFieldHtml(field, previous) {
  const value = (field.value || '').trim();
  const valueHtml = value
    ? escapeHtml(value)
    : '<span class="pf-value empty">inte angivet</span>';
  const chip = (field.assumptions && field.assumptions.length)
    ? ' <span class="kalla-chip antag">antagande</span>' : '';
  const notes = (field.assumptions || [])
    .filter(n => n && n.trim())
    .map(n => '<span class="pf-note">' + escapeHtml(n) + '</span>')
    .join('');
  // `previous` is undefined on a first render, which is not a change: a card
  // where every row is flagged says nothing about what the correction did.
  const oldValue = previous ? (previous.value || '').trim() : value;
  const changed = oldValue !== value;
  const was = changed && oldValue
    ? '<span class="pf-was">' + escapeHtml(oldValue) + '</span>' : '';
  return '<div class="pf-label">' + escapeHtml(field.label) + '</div>' +
         '<div class="pf-value' + (changed ? ' changed' : '') + '">' + valueHtml + chip +
         (changed ? ' <span class="kalla-chip andrad">ändrad</span>' : '') + was + notes + '</div>';
}

function profileCardHtml(profile, total, previous, isUpdate) {
  // `position` counts the cards actually shown; `index` is the agent's own
  // numbering and is only used to match a card against its previous version.
  const counter = total > 1
    ? '<div class="pf-count">Åtgärd ' + (profile.position || profile.index) + ' av ' + total + '</div>' : '';
  const fields = profile.fields || [];
  const desc = fields.find(f => f.label.toLowerCase() === 'beskrivning');
  const rest = fields.filter(f => f !== desc);
  const prevField = (label) => previous
    ? (previous.fields || []).find(f => f.label.toLowerCase() === label.toLowerCase())
    : undefined;
  const descChanged = previous && desc &&
    (prevField('beskrivning') || {}).value !== desc.value;
  // A profile the parser could not read is shown as the agent wrote it. It has
  // to appear somewhere: it travels on to the downstream agents either way.
  const bodyHtml = profile.unparsed
    ? '<div class="pf-unparsed">' + renderMarkdown(profile.unparsed) + '</div>'
    : (desc ? '<p class="pf-desc">' + escapeHtml(desc.value) +
        (descChanged ? ' <span class="kalla-chip andrad">ändrad</span>' : '') + '</p>' : '') +
      '<div class="pf-grid">' +
        rest.map(f => profileFieldHtml(f, prevField(f.label))).join('') +
      '</div>';
  return '<div class="pf-card">' +
    '<div class="pf-head"><div class="pf-name">' + escapeHtml(profile.name) + '</div>' +
    (isUpdate && !previous ? '<span class="kalla-chip andrad">ny åtgärd</span>' : '') +
    counter + '</div>' + bodyHtml + '</div>';
}

// `fallbackText` is what the agent actually wrote. It is rendered whenever the
// parse came back empty, so a template the model drifted from degrades to
// readable markdown in the panel instead of an empty card.
function renderProfiles(profiles, fallbackText, isUpdate) {
  showAnalysisCard();
  const feed = document.getElementById('analysisFeed');
  let sec = panelSection('intake');
  if (!sec) {
    sec = document.createElement('div');
    sec.dataset.pstep = 'intake';
    feed.insertBefore(sec, feed.firstChild);
  }
  // Not `done` yet: the step is finished but the profile is unreviewed, and a
  // green check next to an approve button reads as "already verified".
  sec.className = 'step-sec profile';

  const list = profiles || [];
  const previous = state.profiles || [];
  const priorFor = (profile) => isUpdate
    ? previous.find(p => p.index === profile.index) : undefined;

  const assumptions = list.reduce((n, p) => n + (p.assumption_count || 0), 0);
  const status = [];
  if (list.length > 1) status.push(list.length + ' åtgärder');
  if (assumptions) status.push(assumptions + (assumptions === 1 ? ' antagande' : ' antaganden'));
  if (isUpdate) status.push('uppdaterad ' + new Date().toLocaleTimeString('sv-SE', {hour: '2-digit', minute: '2-digit'}));

  const body = list.length
    ? list.map(p => profileCardHtml(p, list.length, priorFor(p), isUpdate)).join('')
    : '<div class="pf-raw">' + renderMarkdown(cleanOutput(fallbackText)) + '</div>';
  state.profiles = list;

  sec.innerHTML =
    '<div class="step-sec-head"><span class="step-sec-num">1</span>' +
    '<span class="step-sec-title">Åtgärdsprofil</span>' +
    '<span class="step-sec-status">' + escapeHtml(status.join(' · ') || 'klar') + '</span></div>' +
    '<div class="step-sec-body">' + body + '</div>';
  if (isUpdate) {
    // Re-adding a class that is already there does not restart the animation,
    // and the second correction in a row is exactly when the flash is needed.
    sec.classList.remove('pf-updated');
    void sec.offsetWidth;
    sec.classList.add('pf-updated');
  }
  sec.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

/* ---------- right panel: evidens (step 4) ---------- */
// The gate where the user approves the numbers. The agent writes prose with
// fixed labels; the panel puts the decision content back into a table and folds
// the reasoning underneath it.
function evidenceQualityChip(kvalitet) {
  const value = (kvalitet || '').trim();
  if (!value) return '';
  const key = value.toLowerCase();
  const cls = key.indexOf('hög') === 0 || key.indexOf('hog') === 0 ? 'kval-hog'
            : key.indexOf('låg') === 0 || key.indexOf('lag') === 0 ? 'kval-lag' : 'kval-medel';
  return '<span class="kalla-chip ' + cls + '">kvalitet ' + escapeHtml(value) + '</span>';
}

function evidenceSpanHtml(parameter) {
  const cell = (label, value, mid) =>
    '<div class="ev-span-cell' + (mid ? ' mid' : '') + '">' +
    '<div class="ev-span-lab">' + label + '</div>' +
    '<div class="ev-span-val">' + (value ? escapeHtml(value) : '–') + '</div></div>';
  return '<div class="ev-span">' +
    cell('Försiktigt', parameter.min, false) +
    cell('Troligt', parameter.med, true) +
    cell('Optimistiskt', parameter.max, false) +
    '</div>';
}

// A chip has to stay one short token. Real output puts whole sentences in the
// Källor field ("Kommunala fordonsupphandlingskrav är väl beprövade och ..."),
// which overflows the pill and gets clipped, so long ones become plain text.
const SOURCE_CHIP_MAXLEN = 46;

// What a parameter is called on its card. The agent names it like a variable
// (ADOPTION_EXTRA_HANDLARE) and says what it is in parentheses after the name;
// the card leads with what it is (2026-10-13: no
// variable names with underscores and without å, ä, ö as titles). A name with no
// description is at least written as words.
function paramTitle(parameter) {
  const detail = (parameter.detail || '').trim();
  if (detail) return parameter.detail;
  const name = (parameter.name || '').trim();
  return name.includes('_') ? name.replace(/_+/g, ' ').trim().toLowerCase() : parameter.name;
}
function capitalized(text) { return text ? text.charAt(0).toUpperCase() + text.slice(1) : text; }

function evidenceParamHtml(parameter) {
  const meta = [];
  if (parameter.kvalitet) meta.push(evidenceQualityChip(parameter.kvalitet));
  if (parameter.lokaliserbarhet) {
    meta.push('<span class="kalla-chip">lokalisering ' + escapeHtml(parameter.lokaliserbarhet) + '</span>');
  }
  const notes = [];
  (parameter.kallor || []).forEach(source => {
    if (source.length <= SOURCE_CHIP_MAXLEN) {
      meta.push('<span class="kalla-chip">' + escapeHtml(source) + '</span>');
    } else {
      notes.push(source);
    }
  });
  const title = paramTitle(parameter);
  const unit = [title === parameter.detail ? '' : parameter.detail, parameter.enhet, parameter.tidsaspekt]
    .filter(Boolean).join(' · ');
  // The code the agent named it by is not shown under it: it said nothing a
  // reader could use (ΔA_ändrare, andel_utanför), and a library parameter is
  // in the Parametrar table by name and code.
  return '<div class="ev-param">' +
    '<div class="ev-param-head"><span class="ev-param-name">' + escapeHtml(capitalized(title)) + '</span></div>' +
    (unit ? '<div class="ev-param-unit">' + escapeHtml(unit) + '</div>' : '') +
    evidenceSpanHtml(parameter) +
    (meta.length ? '<div class="ev-meta">' + meta.join('') + '</div>' : '') +
    (notes.length ? '<div class="ev-src">' + notes.map(n =>
      'Källa: ' + escapeHtml(n)).join('<br>') + '</div>' : '') +
    (parameter.kommentar ? '<div class="ev-komm">' + escapeHtml(parameter.kommentar) + '</div>' : '') +
    '</div>';
}

function evidenceDriverHtml(driver) {
  const f = driver.factors || {};
  // The three are shares of the effect (0 to 1 in the agent's text), so they
  // read as percent: "5 %" says at once what "0,05" makes the reader work out
  // (2026-10-13). Note 0 % is a real value here (an enabler whose
  // effect is counted on another driver), not a missing one.
  const factorText = (value) => {
    if (value == null) return '–';
    return (value * 100).toLocaleString('sv-SE', {maximumFractionDigits: 1}) + ' %';
  };
  const ft = driver.factors_text || {};
  // When the agent wrote a reason instead of a number, show the reason. It says
  // "counted on another driver", which is the thing a reviewer needs to know.
  const factor = (value, label, key) => {
    const words = (ft[key] || '').trim();
    const numeric = value != null;
    const body = numeric ? factorText(value) : (words || '–');
    return '<div class="ev-factor"><div class="ev-factor-val' + (numeric ? '' : ' words') + '">' +
      escapeHtml(body) + '</div><div class="ev-factor-lab">' + label + '</div></div>';
  };
  const hasFactors = f.territoriell != null || f.konsumtion != null || f.overlap != null
    || ft.territoriell || ft.konsumtion || ft.overlap;
  return '<div class="ev-card">' +
    '<div class="ev-head"><span class="ev-num">' + driver.number + '</span>' +
    '<span class="ev-name">' + escapeHtml(driver.name) + '</span></div>' +
    (driver.mekanism ? '<p class="ev-mek">' + escapeHtml(driver.mekanism.replace(/^(Avoid|Shift|Improve)\b/i,
      (m) => EMAP_MECHANISM[m.toLowerCase()])) + '</p>' : '') +
    (hasFactors ? '<div class="ev-factors">' +
      factor(f.territoriell, 'Territoriell', 'territoriell') +
      factor(f.konsumtion, 'Konsumtion', 'konsumtion') +
      factor(f.overlap, 'Överlapp', 'overlap') + '</div>' : '') +
    (f.motivering ? '<div class="ev-motiv">' + escapeHtml(f.motivering) + '</div>' : '') +
    (driver.parameters || []).map(evidenceParamHtml).join('') +
    (driver.extra || []).map(e =>
      '<div class="ev-extra"><b>' + escapeHtml(e.label) + ':</b> ' + escapeHtml(e.value) + '</div>').join('') +
    '</div>';
}

function toggleEvidenceProse(el) {
  el.closest('.ev-prose').classList.toggle('open');
}

// `fallbackText` is the agent's raw output, rendered whenever no driver parsed.
function renderEvidence(evidence, fallbackText) {
  const cfg = PANEL_STEPS.evidens;
  let sec = panelSection('evidens');
  if (!sec) { panelStepStart('evidens'); sec = panelSection('evidens'); }
  if (!sec) return;

  // Drawn as escaped text, so the words go in here (see plainWords).
  evidence = plainTermsDeep(evidence);
  const drivers = (evidence && evidence.drivers) || [];
  if (!drivers.length) { panelStepDone('evidens', fallbackText); return; }

  const params = drivers.reduce((n, d) => n + ((d.parameters || []).length), 0);
  const status = [drivers.length + (drivers.length === 1 ? ' drivare' : ' drivare')];
  if (params) status.push(params + (params === 1 ? ' parameter' : ' parametrar'));

  const prose = (evidence.sections || []).filter(s => s.body);
  const proseHtml = prose.length
    ? '<div class="ev-prose"><button class="ev-prose-toggle" onclick="toggleEvidenceProse(this)">' +
      '<span class="trail-caret">›</span>Visa CAIA:s resonemang och källor</button>' +
      '<div class="ev-prose-body">' + prose.map(s =>
        '<div class="ev-prose-sec">' + escapeHtml(s.title) + '</div>' +
        renderMarkdownWithChips(s.body)).join('') + '</div></div>'
    : '';

  sec.className = 'step-sec evidens done';
  sec.innerHTML =
    '<div class="step-sec-head"><span class="step-sec-num">✓</span>' +
    '<span class="step-sec-title">' + cfg.title + '</span>' +
    '<span class="step-sec-status">' + escapeHtml(status.join(' · ')) + '</span></div>' +
    '<div class="step-sec-body">' + keyPointsSafely(() => keyPointsHtml(evidenceKeyPoints(drivers))) +
    drivers.map(evidenceDriverHtml).join('') + proseHtml + '</div>';
}

function toggleTrail() {
  const t = document.getElementById('trailToggle');
  const feed = document.getElementById('analysisFeed');
  const open = feed.style.display === 'none';
  feed.style.display = open ? '' : 'none';
  t.classList.toggle('open', open);
  document.getElementById('trailLabel').textContent = open ? 'Dölj analysunderlag' : 'Visa analysunderlag (alla steg)';
}

/* ---------- intake ---------- */
async function sendMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text || state.running) return;

  // A first message with a saved report on screen starts a new analysis.
  // openSaved hides the feed the steps draw into, so the analysis ran unseen
  // behind the old report and its number, gates included.
  if (state.phase === 'idle' && state.history.length === 0 && state.reportMarkdown) resetAll();

  input.value = ''; input.style.height = 'auto';
  addUser(text);
  lockMode(true);

  // After the report, a message used to restart intake and drop the user back
  // at the profile gate with the finished report still on screen. The gates
  // teach people to answer in the chat, so that is easy to hit by accident.
  if (state.phase === 'done') {
    addSystem('Analysen är klar, så jag räknar inte om den här. Vill du pröva en ändrad version av åtgärden: klicka Ny analys och beskriv den justerade åtgärden.');
    return;
  }

  const feedback = {role:'user', content:text};
  state.history.push(feedback);
  setInputEnabled(false); state.running = true;
  const token = runToken;

  // Feedback at a gate re-runs that gate's own step with the feedback in the
  // history, and leaves the user standing at the same gate. The profile gate is
  // the exception: it re-runs intake, which has its own clarifying dialogue and
  // falls through to the block below.
  const gate = GATES[state.phase];
  if (gate && state.phase !== 'profile') {
    showApprove(false);
    updateProgress(gate.step, false);
    // The version on screen is the one the approve button approves if the
    // re-run fails, so it is kept while the section shows the spinner.
    const previous = panelSnapshot(gate.step);
    panelStepUpdating(gate.step);
    let applied = false, restored = false, answered = false, kept = false;
    try {
      const {ok, data} = await postStep(gate.step, state.history, {feedback: true});
      if (token !== runToken) return;  // "Ny analys" happened while we waited
      answered = true;
      if (!ok) { restored = panelStepRestore(gate.step, previous, data.error); addSystem(data.error || 'Okänt fel', true); }
      else {
        // The answer to the comment is said in the chat, where it was asked;
        // the panel only ever holds the analysis.
        const reply = (data.reply || '').trim();
        if ((data.output || '').trim()) {
          // Drawn first, then counted: a new version that cannot be drawn must
          // not go into the history behind a panel that shows the old one.
          // The reply waits for it too: "jag ändrade X" beside a version that
          // could not be shown would say the opposite of the panel.
          const before = state.history[state.history.length - 2];
          const parts = renderStepOutput(gate.step, data);
          state.history.push({role:'assistant', content:data.output});
          applied = true;
          // The new version's gaps and questions are said again only when
          // they changed; the introduction was said the first time.
          const was = before && before.role === 'assistant' ? stepParts(gate.step, before.content).followUp : '';
          const changed = parts && parts.followUp && parts.followUp !== was ? parts.followUp : '';
          const said = [reply, changed].filter(Boolean).join('\n\n');
          if (said) addVoice(said, gate.step);
          addSystem(STEP_LABELS[gate.step] + ' uppdaterad i panelen. Granska och godkänn, eller skriv mer feedback.');
        } else {
          // A reply and no version: the one on screen still stands.
          if (reply) addVoice(reply, gate.step);
          kept = !!reply && panelStepPutBack(gate.step, previous);
          if (!kept) restored = panelStepRestore(gate.step, previous, 'Steget svarade utan en ny version.');
        }
      }
    } catch(e) {
      if (token !== runToken) return;
      const why = (answered ? 'Den nya versionen kunde inte visas: ' : 'Nätverksfel: ') + e.message;
      restored = panelStepRestore(gate.step, previous, why); addSystem(why, true);
    }
    if (!applied) {
      // The re-run failed, so the step that counts is still the previous one.
      // Take the feedback back out of the history: otherwise the approve
      // button, which reappears below, would push the bridge line straight
      // after an unanswered user turn and send the next agent a request
      // the user never saw honoured.
      if (state.history[state.history.length - 1] === feedback) state.history.pop();
      if (kept) addSystem(STEP_LABELS[gate.step] + ' är oförändrad i panelen. Godkänn den, eller skriv mer.');
      else addSystem(restored
        ? 'Feedbacken kunde inte tillämpas. Den tidigare versionen till höger gäller fortfarande: försök igen, eller godkänn den som den är.'
        : 'Feedbacken kunde inte tillämpas, och den tidigare versionen kunde inte visas igen. Skicka rättelsen en gång till.', true);
    }
    // No approving a version that is not on screen.
    showApprove(applied || restored || kept); setInputEnabled(true); state.running = false;
    return;
  }

  // The approve button stays hidden while intake works and while it asks
  // follow-up questions: approving then would send a profile that is being
  // rewritten. A failed call puts it back if a profile was already on screen,
  // and takes the unanswered message back out of the history, as the other
  // gates do: the text stays in the chat, and sending it again must not put
  // it in twice.
  const wasAtGate = state.phase === 'profile';
  const intakeFailed = () => {
    if (state.history[state.history.length - 1] === feedback) state.history.pop();
    if (wasAtGate) showApprove(true);
    // The very first message failed: give the text back to send again, and
    // the choice of analysis back, since nothing has been analysed yet.
    if (!state.history.length) {
      if (!input.value.trim()) input.value = text;
      lockMode(false);
    }
  };
  showApprove(false);
  addSpinner('Intake-agenten analyserar...');
  try {
    const resp = await authFetch('/api/intake', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({history: state.history, mode: state.mode})});
    const data = await resp.jsonSafe();
    if (token !== runToken) return;  // "Ny analys" happened while we waited
    removeSpinner();
    if (!resp.ok) { addSystem(data.error || 'Okänt fel', true); intakeFailed(); setInputEnabled(true); state.running=false; return; }
    // The agents downstream read the full text, so history always gets it.
    // The chat only gets what is conversational; the profile itself belongs in
    // the panel, where it can be compared against the steps built from it.
    state.history.push({role:'assistant', content:data.message});
    if (data.status === 'complete') {
      const profiles = data.profiles || [];
      const isUpdate = !!panelSection('intake');
      renderProfiles(profiles, data.message, isUpdate);
      if (profiles.length) {
        if (data.preamble && data.preamble.trim()) addVoice(data.preamble, 'intake');
      } else {
        // Parse failed: the panel shows raw markdown, and the chat keeps the
        // full answer rather than pointing at a card that never rendered.
        addVoice(data.message, 'intake');
      }
      openGate('profile', isUpdate
        ? 'Profilen uppdaterad i panelen till höger. Godkänn, eller skriv mer feedback.'
        : GATES.profile.ready);
    } else {
      addVoice(data.message, 'intake');
      if (wasAtGate) state.phase = 'intake';
    }
  } catch(e) {
    if (token !== runToken) return;
    removeSpinner(); addSystem('Nätverksfel: ' + e.message, true); intakeFailed();
  }
  setInputEnabled(true); state.running = false;
}

/* ---------- pipeline: four approval gates ---------- */
// profil -> EMAP -> baslinje -> antaganden -> beräkning.
// Every judgement step the user can act on stops and waits. Only the last leg
// (kalkyl, QA, rapport) runs straight through: by then the inputs are approved
// and the rest is calculation and write-up.
// The line that hands one step to the next, keyed by the step that finished.
// From caia.pipeline, so the offline runs send exactly what the page sends.
const BRIDGE = {{ bridge|tojson }};

// One entry per gate. `step` is what is on screen and what feedback re-runs,
// `run` is what approval sets going, `next` is the gate that follows.
const GATES = {
  profile: {
    step: 'intake', button: 'Godkänn profilen och fortsätt', bridge: BRIDGE.intake,
    run: ['emap'], next: 'emap',
    approved: 'Profilen godkänd. Tar fram vilka utsläppskällor åtgärden påverkar...',
    ready: 'Profilen är klar och visas till höger. Granska och godkänn, eller skriv feedback.',
  },
  emap: {
    step: 'emap', button: 'Godkänn utsläppskällorna och fortsätt', bridge: BRIDGE.emap,
    run: ['baslinje'], next: 'baslinje',
    approved: 'Utsläppskällorna godkända. Sätter baslinjen...',
    ready: 'Utsläppskällorna är klara. Granska dem till höger, godkänn eller skriv feedback.',
  },
  baslinje: {
    step: 'baslinje', button: 'Godkänn baslinjen och fortsätt', bridge: BRIDGE.baslinje,
    run: ['evidens'], next: 'assumptions',
    approved: 'Baslinjen godkänd. Tar fram evidens och antaganden...',
    ready: 'Baslinjen är satt. Granska den till höger, godkänn eller skriv feedback.',
  },
  assumptions: {
    step: 'evidens', button: 'Godkänn antagandena och beräkna', bridge: BRIDGE.evidens,
    run: ['kalkyl', 'qa', 'rapport'], next: 'done',
    approved: 'Antagandena godkända. Beräknar klimatnyttan...',
    ready: 'Antagandena är klara. Granska dem till höger, godkänn eller skriv feedback för att justera.',
  },
};

// Run a sequence of pipeline stages, threading history. Returns true on success.
// Each stage is a separate awaited call, so "Ny analys" can land between any two
// of them. A run whose token is stale stops writing: without this it kept
// drawing its steps into the feed of the analysis that replaced it, and pushed
// its history onto the new run's state object.
async function runStages(stages) {
  const token = runToken;
  for (let i = 0; i < stages.length; i++) {
    if (token !== runToken) return false;
    const step = stages[i];
    const inPanel = !!PANEL_STEPS[step];
    updateProgress(step, false);
    // Intermediate steps render as a live section in the right panel; rapport has
    // no panel section (it becomes the report at the top), so it keeps a chat spinner.
    if (inPanel) panelStepStart(step); else addSpinner(STEP_LABELS[step] + '...');
    try {
      const {ok, data} = await postStep(step, state.history);
      if (token !== runToken) return false;
      if (!inPanel) removeSpinner();
      if (!ok) { if (inPanel) panelStepError(step, data.error); addSystem('Fel i ' + STEP_LABELS[step] + ': ' + (data.error||'okänt'), true); return false; }
      state.history.push({role:'assistant', content:data.output});
      if (i < stages.length - 1 && BRIDGE[step]) state.history.push({role:'user', content:BRIDGE[step]});
      if (step === 'kalkyl') { state.headline = data.headline || null; state.kallmarkeringMd = data.kallmarkering_md || null; }
      if (step === 'rapport') {
        // The source section is computed, not written by the model, so it is
        // appended here and travels with the report into display, save and download.
        const report = withKallmarkering(data.output, state.kallmarkeringMd);
        state.reportMarkdown = report; addSystem('Slutrapport klar'); await finishReport(report);
      }
      else {
        const parts = renderStepOutput(step, data);
        if (parts && parts.chat) addVoice(parts.chat, step);
        // The caller always says something about the last step (the gate it
        // opens, or "analysen är klar"), so announcing it here too would say
        // the same thing twice in a row, once per gate.
        if (i < stages.length - 1) addSystem(STEP_LABELS[step] + ' klar');
      }
    } catch(e) {
      if (token !== runToken) return false;
      if (inPanel) panelStepError(step, e.message); else removeSpinner();
      addSystem('Fel i ' + STEP_LABELS[step] + ': ' + e.message, true); return false;
    }
  }
  return true;
}

// Draw one step's result into the panel. Shared by the pipeline and by a
// re-run from a gate, so a step looks the same however it got there. Returns
// the parts of the text that belong in the chat (stepParts); the caller says
// them, since a run and a re-run say different things.
function renderStepOutput(step, data) {
  if (step === 'evidens') { renderEvidence(data.evidence, data.output); return null; }
  const parts = stepParts(step, data.output);
  if (parts.emap) { renderEmap(parts.emap); return parts; }
  // A summary that cannot be read must never cost the step its panel.
  let keyPoints = '';
  try {
    if (step === 'baslinje') keyPoints = keyPointsHtml(baselineKeyPoints(data.output, parts.followUp));
    else if (step === 'kalkyl') {
      state.lastKalkyl = {headline: data.headline || null, span: data.span || null, warnings: data.warnings || []};
      keyPoints = keyPointsHtml(kalkylKeyPoints(data.headline, data.span, data.warnings),
      (data.warnings || []).length ? 'warn' : '');
    }
    else if (step === 'qa') {
      const verdict = qaVerdict(parts.panel);
      state.qaVerdict = verdict;
      keyPoints = keyPointsHtml(qaKeyPoints(verdict), verdict ? (verdict.status === 'ok' ? 'ok' : 'warn') : '');
      markHeroWithQa(verdict);
    }
  } catch (e) { keyPoints = ''; }
  panelStepDone(step, step === 'kalkyl' ? withKallmarkering(parts.panel, data.kallmarkering_md) : parts.panel, keyPoints);
  if (step === 'kalkyl') {
    if (data.headline) renderKalkylHero(data.headline, data.span, data.warnings);
    // The language model computed this one (the engine could not read the
    // form): the number, range and warnings of an earlier kalkyl in the same
    // run must not stand above it. A retry after a failed QA runs the kalkyl
    // again and can end here.
    else hideHero();
  }
  return parts;
}

// Take the number down, with what belongs to it. resetAll does the same.
function hideHero() {
  document.getElementById('heroCard').style.display = 'none';
  document.getElementById('heroScenario').style.display = 'none';
  heroChartData = null;
  document.getElementById('heroWarn').style.display = 'none';
  setHeroInterpretation('');
}

// Park the user at a gate: button labelled for it, input open for feedback.
function openGate(phase, message, isError) {
  const gate = GATES[phase];
  state.phase = phase;
  state.running = false;
  document.getElementById('btnApprove').textContent = gate.button;
  showApprove(true);
  setInputEnabled(true);
  if (message) addSystem(message, !!isError);
}

// The approve button dispatches on which gate we're at.
function onApprove() {
  if (state.running || !GATES[state.phase]) return;
  return approveGate(state.phase);
}

// A failed stage used to leave state.phase on 'running' with the approve button
// hidden: the run was dead and the only way out was a page reload. Put the user
// back on the gate they came from so the button retries that stage.
function resumeAfterFailure(phase) {
  openGate(phase, 'Analysen stannade. Du kan försöka igen, eller skriva feedback först.', true);
}

async function approveGate(phase) {
  const gate = GATES[phase];
  if (!gate) return;
  state.running = true; state.phase = 'running';
  showApprove(false); setInputEnabled(false);
  // The step turns green here, on approval, not when it was rendered.
  const sec = panelSection(gate.step);
  if (sec) sec.classList.add('done');
  // A note about a failed re-run has done its job once the version is approved.
  clearStepNote(gate.step);
  readFrom = null;  // approving is a move: the chat follows the run again
  addSystem(gate.approved);
  // A failed run is retried from this gate. Everything it added to the history
  // (the bridge, and the outputs of the steps that did finish) comes out
  // again, or the retry sends the next agent two kalkyls and two bridges.
  const mark = state.history.length;
  // A recalculation after QA starts again from here (recalcWithQa).
  if (phase === 'assumptions') state.calcMark = mark;
  state.history.push({role: 'user', content: gate.bridge});

  const token = runToken;
  const ok = await runStages(gate.run);
  if (token !== runToken) return;  // reset while the pipeline ran
  state.running = false;
  if (!ok) { state.history.length = mark; resumeAfterFailure(phase); return; }

  if (gate.next === 'done') {
    state.phase = 'done';
    setInputEnabled(true);
    updateProgress('rapport', true);
    addSystem('Analysen är klar. Rapporten visas till höger.');
    offerRecalc();
    return;
  }
  openGate(gate.next, GATES[gate.next].ready);
}

// Show an intermediate agent's full output in the chat (it's structured markdown,
// scannable and scrollable). Strip a leading thematic-break line the agents emit.
// The källmarkering section (Talens ursprung) is computed by the server from
// the calc model, so it is appended to what the model wrote rather than left
// for the model to copy. A report without one (loaded, or an old run) is
// returned as it is.
function withKallmarkering(md, kallmarkeringMd) {
  if (!kallmarkeringMd) return md;
  return (md || '').replace(/\s+$/, '') + '\n\n' + kallmarkeringMd + '\n';
}

function cleanOutput(md) {
  return (md || '').replace(/^[\s\n]*-{3,}[\s\n]*/, '');
}

async function finishReport(markdown) {
  const actionName = (state.profiles || []).map(p => p.name).filter(Boolean).join(' + ');
  showReport(markdown, null, {qa: state.qaVerdict, name: actionName});
  document.getElementById('reportActions').style.display = '';
  // The report is what the run was for: show it from the top, with the number
  // and the chart, and let the line draw once more now that it is in view.
  document.getElementById('resultsPanel').scrollTo({top: 0, behavior: 'smooth'});
  try { if (heroChartData && document.getElementById('heroChart').offsetParent) drawHeroChart(heroChartData, true); }
  catch (e) { /* the drawn chart stays; the report and its save matter more */ }
  // The report is now the main view — collapse the live step trail under a toggle.
  const feed = document.getElementById('analysisFeed');
  const t = document.getElementById('trailToggle');
  if (t && feed.children.length) {
    t.style.display = '';
    t.classList.remove('open');
    feed.style.display = 'none';
    document.getElementById('trailLabel').textContent = 'Visa analysunderlag (alla steg)';
  }
  if (!HAS_SUPABASE || !currentUser) return;
  const ind = document.getElementById('saveIndicator');
  if (ind) ind.textContent = 'Sparar...';
  const token = runToken;
  try {
    // The action name comes from the intake profile the user approved, and the
    // headline from the deterministic calc; the report text is what the model
    // wrote *about* them. Sending both means the saved row (and the hero drawn
    // from it) carries the numbers that were computed, not a regex hit on prose.
    const r = await authFetch('/api/reports', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        formatted_report: markdown,
        intake_summary: (state.history[0]||{}).content || '',
        action_name: actionName || undefined,
        key_metric: state.headline || undefined,
      })});
    // fetch only rejects on network failure. Without this check an HTTP 500
    // read as "Sparat" and the user walked away from an unsaved report.
    if (!r.ok) { const d = await r.jsonSafe(); throw new Error((d && d.error) || ('HTTP ' + r.status)); }
    const saved = await r.jsonSafe();
    // "Ny analys" while the save was on its way: the row is saved, and its
    // number belongs to a report that is no longer on screen. Drawn anyway,
    // it stood above the empty page of the new analysis.
    if (token !== runToken) { if (ind) ind.textContent = ''; loadSavedList(); return; }
    if (saved && saved.key_metric) {
      updateHero(saved.key_metric);
      // updateHero writes the label without the years the number covers. The
      // kalkyl knows them: a follow-up's "medel per år 2023–2030" lost its
      // years the moment the report was saved.
      const k = state.lastKalkyl;
      if (state.headline && k && k.span) setHeroLabel(k.span.mode || state.mode, k.span.window, saved.key_metric.year);
    }
    if (ind) { ind.textContent = 'Sparat'; setTimeout(()=>{ind.textContent='';}, 2500); }
    loadSavedList();
  } catch(e) {
    // "Ny analys" while the save was on its way: the report is gone from the
    // screen, so "ladda ner den" beside the new analysis points at nothing.
    // Said once in the chat instead: the report is not in the list.
    if (token !== runToken) {
      if (ind) ind.textContent = '';
      addSystem('Rapporten från den förra analysen kunde inte sparas (' + e.message + ').', true);
      return;
    }
    // Left visible: a failed save is not a transient toast, and the user is
    // about to close the tab on a report that only exists in this DOM.
    // The server's reason says who can fix it (NOT_SAVED names the list).
    if (ind) ind.textContent = 'Sparfel - rapporten är inte sparad. Ladda ner den så du har den kvar. (' + e.message + ')';
  }
}

// The report's short interpretation of the medel scenario ("Kort
// tolkning_medel: ..." in Beräknad klimatnytta) is shown under the headline
// number, which is the number it explains, and taken out of the report body
// so it is read once (2026-10-14). The min and max interpretations
// stay with their scenarios, and the download keeps the text as written.
// The models write the line in one piece; a wrapped one is joined up to the
// next blank line or field.
const INTERP_LINE = /^\s*(?:[-*•]\s*)?(?:\*\*)?\s*Kort tolkning[_ (]*medel\)?\s*(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$/i;
const FIELD_LINE = /^\s*(?:[-*•#]|\*\*|[^:\n]{1,60}:(\s|$))/;
function reportInterpretation(md) {
  const lines = (md || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    const m = INTERP_LINE.exec(lines[i]);
    if (!m) continue;
    const parts = [m[1].trim()];
    let j = i + 1;
    while (j < lines.length && lines[j].trim() && !FIELD_LINE.test(lines[j])) parts.push(lines[j++].trim());
    const text = parts.filter(Boolean).join(' ').replace(/\s*\*\*\s*$/, '');
    // The blank line on each side of the removed line becomes one.
    let end = j;
    if ((i === 0 || !lines[i - 1].trim()) && end < lines.length && !lines[end].trim()) end++;
    return {text: text, rest: lines.slice(0, i).concat(lines.slice(end)).join('\n')};
  }
  return {text: '', rest: md || ''};
}
function setHeroInterpretation(text) {
  const el = document.getElementById('heroInterp');
  if (!el) return;
  el.innerHTML = text ? renderMarkdown(text) : '';
  el.style.display = text ? '' : 'none';
}

// ---------- The report in parts ----------
// The workshop at Transition Lab Forum (2026-10-14) met the report as one
// long page and lost the result in it. The page now shows the title, the
// number and the report's own verdict, and every part of the report as a row
// that opens with one click, with a line saying what is in it
// (2026-10-15). Display only: the report text, the save and the download are
// as the model and the program wrote them, so no prompt changes.
// The parts are the report prompt's sections (agents/rapport.py, and
// agents/uppfoljning.py for a follow-up) and the three the program adds. A
// line is a part's heading only when it names one of them whole, in any of
// the forms the models write ("**X**", "## X", a bare line), so a sub-label
// inside a part ("QA-status och huvudanmärkningar") never splits it.
const REPORT_PARTS = [
  ['beskrivning', /^Kort beskrivning av åtgärden$/i],
  ['klimatnytta', /^Beräknad klimatnytta$/i],
  ['verksamhet', /^Vad åtgärden ändrar i verksamheten$/i],
  ['uppmatt', /^Uppmätt och antaget$/i],
  ['mekanism', /^Hur åtgärden minskar utsläppen$/i],
  ['antaganden', /^Nyckelantaganden och beräkningsgrund$/i],
  ['tidsprofil', /^Tidsprofil\s*[–—:-]?\s*när kommer effekten\??$/i],
  ['osakerhet', /^Osäkerhet, QA och beroenden$/i],
  ['rekommendation', /^Rekommendation och nästa steg$/i],
  ['uppfoljning', /^Följ upp med$/i],
  ['kallor', /^Källor och underlag$/i],
  ['bilaga', /^Teknisk bilaga: Beräkningssteg$/i],
  ['ursprung', /^Talens ursprung$/i],
];
// With fewer parts than this the text is not the report the prompt asks for,
// and it is shown whole, as it was before the parts.
const REPORT_PARTS_MIN = 3;
function reportPartKey(line) {
  const h = headingText(line);
  const bare = (h !== null ? h : line.trim().replace(/^\d+[).]\s*/, '').replace(/\*\*/g, '').replace(/[:\s]+$/, '')).trim();
  if (!bare || bare.length > 60) return null;
  const hit = REPORT_PARTS.find(([, re]) => re.test(bare));
  return hit ? hit[0] : null;
}
// The report's title ("## Åtgärdens namn": the first such heading before the
// first part, which is the first line unless a note stands above it),
// whatever else comes before the first part, and the parts with their
// headings as the report wrote them.
function reportSections(md) {
  const lines = (md || '').split('\n');
  let title = '';
  const pre = [], parts = [];
  for (let i = 0; i < lines.length; i++) {
    const key = reportPartKey(lines[i]);
    if (key) {
      const heading = (headingText(lines[i]) || lines[i].trim()).replace(/^\d+[).]\s*/, '').replace(/\*\*/g, '').replace(/[:\s]+$/, '');
      parts.push({key: key, title: heading, lines: []});
      continue;
    }
    const t = !parts.length && !title && lines[i].match(/^\s{0,3}#{1,2}\s+(.+?)\s*#*\s*$/);
    // The title is drawn as text, so "## **Namn**" would show its stars.
    if (t) { title = t[1].replace(/\*\*|__|`/g, '').replace(/^[*_]+|[*_]+$/g, '').trim(); continue; }
    (parts.length ? parts[parts.length - 1].lines : pre).push(lines[i]);
  }
  return {title: title, preamble: trimBlock(pre),
          parts: parts.map(p => ({key: p.key, title: p.title, body: trimBlock(p.lines)}))};
}
// A line that names what follows it ("Förslag på nästa steg:").
const LABEL_LINE = /^\s*(?:\*\*)?[A-ZÅÄÖ][^:\n]{1,80}:\s*(?:\*\*)?\s*$/;
function bareLine(line) { return line.replace(/\*\*/g, '').trim(); }
// How many points the list under a label has. Sub-points and wrapped lines
// belong to the point above them.
function bulletsUnder(body, label) {
  const lines = (body || '').split('\n');
  const at = lines.findIndex(l => label.test(bareLine(l)));
  if (at < 0) return 0;
  let n = 0;
  for (let j = at + 1; j < lines.length; j++) {
    const l = lines[j];
    if (!l.trim()) continue;
    if (/^ ?[-*•]\s+\S/.test(l)) { n++; continue; }
    if (n && /^\s{2,}\S/.test(l) && !LABEL_LINE.test(l)) continue;
    break;
  }
  return n;
}
// The text under a label ("Samlad rekommendation:"), up to the next label,
// list or heading, and the body without it. Null when it is not there.
function liftLabelled(body, label) {
  const lines = (body || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    const m = bareLine(lines[i]).match(label);
    if (!m) continue;
    const paras = [[]];
    if (m[1] && m[1].trim()) paras[0].push(m[1].trim());
    let j = i + 1;
    for (; j < lines.length; j++) {
      const l = lines[j];
      if (!l.trim()) { if (paras[paras.length - 1].length) paras.push([]); continue; }
      if (LABEL_LINE.test(l) || headingText(l) !== null || /^\s*([-*•]|\d+[.)])\s|^\s*\|/.test(l)) break;
      paras[paras.length - 1].push(l.trim());
    }
    const text = paras.filter(p => p.length).map(p => p.join(' ')).join('\n\n');
    if (!text) return null;
    return {text: text, rest: trimBlock(lines.slice(0, i).concat([''], lines.slice(j)))};
  }
  return null;
}
// "hög", "medel", "låg till medel"; anything else is not a level.
const LEVEL = /^(låg|medel|medelhög|hög)(?:\s*(?:till|–|-)\s*(låg|medel|medelhög|hög))?$/i;
function levelIn(text) {
  const v = (text || '').replace(/\*\*/g, '').replace(/\(.*$/, '').replace(/[[\]'"`.]/g, '').trim();
  return LEVEL.test(v) ? v.toLowerCase() : null;
}
// A level written on the label's line ("Risk för dubbelräkning: medel") or
// as "Bedömning: medel" on one of the lines right under it.
function levelUnder(body, label) {
  const lines = (body || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    const m = bareLine(lines[i]).match(label);
    if (!m) continue;
    if (m[1] && m[1].trim()) return levelIn(m[1]);
    for (let j = i + 1, seen = 0; j < lines.length && seen < 3; j++) {
      if (!lines[j].trim()) continue;
      seen++;
      const b = bareLine(lines[j]).match(/^Bedömning\s*:\s*(.*)$/i);
      if (b) return levelIn(b[1]);
    }
  }
  return null;
}
// "Scenario_min" ... "ΔE_2030_total (Netto): 68 ton": each scenario's net
// number per year, as written.
function scenarioNet(body) {
  const out = {};
  let at = null;
  for (const line of (body || '').split('\n')) {
    const bare = bareLine(line);
    const s = bare.match(/^Scenario[_ ](min|medel|max)\b/i);
    if (s) { at = s[1].toLowerCase(); out[at] = out[at] || {}; continue; }
    if (LABEL_LINE.test(line) || headingText(line) !== null) { at = null; continue; }
    const v = at && bare.match(/^ΔE_(\d{4})_total\s*\(Netto\)\s*:\s*([-−–]?\s*\d[\d\s]*(?:[.,]\d+)?)\s*ton/i);
    if (v) out[at][v[1]] = v[2].replace(/\s+/g, ' ').trim();
  }
  return out;
}
function firstSentence(text, max) {
  const flat = (text || '').replace(/\s+/g, ' ').trim();
  const m = flat.match(/^.+?[.!?](?=\s+[A-ZÅÄÖ]|\s*$)/);
  const s = (m ? m[0] : flat).trim();
  return s && s.length <= max ? s : '';
}
function countOf(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
// The line under a part's title. Made by the program from the part's own
// content, never a cut-off piece of it: a number it can read, or a fixed line
// saying what the part holds.
function partTeaser(part, lifted) {
  const b = part.body;
  switch (part.key) {
    case 'beskrivning': return {text: 'Vad åtgärden går ut på och vem den riktar sig till.'};
    case 'klimatnytta': {
      const s = scenarioNet(b);
      const years = Object.keys(s.min || {}).filter(y => (s.medel || {})[y] && (s.max || {})[y]).sort();
      const target = (b.split('\n').map(bareLine).find(l => /^Målår\s*:\s*\d{4}\b/i.test(l)) || '').match(/\d{4}/);
      const y = target && years.includes(target[0]) ? target[0] : years[years.length - 1];
      if (y) return {text: 'År ' + y + ': försiktigt ' + s.min[y] + ', mest sannolikt ' + s.medel[y] +
                          ' och full potential ' + s.max[y] + ' ton CO₂e/år.'};
      return {text: 'Resultatet i tre scenarier: försiktigt, mest sannolikt och full potential.'};
    }
    case 'uppmatt': return {text: 'Vad som är uppmätt och vad som är antaget.'};
    case 'verksamhet': {
      const n = (b.match(/^- /gm) || []).length;
      return {text: 'Samma förändring som tonnen, i km, liter, m² och andra enheter som går att följa' +
                    (n ? ', för ' + countOf(n, 'utsläppskälla', 'utsläppskällor') : '') + '.'};
    }
    case 'mekanism': {
      const n = bulletsUnder(b, /^Huvuddrivare\s*:/i);
      return {text: n ? countOf(n, 'huvuddrivare', 'huvuddrivare') + ' och hur de ger effekt.' : 'Vilka drivare som ger effekten, och hur.'};
    }
    case 'antaganden': {
      const n = bulletsUnder(b, /^Nyckelantaganden(\s*\(översikt\))?\s*:/i);
      return {text: n ? countOf(n, 'nyckelantagande', 'nyckelantaganden') + ' och hur beräkningen är gjord.'
                      : 'Vad resultatet bygger på och hur beräkningen är gjord.'};
    }
    case 'tidsprofil': {
      // Only bare years: "2029 för kravet och 2030 för ..." does not fit in a line.
      const year = (re) => { const l = b.split('\n').map(bareLine).find(x => re.test(x)); const m = l && l.match(/:\s*(\d{4})\.?$/); return m ? m[1] : null; };
      const from = year(/^Startar\s*:/i), full = year(/^Full[_ ]effekt[_ ]uppnås\s*:/i);
      if (from && full) return {text: from === full ? 'Full effekt från ' + full + '.' : 'Effekten börjar ' + from + ' och är full ' + full + '.'};
      return {text: 'När effekten kommer och hur den byggs upp.'};
    }
    case 'osakerhet': {
      const n = bulletsUnder(b, /^(Viktigaste )?QA-anmärkningar\s*:/i);
      return {text: 'Vad resultatet är mest känsligt för, ' + (n ? countOf(n, 'anmärkning', 'anmärkningar') + ' från granskningen' : 'granskningen') +
                    ' och beroenden till andra beslut.'};
    }
    case 'rekommendation': {
      const n = bulletsUnder(b, /^Förslag på nästa steg\s*:/i);
      const more = bulletsUnder(b, /^Förslag på information/i) > 0;
      if (n) return {text: countOf(n, 'förslag', 'förslag') + ' på nästa steg' + (more ? ', och underlag som skulle göra analysen säkrare.' : '.')};
      return {text: lifted ? 'Förslag på nästa steg.' : 'Rekommendationen och förslag på nästa steg.'};
    }
    case 'uppfoljning': {
      const n = bulletsUnder(b, /^Indikatorer\s*:/i);
      return {text: n ? countOf(n, 'indikator', 'indikatorer') + ' som visar om åtgärden ger effekt.'
                      : 'Vad som ska mätas för att se om åtgärden ger effekt.'};
    }
    case 'kallor': {
      const n = bulletsUnder(b, /^Externa studier( och rapporter)?\s*:/i);
      return {text: n ? countOf(n, 'extern studie', 'externa studier') + ' och underlagen analysen bygger på.' : 'Underlagen analysen bygger på.'};
    }
    case 'bilaga': return {text: 'Kalkylmotorns uträkning steg för steg, för den som vill kontrollera talen.'};
    case 'ursprung': {
      const total = b.match(/bygger på (\d+) inmatade tal/), check = b.match(/(\d+) behöver kontrolleras/);
      if (total) return {text: 'Varifrån vart och ett av de ' + total[1] + ' talen i kalkylen kommer.' +
                               (check ? ' ' + check[1] + ' behöver kontrolleras.' : ''), warn: !!check};
      // The section that says the check could not be made (kallmarkering.SAKNAS, KONTROLL_FEL).
      const said = firstSentence(b, 140);
      return said ? {text: said, warn: true} : {text: 'Varifrån talen i kalkylen kommer.'};
    }
  }
  return {text: ''};
}
// Everything the page draws, read from the report text: the title, the
// report's own recommendation with three levels under it, and the parts.
// opts.qa is the QA step's own verdict in a live run (the number's warning
// reads the same one); a saved report has only its text. opts.hero: there is
// a number above, so the result part need not stand open. Null: show the
// text whole.
function reportView(md, opts) {
  opts = opts || {};
  const r = reportSections(md);
  if (r.parts.length < REPORT_PARTS_MIN) return null;
  const find = (key) => r.parts.find(p => p.key === key);
  let recommendation = '', lifted = false;
  const rec = find('rekommendation');
  if (rec) {
    const got = liftLabelled(rec.body, /^Samlad rekommendation(?:\s*:\s*(.*)|\s*)$/i);
    // Read once: it is the verdict now, and the part is the next steps.
    if (got) { recommendation = got.text; rec.body = got.rest; rec.title = 'Nästa steg'; lifted = true; }
  }
  const osak = (find('osakerhet') || {body: ''}).body;
  const status = [];
  const unc = levelUnder(osak, /^Övergripande bedömning av osäkerhet\s*:\s*(.*)$/i) || levelUnder(osak, /^Osäkerhetsnivå\s*:\s*(.*)$/i);
  if (unc) status.push({label: 'Osäkerhet', value: unc});
  const qa = (opts.qa && opts.qa.status) || ((qaVerdict(md) || {}).status);
  if (qa) status.push({label: 'Kvalitetsgranskning', value: qa === 'ok' ? 'godkänd' : 'varning', warn: qa !== 'ok'});
  const dub = levelUnder(osak, /^Risk för dubbelräkning(?:\s*:\s*(.*)|\s*)$/i);
  if (dub) status.push({label: 'Risk för dubbelräkning', value: dub});
  status.forEach(s => { s.value = s.value.charAt(0).toUpperCase() + s.value.slice(1); s.warn = !!s.warn; });
  const seen = {};
  const parts = r.parts.filter(p => p.body).map(p => {
    seen[p.key] = (seen[p.key] || 0) + 1;
    return {id: p.key + (seen[p.key] > 1 ? '-' + seen[p.key] : ''), key: p.key, title: p.title, body: p.body,
            open: !opts.hero && p.key === 'klimatnytta'};
  });
  // The program appends Talens ursprung last; a line by that name the model
  // wrote higher up is only text.
  const urs = parts.filter(p => p.key === 'ursprung').pop();
  parts.forEach(p => {
    const t = p.key === 'ursprung' && p !== urs ? {text: ''} : partTeaser(p, lifted && p.key === 'rekommendation');
    p.teaser = t.text;
    p.warn = !!t.warn;
  });
  const checkMatch = urs && urs.body.match(/(\d+) behöver kontrolleras/);
  const check = checkMatch ? Number(checkMatch[1])
    : (urs ? bulletsUnder(urs.body, /^#{0,6}\s*Kontrollera först$/i) : 0);
  const verdict = (recommendation || status.length || check)
    ? {text: recommendation, status: status, check: check, checkPart: urs ? urs.id : null} : null;
  return {title: r.title, preamble: r.preamble, verdict: verdict, parts: parts};
}

// ---------- The report in parts, drawn ----------
// The parts the person opened or closed, by id, so a recalculation that draws
// the report again leaves them as they were. Cleared with the analysis.
const reportOpen = new Map();
function wrapTables(frag) {
  for (const t of Array.from(frag.querySelectorAll('table'))) {
    const box = document.createElement('div');
    box.className = 'table-scroll';
    t.parentNode.insertBefore(box, t);
    box.appendChild(t);
  }
  return frag;
}
function reportPartEls() { return Array.from(document.querySelectorAll('#reportContent details.part')); }
function syncPartsToggle() {
  const btn = document.getElementById('partsToggle');
  if (!btn) return;
  const all = reportPartEls().every(d => d.open);
  btn.textContent = all ? 'Fäll ihop alla' : 'Visa alla delar';
  btn.setAttribute('aria-expanded', all ? 'true' : 'false');
}
function setAllParts(open) {
  reportPartEls().forEach(d => { d.open = open; reportOpen.set(d.dataset.part, open); });
  syncPartsToggle();
}
function openPart(id) {
  const d = reportPartEls().find(x => x.dataset.part === id);
  if (!d) return;
  d.open = true;
  reportOpen.set(id, true);
  syncPartsToggle();
  d.scrollIntoView({behavior: 'smooth', block: 'start'});
  d.querySelector('summary').focus({preventScroll: true});
}
// Every text the model wrote goes through sanitizedFragment, the one place
// model text is sanitised; titles and the lines under them are text nodes.
function renderReportView(rc, view) {
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  rc.textContent = '';
  rc.classList.add('structured');
  if (view.preamble) {
    const pre = el('div', 'report-pre');
    pre.appendChild(wrapTables(sanitizedFragment(view.preamble)));
    rc.appendChild(pre);
  }
  if (view.verdict) {
    const v = el('section', 'report-verdict');
    v.appendChild(el('div', 'section-eyebrow', 'Bedömning'));
    if (view.verdict.text) {
      const t = el('div', 'verdict-text');
      t.appendChild(sanitizedFragment(view.verdict.text));
      v.appendChild(t);
    }
    const checkPart = view.verdict.check ? view.verdict.checkPart : null;
    if (view.verdict.status.length || checkPart) {
      const row = el('div', 'verdict-status');
      view.verdict.status.forEach(s => {
        const dl = el('dl', s.warn ? 'warn' : '');
        dl.appendChild(el('dt', '', s.label));
        dl.appendChild(el('dd', '', s.value));
        row.appendChild(dl);
      });
      if (checkPart) {
        const b = el('button', 'verdict-check', 'Kontrollera först: ' + view.verdict.check + ' tal');
        b.type = 'button';
        b.addEventListener('click', () => openPart(checkPart));
        row.appendChild(b);
      }
      v.appendChild(row);
    }
    rc.appendChild(v);
  }
  const head = el('div', 'parts-head');
  head.appendChild(el('div', 'section-eyebrow', 'Rapportens delar'));
  const toggle = el('button', 'parts-toggle');
  toggle.type = 'button';
  toggle.id = 'partsToggle';
  toggle.addEventListener('click', () => setAllParts(toggle.getAttribute('aria-expanded') !== 'true'));
  head.appendChild(toggle);
  rc.appendChild(head);
  const sheet = el('div', 'report-parts');
  view.parts.forEach(p => {
    const d = el('details', 'part');
    d.dataset.part = p.id;
    const s = el('summary');
    const caret = el('span', 'part-caret');
    caret.setAttribute('aria-hidden', 'true');
    s.appendChild(caret);
    s.appendChild(el('span', 'part-title', plainTerms(p.title)));
    if (p.teaser) s.appendChild(el('span', 'part-teaser' + (p.warn ? ' warn' : ''), plainTerms(readableNumbers(p.teaser))));
    d.appendChild(s);
    const body = el('div', 'part-body');
    body.appendChild(wrapTables(sanitizedFragment(p.body)));
    d.appendChild(body);
    d.open = reportOpen.has(p.id) ? reportOpen.get(p.id) : p.open;
    d.addEventListener('toggle', () => { reportOpen.set(p.id, d.open); syncPartsToggle(); });
    sheet.appendChild(d);
  });
  rc.appendChild(sheet);
  syncPartsToggle();
}

// opts.qa: the QA step's verdict in a live run. opts.name: what to call the
// analysis when the report has no title line (the profile names, or the
// saved row's).
function showReport(markdown, keyMetric, opts) {
  opts = opts || {};
  showAnalysisCard();
  if (keyMetric) updateHero(keyMetric);
  // The interpretation moves up only when there is a number for it to sit
  // under; without one (the calc fell back to the model, nothing saved) it
  // stays where the model wrote it.
  const hero = document.getElementById('heroCard').style.display !== 'none';
  const interp = hero ? reportInterpretation(markdown) : {text: '', rest: markdown || ''};
  setHeroInterpretation(interp.text);
  const rc = document.getElementById('reportContent');
  rc.style.display = '';
  const title = document.getElementById('reportTitle');
  // A report the parts cannot be read from is shown whole, as it always was.
  let view = null;
  try { view = reportView(interp.rest, {qa: opts.qa, hero: hero}); } catch (e) { view = null; }
  if (view) {
    try {
      const name = plainTerms(view.title || opts.name || '');
      title.textContent = name;
      title.style.display = name ? '' : 'none';
      renderReportView(rc, view);
      return;
    } catch (e) { /* drawn whole below */ }
  }
  title.textContent = '';
  title.style.display = 'none';
  rc.classList.remove('structured');
  rc.innerHTML = renderMarkdown(interp.rest);
}

// A saved row's number in words. Rows from 2026-10-13 on carry the target
// year their number is for; rows without one hold an average per year.
function keyMetricText(net, km) {
  return km && km.year ? fmt(net) + ' ton CO₂e år ' + km.year : fmt(net) + ' ton CO₂e/år i snitt';
}
function updateHero(km) {
  if (!km || (km.net == null && km.cons == null && km.terr == null)) return;
  const net = km.net != null ? km.net : (km.cons != null ? km.cons : km.terr);
  // The label follows what this number is (a year or an average). Callers
  // that know the window set it again after this.
  setHeroLabel(state.mode, null, km.year);
  document.getElementById('heroCard').style.display = '';
  document.getElementById('heroValue').innerHTML = fmt(net) + ' <span>ton CO₂e/år</span>';
  const parts = [];
  if (km.terr != null) parts.push('Territoriell <b>' + fmt(km.terr) + '</b>');
  if (km.cons != null) parts.push('Konsumtion <b>' + fmt(km.cons) + '</b>');
  if (km.net != null) parts.push('Netto <b>' + fmt(km.net) + '</b>');
  // A headline read out of the report text (the calc fell back to the
  // language model) is not the program's result and must not look like it.
  if (km.source === 'rapport') parts.push('<span>ur rapportens text, inte programmets kalkyl</span>');
  document.getElementById('heroSub').innerHTML = parts.join('');
}

// The downloaded report is what travels onwards into a board paper, so it
// carries its own provenance rather than relying on whoever forwards it.
const REPORT_ATTRIBUTION = [
  '',
  '---',
  '',
  'Framtaget med CAIA, ett klimatberäkningsverktyg för kommunala klimatåtgärder.',
  ORIGIN,
  '',
  'Siffrorna är estimat. Beräkningen är deterministisk, men antagandena bygger på',
  'ett parameterbibliotek där en del värden är lokalt verifierade för ' + KOMMUN.ort + ' och',
  'en del är nationella schabloner.',
  '',
].join('\n');

// The browser's own print dialog: "Spara som PDF" there gives a file with the
// number, the chart and the report, the way it looks on screen. The page
// title becomes the file name.
function printReport() {
  if (!state.reportMarkdown) return;
  document.getElementById('printAttribution').innerHTML = renderMarkdown(REPORT_ATTRIBUTION);
  const title = document.title;
  const name = (state.profiles || []).map(p => p.name).filter(Boolean).join(' + ');
  document.title = 'CAIA ' + (name ? name + ' ' : '') + new Date().toISOString().slice(0, 10);
  window.addEventListener('afterprint', () => { document.title = title; }, {once: true});
  window.print();
}

function downloadReport() {
  if (!state.reportMarkdown) return;
  const blob = new Blob([plainTerms(state.reportMarkdown) + REPORT_ATTRIBUTION], {type:'text/markdown'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'caia-rapport-' + new Date().toISOString().slice(0,10) + '.md';
  a.click();
}

const PROV = {
  lokal:    ['Lokalt verifierad', 'prov-lokal'],
  datafil:  ['Ur lokal datafil', 'prov-datafil'],
  schablon: ['Nationell schablon', 'prov-schablon'],
};

async function openParams() {
  const modal = document.getElementById('paramsModal');
  modal.style.display = 'flex';
  const body = document.getElementById('paramsBody');
  body.innerHTML = '<div style="padding:40px;text-align:center;color:var(--kk-gray-400)">Laddar parametrar...</div>';
  try {
    const r = await authFetch('/api/parameters');
    const d = await r.jsonSafe();
    if (!r.ok) { body.innerHTML = '<div style="padding:40px;color:var(--kk-red)">Fel: ' + escapeHtml(d.error || 'okänt') + '</div>'; return; }
    renderParams(d);
  } catch(e) { body.innerHTML = '<div style="padding:40px;color:var(--kk-red)">Fel: ' + escapeHtml(e.message) + '</div>'; }
}

function closeParams() { document.getElementById('paramsModal').style.display = 'none'; }
function openAbout() { document.getElementById('aboutModal').style.display = 'flex'; }
function closeAbout() { document.getElementById('aboutModal').style.display = 'none'; }
// Escape closes whatever lies on top: a modal, or the saved-reports menu.
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const open = id => { const el = document.getElementById(id); return el && el.style.display && el.style.display !== 'none'; };
  if (open('paramsModal')) closeParams();
  else if (open('portfolioModal')) closePortfolio();
  else if (open('aboutModal')) closeAbout();
  else if (open('savedMenu')) document.getElementById('savedMenu').style.display = 'none';
});

function renderParams(d) {
  const c = d.counts || {};
  let html = '<div class="param-summary">Av <b>' + d.total + '</b> faktorer: ' +
    '<span class="prov-lokal">' + (c.lokal||0) + ' lokalt verifierade</span> &#xB7; ' +
    '<span class="prov-datafil">' + (c.datafil||0) + ' ur lokal datafil</span> &#xB7; ' +
    '<span class="prov-schablon">' + (c.schablon||0) + ' nationella schabloner</span> ' +
    '&#x2014; schablonerna är inte lokalt verifierade och bör kontrolleras mot ' + escapeHtml(KOMMUN.ort) + '-data innan beslut.</div>';
  (d.sections || []).forEach(s => {
    html += '<div class="param-sec">' + escapeHtml(s.title) + '</div>';
    html += '<table class="param-table"><thead><tr><th>Parameter</th><th>Värde som används</th><th>Enhet</th><th>Källa</th></tr></thead><tbody>';
    s.rows.forEach(r => {
      const b = PROV[r.provenance] || ['', ''];
      // The description is the name a reader recognises; the Parameter_ID sits
      // under it for whoever looks one up from a report. No description: the ID alone.
      const name = r.beskrivning
        ? '<div class="param-name">' + escapeHtml(r.beskrivning) + '</div><div class="param-id">' + escapeHtml(r.id) + '</div>'
        : '<div class="param-name">' + escapeHtml(r.id) + '</div>';
      html += '<tr><td>' + name + '</td>' +
        '<td><div class="param-val">' + escapeHtml(r.value_display || r.value_used || '–') + '</div>' +
        (r.value_note ? '<div class="param-note">' + escapeHtml(r.value_note) + '</div>' : '') + '</td>' +
        '<td>' + escapeHtml(r.enhet) + '</td>' +
        '<td><span class="prov-badge ' + b[1] + '">' + b[0] + '</span></td></tr>';
    });
    html += '</tbody></table>';
  });
  document.getElementById('paramsBody').innerHTML = html;
}

/* ---------- portfolio (caia.calc.portfolj) ---------- */
// Step one lists the saved analyses; step two shows each one's parts with a
// pot to choose, and "is a target for". Nothing is preselected except the pot
// the analysis itself named, so every choice sent is one the user made or saw.
let portfolio = { rows: [], atgarder: [], potter: [] };

async function openPortfolio() {
  document.getElementById('portfolioModal').style.display = 'flex';
  const body = document.getElementById('portfolioBody');
  body.innerHTML = '<div class="saved-empty">Hämtar sparade analyser...</div>';
  try {
    const r = await authFetch('/api/reports');
    const rows = await r.jsonSafe();
    if (!r.ok) { body.innerHTML = '<div class="pf-msg">Kunde inte hämta sparade analyser: ' + escapeHtml(rows.error || ('fel ' + r.status)) + '</div>'; return; }
    portfolio.rows = Array.isArray(rows) ? rows : [];
    renderPortfolioPick();
  } catch(e) { body.innerHTML = '<div class="pf-msg">Kunde inte hämta sparade analyser: ' + escapeHtml(e.message) + '</div>'; }
}
function closePortfolio() { document.getElementById('portfolioModal').style.display = 'none'; }

function renderPortfolioPick(message) {
  const body = document.getElementById('portfolioBody');
  if (portfolio.rows.length < 2) {
    body.innerHTML = '<p>En portfölj behöver minst två sparade analyser. Gör och spara en analys till, så kan du räkna dem tillsammans här.</p>';
    return;
  }
  body.innerHTML = '<div class="param-sec">Välj analyser</div>' +
    '<p>Ta med en analys av varje åtgärd. Två körningar av samma åtgärd kan ge mycket olika tal, så portföljen tar bara en.</p>' +
    '<div id="pfPickList"></div>' +
    '<div class="pf-buttons"><button class="btn-save" id="pfNext">Fortsätt till utsläppspotterna</button></div>' +
    '<div class="pf-msg" id="pfMsg"' + (message ? '' : ' style="display:none"') + '></div>';
  if (message) document.getElementById('pfMsg').textContent = message;
  const list = document.getElementById('pfPickList');
  portfolio.rows.forEach(row => {
    const label = document.createElement('label');
    label.className = 'pf-pick';
    const box = document.createElement('input');
    box.type = 'checkbox'; box.value = row.id;
    box.checked = (portfolio.picked || []).indexOf(row.id) >= 0;
    const text = document.createElement('div');
    const net = row.key_metric && (row.key_metric.net != null ? row.key_metric.net : null);
    text.innerHTML = '<div>' + escapeHtml(row.action_name || 'Namnlös') + '</div><div class="si-meta">' +
      escapeHtml((row.created_at || '').slice(0, 10)) + (net != null ? ', ' + escapeHtml(keyMetricText(net, row.key_metric)) : '') + '</div>';
    label.appendChild(box); label.appendChild(text);
    list.appendChild(label);
  });
  document.getElementById('pfNext').addEventListener('click', portfolioParts);
}

async function portfolioParts() {
  const ids = Array.from(document.querySelectorAll('#pfPickList input:checked')).map(b => b.value);
  portfolio.picked = ids;
  if (ids.length < 2) { renderPortfolioPick('Välj minst två analyser.'); return; }
  document.getElementById('pfNext').disabled = true;
  // postJson rejects on a dropped connection. Uncaught, the button stayed
  // disabled and nothing was said.
  let r;
  try { r = await postJson('/api/portfolj/atgarder', {ids}); }
  catch (e) { renderPortfolioPick('Kunde inte nå servern: ' + e.message + '. Försök igen.'); return; }
  if (!r.ok) { renderPortfolioPick(r.data.error || 'Något gick fel.'); return; }
  portfolio.atgarder = r.data.atgarder || [];
  portfolio.potter = r.data.potter || [];
  renderPortfolioParts();
}

function renderPortfolioParts() {
  const body = document.getElementById('portfolioBody');
  const usable = portfolio.atgarder.filter(a => !a.fel);
  let html = '<div class="param-sec">Markera vad varje del verkar på</div>' +
    '<p>En utsläppspott är en avgränsad del av kommunens utsläpp med ett känt utsläpp per år, till exempel kommunens husbyggnad. ' +
    'Delar som verkar på samma pott räknas tillsammans. En del utan pott räknas för sig, som i analysen.</p>';
  if (!portfolio.potter.length) html += '<p class="pf-skip">Kommunen har inga utsläppspotter registrerade, så portföljen kan bara lägga ihop analyserna.</p>';
  html += '<div id="pfParts"></div>' +
    '<div class="pf-buttons"><button class="btn-approve" id="pfRun">Räkna portföljen</button>' +
    '<button class="btn-pill" id="pfBack">Välj andra analyser</button></div>' +
    '<div class="pf-msg" id="pfMsg" style="display:none"></div><div class="pf-result" id="pfResult"></div>';
  body.innerHTML = html;
  const parts = document.getElementById('pfParts');
  portfolio.atgarder.forEach(a => {
    const head = document.createElement('div');
    head.className = 'pf-action';
    head.innerHTML = escapeHtml(a.namn) + ' <span class="si-meta">' + escapeHtml(a.skapad || '') + '</span>';
    parts.appendChild(head);
    if (a.fel) {
      const p = document.createElement('div'); p.className = 'pf-skip';
      p.textContent = 'Den här analysen ' + a.fel; parts.appendChild(p); return;
    }
    const table = document.createElement('table');
    table.className = 'param-table pf-table';
    table.innerHTML = '<thead><tr><th>Del av åtgärden</th><th>Utsläppspott</th></tr></thead>';
    const tb = document.createElement('tbody');
    a.delar.forEach((d, i) => {
      const tr = document.createElement('tr');
      const td1 = document.createElement('td'); td1.textContent = d.namn;
      const td2 = document.createElement('td');
      const sel = document.createElement('select');
      sel.dataset.atgard = a.id; sel.dataset.del = String(i);
      sel.setAttribute('aria-label', 'Utsläppspott för ' + d.namn);
      sel.appendChild(new Option('Ingen utsläppspott', ''));
      portfolio.potter.forEach(p => sel.appendChild(new Option(p.namn + ' (' + fmt(p.baslinje) + ' ton per år ' + p.ar + ')', p.id)));
      sel.value = d.pott && portfolio.potter.some(p => p.id === d.pott) ? d.pott : '';
      td2.appendChild(sel);
      tr.appendChild(td1); tr.appendChild(td2); tb.appendChild(tr);
    });
    table.appendChild(tb);
    parts.appendChild(table);
    const others = usable.filter(o => o.id !== a.id);
    if (others.length) {
      const t = document.createElement('div');
      t.className = 'pf-targets';
      t.innerHTML = '<div>Är den här åtgärden ett mål som någon av de andra är ett sätt att nå? Kryssa i dem. De räknas då inom målet, inte ovanpå det.</div>';
      others.forEach(o => {
        const label = document.createElement('label');
        const box = document.createElement('input');
        box.type = 'checkbox'; box.dataset.mal = a.id; box.value = o.id;
        label.appendChild(box); label.appendChild(document.createTextNode(' ' + o.namn));
        t.appendChild(label);
      });
      parts.appendChild(t);
    }
  });
  document.getElementById('pfRun').addEventListener('click', runPortfolio);
  document.getElementById('pfBack').addEventListener('click', () => renderPortfolioPick());
}

async function runPortfolio() {
  const msg = document.getElementById('pfMsg');
  const out = document.getElementById('pfResult');
  msg.style.display = 'none'; out.innerHTML = '';
  const usable = portfolio.atgarder.filter(a => !a.fel);
  if (usable.length < 2) { msg.textContent = 'Minst två av analyserna måste gå att använda.'; msg.style.display = ''; return; }
  const potter = {}, mal_for = {};
  usable.forEach(a => {
    potter[a.id] = a.delar.map((d, i) => {
      const v = document.querySelector('select[data-atgard="' + a.id + '"][data-del="' + i + '"]').value;
      return v || null;
    });
    mal_for[a.id] = Array.from(document.querySelectorAll('input[data-mal="' + a.id + '"]:checked')).map(b => b.value);
  });
  const btn = document.getElementById('pfRun');
  btn.disabled = true;
  try {
    const r = await postJson('/api/portfolj', {ids: usable.map(a => a.id), potter, mal_for});
    if (!r.ok) { msg.textContent = r.data.error || 'Något gick fel.'; msg.style.display = ''; return; }
    const box = document.createElement('div');
    box.className = 'report-container';
    box.appendChild(sanitizedFragment(r.data.markdown));
    out.appendChild(box);
    out.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (e) {
    msg.textContent = 'Kunde inte nå servern: ' + e.message + '. Försök igen.'; msg.style.display = '';
  } finally { btn.disabled = false; }
}

// A running step says how long it has been at it. Evidens takes a few
// minutes, and a spinner alone for that long reads as hung.
setInterval(() => {
  document.querySelectorAll('.step-sec.running[data-started]').forEach(sec => {
    const t = sec.querySelector('.step-sec-time');
    if (!t) return;
    const secs = Math.max(0, Math.floor((Date.now() - Number(sec.dataset.started)) / 1000));
    t.textContent = Math.floor(secs / 60) + ':' + String(secs % 60).padStart(2, '0');
  });
}, 1000);

// An analysis lives only in this page until the report is saved: a reload, a
// back-swipe or "Ny analys" used to throw away up to nine minutes and four
// approvals without a word.
function analysisInProgress() {
  return state.history.length > 0 && state.phase !== 'done';
}
window.addEventListener('beforeunload', (e) => {
  if (!analysisInProgress()) return;
  e.preventDefault();
  e.returnValue = '';  // older Chrome and Safari need a value to show the dialog
});

function confirmDiscard() {
  return !analysisInProgress() || window.confirm('Börja om? Analysen du håller på med försvinner.');
}

function startNewAnalysis() {
  if (confirmDiscard()) resetAll();
}

function resetAll() {
  runToken++;
  state = { phase:'idle', history:[], reportMarkdown:null, running:false, profiles:null, headline:null, kallmarkeringMd:null, mode: state.mode,
            calcMark: null, lastKalkyl: null, qaVerdict: null };
  document.getElementById('btnApprove').textContent = GATES.profile.button;
  document.getElementById('chatMessages').innerHTML = '<div class="msg-system"></div>';
  document.querySelector('#chatMessages .msg-system').textContent = MODES[state.mode].prompt;
  lockMode(false);
  setHeroLabel(state.mode, null);
  document.getElementById('resultsEmpty').style.display = '';
  document.getElementById('analysisCard').style.display = 'none';
  document.getElementById('analysisFeed').innerHTML = '';
  document.getElementById('analysisFeed').style.display = '';
  document.getElementById('reportContent').style.display = 'none';
  document.getElementById('reportContent').innerHTML = '';
  document.getElementById('reportContent').classList.remove('structured');
  document.getElementById('reportTitle').style.display = 'none';
  document.getElementById('reportTitle').textContent = '';
  reportOpen.clear();
  document.getElementById('reportActions').style.display = 'none';
  document.getElementById('trailToggle').style.display = 'none';
  document.getElementById('heroCard').style.display = 'none';
  document.getElementById('heroScenario').style.display = 'none';
  heroChartData = null;
  document.getElementById('heroWarn').style.display = 'none';
  setHeroInterpretation('');
  showApprove(false); setInputEnabled(true);
  document.querySelectorAll('.progress-step').forEach(el => el.classList.remove('active','done'));
  document.querySelector('[data-step="intake"]').classList.add('active');
}

// On paper (print, and "Spara som PDF" in the same dialog) the whole report is
// read: every part is opened for the print and closed again after it.
let partsOpenedForPrint = [];
// Added to, not replaced: a second beforeprint before the afterprint (the
// browser's own after the page's) would otherwise forget which to close.
window.addEventListener('beforeprint', () => {
  const closed = reportPartEls().filter(d => !d.open);
  closed.forEach(d => { d.open = true; });
  partsOpenedForPrint = partsOpenedForPrint.concat(closed);
});
window.addEventListener('afterprint', () => {
  partsOpenedForPrint.forEach(d => { d.open = false; });
  partsOpenedForPrint = [];
});

document.getElementById('chatInput').addEventListener('input', function() {
  this.style.height = 'auto'; this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
</script>
</body>
</html>"""


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not CAIA_PASSWORD:
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        ip = _client_ip()
        if _login_blocked(ip):
            app.logger.warning("Login blocked after repeated wrong passwords, ip %s",
                               _hashed_ip())
            error = 'F\u00f6r m\u00e5nga felaktiga f\u00f6rs\u00f6k. V\u00e4nta tio minuter och f\u00f6rs\u00f6k igen.'
            return _render(LOGIN_TEMPLATE, error=error,
                                          **_page_context()), 429
        given = request.form.get('password') or ''
        if hmac.compare_digest(given.encode(), CAIA_PASSWORD.encode()):
            session.clear()
            session.permanent = True
            session['pw'] = _password_tag()
            return redirect(url_for('index'))
        _login_failed(ip)
        app.logger.warning("Wrong password, ip %s", _hashed_ip())
        error = 'Fel l\u00f6senord'
    return _render(LOGIN_TEMPLATE, error=error, **_page_context())


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login') if CAIA_PASSWORD else url_for('index'))


@app.route('/')
def index():
    # Supabase mode: serve the page; the frontend login overlay gates access and
    # attaches the JWT to /api calls (which are individually @require_auth).
    if SUPABASE_URL:
        return _render(
            HTML_TEMPLATE,
            has_supabase=True,
            supabase_url=SUPABASE_URL,
            supabase_anon_key=SUPABASE_ANON_KEY,
            **_page_context(),
        )
    # Password mode (or fully open local dev).
    if CAIA_PASSWORD and not _password_session_ok():
        return redirect(url_for('login'))
    return _render(
        HTML_TEMPLATE, has_supabase=False, supabase_url='', supabase_anon_key='',
        password_mode=bool(CAIA_PASSWORD), **_page_context(),
    )


@app.route('/api/intake', methods=['POST'])
@require_auth
@rate_limited
def api_intake():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    if not history:
        raise RequestError('Ingen historik')
    try:
        return jsonify(run_intake(history, mode=mode))
    except Exception as e:
        return _step_error(e)


def _feedback(data) -> bool:
    """Whether this run answers a comment written at the step's gate."""
    return isinstance(data, dict) and data.get('feedback') is True


def _gate_answer(output: str, feedback: bool, history: list[dict]) -> dict:
    """A step's response. On a gate re-run the reply to the comment goes to
    the chat and only the version to the panel and history (caia.feedback)."""
    if not feedback:
        return {'output': output}
    reply, version = split_reply(output, previous_version(history))
    return {'output': version, 'reply': reply}


@app.route('/api/emap', methods=['POST'])
@require_auth
@rate_limited
def api_emap():
    data = request.get_json(silent=True)
    history, mode, feedback = _history(data), _mode(data), _feedback(data)
    try:
        output = run_emap(frame_history(history) if feedback else history, mode=mode)
        return jsonify(_gate_answer(output, feedback, history))
    except Exception as e:
        return _step_error(e)


@app.route('/api/baslinje', methods=['POST'])
@require_auth
@rate_limited
def api_baslinje():
    data = request.get_json(silent=True)
    history, mode, feedback = _history(data), _mode(data), _feedback(data)
    try:
        output = run_baslinje_bau(frame_history(history) if feedback else history,
                                  data_context=get_data_context(), mode=mode)
        return jsonify(_gate_answer(output, feedback, history))
    except Exception as e:
        return _step_error(e)


@app.route('/api/evidens', methods=['POST'])
@require_auth
@rate_limited
def api_evidens():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    try:
        output = run_evidens(history, data_context=get_data_context(), mode=mode)
        # Parsed for the panel; `output` stays the source of truth for the
        # downstream agents and for the raw fallback when nothing parses.
        return jsonify({'output': output, 'evidence': parse_evidence(output)})
    except Exception as e:
        return _step_error(e)


# Evidens split into plan -> parts -> merge (agents/evidens_split.py). The
# client drives the three phases so that each request holds at most one model
# call; /api/evidens above stays as the single-call fallback for a history
# whose drivers cannot be parsed.

# The client starts one Opus call per driver at once. Real analyses have had
# up to four; the cap is there so a history cannot fan out into dozens.
MAX_DRIVERS = 12


def _drivers(history):
    drivers = drivers_from_history(history)
    if len(drivers) > MAX_DRIVERS:
        raise EvidensSplitError(f'Analysen har {len(drivers)} drivare; CAIA tar högst '
                                f'{MAX_DRIVERS} i ett steg. Dela upp åtgärden.')
    return drivers


@app.route('/api/evidens/plan', methods=['POST'])
@require_auth
@report_rate_limited
def api_evidens_plan():
    history = _history(request.get_json(silent=True))
    try:
        drivers = _drivers(history)
    except EvidensSplitError as e:
        return jsonify({'error': str(e)}), 422
    if not drivers:
        # The page then runs evidens as one call. Say so in the log: it is
        # the slower path, and a baslinje the parser cannot read is a finding.
        app.logger.warning("evidens plan: no drivers parsed from the baslinje; single-call fallback")
    return jsonify({'drivers': [{'number': d.number, 'name': d.name} for d in drivers]})


@app.route('/api/evidens/part', methods=['POST'])
@require_auth
@rate_limited
def api_evidens_part():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    number = data.get('driver')
    if not isinstance(number, int) or isinstance(number, bool):
        raise RequestError('driver ska vara drivarens nummer.')
    try:
        drivers = _drivers(history)
        driver = next((d for d in drivers if d.number == number), None)
        if driver is None:
            raise RequestError(f'Drivare {number} finns inte i analysen.')
        part = run_part(history, driver, drivers, data_context=get_data_context(), mode=mode)
        return jsonify({'number': driver.number, 'name': driver.name, 'text': part.raw})
    except RequestError:
        raise
    except EvidensSplitError as e:
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        return _step_error(e)


@app.route('/api/evidens/merge', methods=['POST'])
@require_auth
@rate_limited
def api_evidens_merge():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    items = data.get('parts') or []
    if not isinstance(items, list) or len(items) > MAX_DRIVERS:
        raise RequestError(f'parts ska vara en lista med högst {MAX_DRIVERS} delresultat.')
    try:
        drivers = _drivers(history)
        if not drivers:
            raise RequestError('Inga drivare att foga samman.')
        by_number = {d.number: d for d in drivers}
        parts = []
        total = 0
        for item in items:
            number = item.get('number') if isinstance(item, dict) else None
            driver = by_number.get(number)
            if driver is None:
                raise RequestError(f'Delresultat för okänd drivare {number}.')
            text = item.get('text') or ''
            if not isinstance(text, str):
                raise RequestError(f'Delresultatet för drivare {number} ska vara text.')
            # Each part goes through the line parsers and on to the merge
            # model, so it gets the same cap as a turn (S3, S6).
            if len(text) > MAX_PARTS_CHARS:
                raise RequestError(f'Delresultatet för drivare {number} är för långt '
                                   f'(högst {MAX_PARTS_CHARS} tecken).')
            # All of them go into one prompt, on top of the history, so the
            # sum has a cap of its own (re-review 2026-10-07, F3): twelve
            # parts at the cap above were 1.2 million characters in a single
            # counted call. The merged answer becomes one turn of the
            # history, so what goes in gets a turn's cap. Measured the same
            # day on 181 evidens answers on disk: the largest was 38 985
            # characters, the median 12 581.
            total += len(text)
            if total > MAX_PARTS_CHARS:
                raise RequestError('Delresultaten är tillsammans för långa '
                                   f'(högst {MAX_PARTS_CHARS} tecken).')
            parts.append(split_part(driver, text))
        # Re-checked here rather than trusted from the client: a missing part
        # would reach step 5 looking like a driver with no effect.
        check_parts_cover(drivers, parts)
        output, corrected, skipped = run_merge(history, parts, data_context=get_data_context(),
                                               mode=mode)
        # skipped: corrections whose field is not in the block. They stand at
        # the end of the output too, so steps 6 and 7 see them.
        return jsonify({'output': output, 'evidence': parse_evidence(output),
                        'corrected': corrected, 'skipped': skipped})
    except RequestError:
        raise
    except EvidensSplitError as e:
        return jsonify({'error': str(e)}), 422
    except Exception as e:
        return _step_error(e)


# The LLM fallback's longest call in the logs of 2026-10-14 took 204 s
# (the development log's measurement of cost and time per step). With less left than that, a fallback
# is likely to be cut by the platform after it has been paid for; the user is
# asked to run the step again instead, which runs the extraction again.
KALKYL_FALLBACK_MIN_S = 204.0
# The kalkyl text holds a table row per driver, scenario and year, and goes
# back to the server as one turn of the history (MAX_TURN_CHARS).
KALKYL_TOO_LONG = ('Kalkylen blev för lång för att gå vidare till granskningen: {drivers} drivare '
                   'räknade år för år till {target}. Dela upp åtgärden i flera analyser, eller '
                   'välj ett närmare målår.')
KALKYL_NO_TIME = ('Kalkylen gick inte att läsa ut ur analysen, och tiden räckte inte till '
                  'reservberäkningen. Kör steget igen.')


@app.route('/api/kalkyl', methods=['POST'])
@require_auth
@rate_limited
def api_kalkyl():
    started = time.monotonic()
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    try:
        # Deterministic path: extract structured params from the prior analysis,
        # then compute emissions in pure Python (caia.calc). Falls back to the
        # legacy LLM-math kalkyl if extraction or computation fails.
        try:
            extracted = run_kalkyl_extract(history, mode=mode)
            if extracted:
                model = CalcModel.from_dict(extracted, mode=mode)
                result = compute(model)
                # The appendix ends the kalkyl text; /api/rapport copies it
                # into the report as it stands (caia.appendix). Before it, what
                # the action changes in each driver's own unit, which
                # /api/rapport moves into the report beside the tons. Its own
                # try: a sentence must never cost the computed result.
                try:
                    changes = activity_changes(model)
                    activity = render_activity(model, changes)
                except Exception as e:
                    _log_failure("activity sentences failed", e)
                    changes, activity = None, ""
                output = "\n\n".join(part for part in (
                    render_markdown(model, result), activity, render_appendix(model, result)) if part)
                # The page sends this text back as a turn of the history, and
                # _history refuses a turn over MAX_TURN_CHARS and a history
                # over MAX_HISTORY_CHARS. Said here, where the user can act on
                # it, and not as "Tur 11 är för lång" at the next step.
                # Returned, not raised: the fallback below would catch it and
                # spend a second model call on the same analysis.
                carried = sum(len(turn['content']) for turn in history)
                if len(output) > MAX_TURN_CHARS or carried + len(output) > MAX_HISTORY_CHARS:
                    app.logger.warning("kalkyl: the text is %d characters after %d of history "
                                       "(%d drivers to %d); over the cap", len(output), carried,
                                       len(model.drivers), model.target_year)
                    return jsonify({'error': KALKYL_TOO_LONG.format(
                        drivers=len(model.drivers), target=model.target_year)}), 422
                # Scenario span + cumulative feed the right-panel hero (low/mid/high
                # range bar + 'ackumulerat till målår'), mirroring the åtgärdskort mockup.
                # Low and high for the same number the headline is: the target
                # year in potential mode, the average in a follow-up.
                head_year = result['headline'].get('year')

                def _band(sc: str) -> float:
                    tot = result[sc]['total']
                    return tot['years'][head_year]['net'] if head_year else tot['avg_net']
                span = {
                    'net_lo': round(_band('min'), 1),
                    'net_hi': round(_band('max'), 1),
                    # The average per year, shown under a target-year headline.
                    'avg_net': round(result['med']['total']['avg_net'], 1),
                    'headline_year': head_year,
                    'cum_net': round(result['med']['total']['cumulative_net']),
                    # Their low and high, so the card shows each number with
                    # its range and not only the headline's (2026-10-13).
                    'avg_lo': round(result['min']['total']['avg_net'], 1),
                    'avg_hi': round(result['max']['total']['avg_net'], 1),
                    'cum_lo': round(result['min']['total']['cumulative_net']),
                    'cum_hi': round(result['max']['total']['cumulative_net']),
                    'target_year': model.target_year,
                    # The years "medel/år" averages over, so the page can say so.
                    'window': list(result['med']['total']['avg_window']),
                    'mode': mode,
                }
                # The same sentences for the page's summary, largest first.
                if changes and changes['rows']:
                    span['activity'] = {
                        'rows': [{'driver': r['driver'], 'text': r['text']}
                                 for r in sorted(changes['rows'], key=lambda r: -r['weight'])],
                        'notes': changes['notes'],
                    }
                # Every year, so the hero can draw how the benefit builds up.
                # Its own try: a chart must never cost the computed result.
                try:
                    ser = year_series(model)
                    span['series'] = {'years': ser['years'],
                                      **{sc: [round(v, 3) for v in ser[sc]]
                                         for sc in ('min', 'med', 'max')}}
                except Exception as e:
                    _log_failure("year series failed", e)
                if mode == UPPFOLJNING:
                    span['followup'] = {
                        'year': result['followup_year'],
                        'realised': {sc: round(result[sc]['total']['realised_net'], 1)
                                     for sc in ('min', 'med', 'max')},
                        'remaining': {sc: round(result[sc]['total']['remaining_net'], 1)
                                      for sc in ('min', 'med', 'max')},
                        # share is a fraction: one decimal would turn 0.25 into 0.2.
                        'allocation': [{k: (round(v, 3 if k == 'share' else 1)
                                            if isinstance(v, float) else v)
                                        for k, v in row.items()}
                                       for row in result['allocation']],
                    }
                # Källmarkering in its own try: a fault in the source check
                # must not throw a computed result away for the LLM fallback.
                try:
                    kallor, kallor_md = kallmarkering(model, history)
                except Exception as e:
                    _log_failure("källmarkering failed", e)
                    kallor, kallor_md = None, KALLOR_KONTROLL_FEL
                warnings = sanity_warnings(result, model)
                # A number that departs from what the user approved (S21) is
                # named under Talens ursprung; the headline says it exists.
                avviker = sum(1 for k in kallor or [] if k.get('godkant'))
                if avviker:
                    warnings.append(
                        (f"{avviker} tal i beräkningen avviker" if avviker > 1
                         else "Ett tal i beräkningen avviker")
                        + " från baslinjen eller antagandena du godkände. Se Kontrollera "
                        "först under Talens ursprung.")
                return jsonify({'output': output, 'deterministic': True,
                                'headline': result['headline'], 'span': span,
                                'warnings': warnings,
                                'kallmarkering': kallor, 'kallmarkering_md': kallor_md})
            app.logger.warning("kalkyl extraction found no JSON; using the LLM fallback")
        except anthropic.APIError:
            # The provider failed, not the reading. The fallback is a second
            # call to the same provider with what is left of the function's
            # 300 s (a connection dropped 108 s into the extraction,
            # 2026-10-13). Answer now instead: _step_error marks a dropped
            # connection retryable and the page runs the step again.
            raise
        except Exception as e:
            _log_failure("deterministic kalkyl failed, falling back to LLM", e)
        # The fallback is a second model call in the same function (security
        # review S29). It gets what is left of the request's budget, and is
        # not started when that is less than it has been seen to need.
        left = api_client.REQUEST_TIMEOUT_S - (time.monotonic() - started)
        if left < KALKYL_FALLBACK_MIN_S:
            app.logger.warning("kalkyl: %.0f s left of the budget, the LLM fallback "
                               "needs %.0f s; not started", left, KALKYL_FALLBACK_MIN_S)
            return jsonify({'error': KALKYL_NO_TIME}), 502
        output = run_kalkyl(history, data_context=get_data_context(), mode=mode,
                            timeout_s=left)
        return jsonify({'output': output, 'deterministic': False,
                        'kallmarkering': None, 'kallmarkering_md': KALLOR_SAKNAS})
    except Exception as e:
        return _step_error(e)


@app.route('/api/qa', methods=['POST'])
@require_auth
@rate_limited
def api_qa():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    try:
        return jsonify({'output': run_cove_qa(history, mode=mode)})
    except Exception as e:
        return _step_error(e)


@app.route('/api/rapport', methods=['POST'])
@require_auth
@rate_limited
def api_rapport():
    data = request.get_json(silent=True)
    history, mode = _history(data), _mode(data)
    try:
        # The calculation appendix is the engine's, copied from the kalkyl
        # step. The model is told not to write one; if it does anyway, its
        # version is cut so the report cannot carry two sets of numbers.
        output, cut = with_engine_appendix(run_rapport(history, mode=mode), history)
        if cut:
            app.logger.warning("rapport: removed a calculation appendix the model wrote itself")
        return jsonify({'output': output})
    except Exception as e:
        return _step_error(e)


# The label, then the first number after it, tolerating a range tail
# ("1 200 – 1 400") without crossing the dash inside the captured group.
#
# The number used to be `[\d\s .,]*?` followed by `\s*` and another such
# class, all unbounded: runs that could each take the same blanks, so a label
# followed by 2 000 blanks took 11 s to give up and 4 000 never finished
# (security review S3), from one saved report. Now the number and the range
# tail are bounded (a number is at most 41 characters, a tail 60), no two
# unbounded runs of blanks sit next to each other, and the number is only
# looked for in a short window after each label, so the work per label is
# bounded by the window, not by the report. Same forms accepted as before.
_LABELS = {
    'terr': re.compile(r'Medel\s*effekt/år\s*\(Territoriell\)', re.IGNORECASE),
    'cons': re.compile(r'Medel\s*effekt/år\s*\(Konsumtion\)', re.IGNORECASE),
    'net': re.compile(r'Medel\s*effekt/år\s*\(Netto(?:/Total)?\)', re.IGNORECASE),
}
_VALUE = re.compile(r'\s*(?::\s*)?(-?\d[\d\s.,]{0,40}?)\s*(?:[–—-][\d\s.,]{0,60}?)?ton',
                    re.IGNORECASE)
# The label's colon, a number and a range tail fit in about 110 characters;
# the window leaves room for stray blanks around them.
_VALUE_WINDOW = 200


def extract_key_metric(markdown: str) -> dict:
    """Pull the three 'Medel effekt/år' headline numbers from a CAIA report.

    Robust to thousands-spaces and decimal commas. Returns {} on no match so a
    report still saves even if the format drifts.
    """
    out = {}
    if not markdown:
        return out
    for key, label in _LABELS.items():
        m = next((v for lm in label.finditer(markdown)
                  if (v := _VALUE.match(markdown, lm.end(), lm.end() + _VALUE_WINDOW))), None)
        if not m:
            continue
        raw = m.group(1).strip().replace(' ', '').replace(' ', '').replace(',', '.')
        try:
            out[key] = float(raw)
        except ValueError:
            continue
    return out


_THEMATIC_BREAK = re.compile(r'^\s*([-*_])(\s*\1){2,}\s*$')


def _extract_action_name(markdown: str) -> str:
    """Fallback title when the client did not send one: the first markdown
    heading, else the first line of text.

    The rapport agent leads with '## <title>' but often puts a '---' above
    it. That thematic break stripped to '---' and was saved as the action
    name, so the saved-reports list showed a row called '---'. Breaks and
    blank lines are skipped, and a heading anywhere wins over prose above it.
    The canonical name lives in the intake profile; the frontend sends that
    one, and this only runs when it has nothing."""
    if not markdown:
        return 'Namnlös åtgärd'
    first_text = ''
    for line in markdown.splitlines():
        if _THEMATIC_BREAK.match(line) or not line.strip():
            continue
        if line.lstrip().startswith('#'):
            s = line.strip().lstrip('#').strip()
            if s:
                return s[:200]
        if not first_text:
            first_text = line.strip().strip('*_ ')
    return first_text[:200] or 'Namnlös åtgärd'


@app.route('/api/parameters', methods=['GET'])
@require_auth
@report_rate_limited
def get_parameters():
    """The hardcoded climate factors the calculations rest on, with provenance.

    Read-only for now (source = parameters_library.md). Forward-compatible: a
    future editable version swaps the data source behind this same contract.

    `value_display` is what the view prints: for a row that reads a data file,
    the number in the file instead of the LOOKUP expression, with `value_note`
    saying where it came from."""
    sections = parameter_view()
    counts = {'lokal': 0, 'datafil': 0, 'schablon': 0}
    for s in sections:
        for r in s['rows']:
            counts[r['provenance']] = counts.get(r['provenance'], 0) + 1
    return jsonify({'sections': sections, 'counts': counts,
                    'total': sum(counts.values()), 'editable': False})


# What a saved row may hold. A report is at most ~12k tokens of model output,
# so 300k characters leaves room without letting one row take megabytes.
REPORT_MAX_CHARS = {'formatted_report': 300_000, 'intake_summary': 50_000, 'action_name': 300}
KEY_METRIC_FIELDS = ('terr', 'cons', 'net')


def _report_text(data: dict, field: str) -> str:
    value = data.get(field) or ''
    if not isinstance(value, str):
        raise RequestError(f'{field} ska vara text.')
    # Characters and bytes both, like the table (deploy/reports.sql): a
    # character can be four bytes, and Swedish text is at most two.
    if (len(value) > REPORT_MAX_CHARS[field]
            or len(value.encode('utf-8', 'surrogatepass')) > 2 * REPORT_MAX_CHARS[field]):
        raise RequestError(f'{field} är för lång (högst {REPORT_MAX_CHARS[field]} tecken).')
    return value


def _client_key_metric(value) -> dict | None:
    """The calc's headline as the page sends it: terr/cons/net, finite numbers.

    It is stamped source=calc, so it has to be one: anything else used to be
    saved as the program's result."""
    if value in (None, {}):
        return None
    if not isinstance(value, dict) or not set(value) <= set(KEY_METRIC_FIELDS) | {'year'}:
        raise RequestError('key_metric får bara innehålla terr, cons, net och year.')
    # year: the target year a potential-mode headline is for (2026-10-13).
    # Without it the numbers are an average per year, as every row before.
    year = value.get('year')
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1990 <= year <= 2100):
        raise RequestError('key_metric.year ska vara ett årtal.')
    for k in KEY_METRIC_FIELDS:
        v = value.get(k)
        if v is None:
            continue
        # An integer too large for a float (JSON has no upper bound, Python
        # reads 1e400 written out) raised OverflowError in isfinite: a 500.
        try:
            finite = not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
        except OverflowError:
            finite = False
        if not finite:
            raise RequestError(f'key_metric.{k} ska vara ett tal.')
    return value if any(value.get(k) is not None for k in KEY_METRIC_FIELDS) else None


@app.route('/api/reports', methods=['POST'])
@require_supabase_auth
@report_rate_limited
def create_report():
    token = request.headers.get('Authorization', '')[7:]
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise RequestError('Förväntade ett JSON-objekt.')
    markdown = _report_text(data, 'formatted_report')
    if not markdown.strip():
        raise RequestError('Rapporten är tom.')
    # The headline numbers come from the deterministic calc (caia.calc) when
    # the pipeline had one; the client sends them as key_metric. Scraping the
    # LLM-written report is the fallback for the LLM-math path only, and the
    # row says which it was, so a saved report never passes a regex hit off
    # as a computed result.
    key_metric = _client_key_metric(data.get('key_metric'))
    if key_metric:
        key_metric = dict(key_metric, source='calc')
    else:
        key_metric = extract_key_metric(markdown)
        if key_metric:
            key_metric['source'] = 'rapport'
    row = {
        'user_id': request.user_id,
        'action_name': _report_text(data, 'action_name') or _extract_action_name(markdown),
        'key_metric': key_metric,
        'intake_summary': _report_text(data, 'intake_summary'),
        'formatted_report': markdown,
    }
    try:
        result = supabase_request('POST', 'reports', data=row, token=token)
    except SupabaseError as e:
        # The table has its own list of who may save (caia.allowed, re-review
        # 2026-10-07, F2). An account the app lets in and the table refuses
        # means the two lists differ, which only the operator can mend.
        if e.status in (401, 403):
            raise SupabaseError(NOT_SAVED) from e
        raise
    return jsonify(result[0] if isinstance(result, list) else result)


@app.route('/api/reports', methods=['GET'])
@require_supabase_auth
@report_rate_limited
def list_reports():
    token = request.headers.get('Authorization', '')[7:]
    params = {
        'select': 'id,action_name,key_metric,created_at',
        'user_id': f'eq.{request.user_id}',
        'order': 'created_at.desc',
        'limit': '30',
    }
    return jsonify(supabase_request('GET', 'reports', token=token, params=params) or [])


_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)


@app.route('/api/reports/<report_id>', methods=['GET'])
@require_supabase_auth
@report_rate_limited
def get_report(report_id):
    token = request.headers.get('Authorization', '')[7:]
    if not _UUID.fullmatch(report_id):
        return jsonify({'error': 'Ej hittad'}), 404
    params = {'id': f'eq.{report_id}', 'user_id': f'eq.{request.user_id}'}
    result = supabase_request('GET', 'reports', token=token, params=params)
    if not result:
        return jsonify({'error': 'Ej hittad'}), 404
    return jsonify(result[0])


# --- Portfolio: several saved analyses at once (caia.calc.portfolj) ---------

PORTFOLJ_NO_APPENDIX = ("kan inte användas i en portfölj: analysen saknar kalkylmotorns tekniska "
                        "bilaga (sparad före 30 september 2026, eller räknad utan motorn). "
                        "Gör om analysen för att ta med den.")


@app.errorhandler(PortfoljError)
def _handle_portfolj_error(exc):
    return jsonify({'error': str(exc)}), 422


def _portfolj_ids(data) -> list[str]:
    ids = data.get('ids') if isinstance(data, dict) else None
    if not isinstance(ids, list) or not all(isinstance(i, str) and _UUID.fullmatch(i) for i in ids):
        raise RequestError('ids ska vara en lista med analysernas id.')
    if len(set(ids)) != len(ids):
        raise PortfoljError('Samma analys är vald två gånger.')
    if len(ids) < 2:
        raise PortfoljError('Välj minst två analyser. En portfölj av en åtgärd är analysen själv.')
    if len(ids) > portfolj.MAX_ACTIONS:
        raise PortfoljError(f'Välj högst {portfolj.MAX_ACTIONS} analyser åt gången.')
    return ids


def _portfolj_insatser(ids: list[str]) -> list[tuple[dict, portfolj.Insats | None]]:
    """The user's own saved rows, in the order asked for, each with its
    appendix read back to numbers (None where it has none)."""
    token = request.headers.get('Authorization', '')[7:]
    params = {'select': 'id,action_name,created_at,formatted_report',
              'id': f'in.({",".join(ids)})', 'user_id': f'eq.{request.user_id}'}
    rows = {r['id']: r for r in supabase_request('GET', 'reports', token=token, params=params) or []}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise PortfoljError('En vald analys finns inte bland dina sparade analyser.')
    out = []
    for i in ids:
        row = rows[i]
        namn = plain(row.get('action_name') or 'Namnlös analys')
        bilaga = portfolj.parse_appendix(row.get('formatted_report') or '')
        ins = None
        if bilaga is not None:
            ins = portfolj.Insats(id=i, namn=namn, mode=bilaga.mode, delar=bilaga.delar,
                                  skapad=str(row.get('created_at') or ''))
        out.append(({'id': i, 'namn': namn, 'skapad': str(row.get('created_at') or '')[:10]}, ins))
    return out


def _portfolj_potter() -> list[portfolj.Pott]:
    try:
        return portfolj.load_potter(kommun.active().potter_file)
    except PortfoljError as e:
        # The message names a path on the server; the user gets what to do.
        app.logger.error("potter.toml: %s", e)
        raise PortfoljError('Kommunens register över utsläppspotter går inte att läsa. '
                            'Säg till den som sköter CAIA.') from e


@app.route('/api/portfolj/atgarder', methods=['POST'])
@require_supabase_auth
@report_rate_limited
def portfolj_atgarder():
    """Step one: what the chosen analyses hold, so the user can mark which of
    their parts work on which emission pot."""
    ids = _portfolj_ids(request.get_json(silent=True))
    pairs = _portfolj_insatser(ids)
    usable = [ins for _, ins in pairs if ins is not None]
    dup = portfolj.duplicate_runs(usable)
    if dup:
        raise PortfoljError(portfolj.duplicate_message(dup))
    atgarder = []
    for meta, ins in pairs:
        if ins is None:
            atgarder.append(dict(meta, fel=PORTFOLJ_NO_APPENDIX))
            continue
        atgarder.append(dict(meta, mode=ins.mode,
                             delar=[{'namn': d.namn, 'pott': d.pott} for d in ins.delar]))
    return jsonify({'potter': [p.public() for p in _portfolj_potter()], 'atgarder': atgarder})


@app.route('/api/portfolj', methods=['POST'])
@require_supabase_auth
@report_rate_limited
def portfolj_berakna():
    """Step two: the portfolio's numbers, per pot and per action, as text."""
    data = request.get_json(silent=True)
    ids = _portfolj_ids(data)
    potter = _portfolj_potter()
    known = {p.id for p in potter}
    val = data.get('potter') or {}
    mal = data.get('mal_for') or {}
    if not isinstance(val, dict) or not isinstance(mal, dict):
        raise RequestError('potter och mal_for ska vara objekt.')
    insatser = []
    for meta, ins in _portfolj_insatser(ids):
        if ins is None:
            raise PortfoljError(f"«{meta['namn']}» {PORTFOLJ_NO_APPENDIX}")
        chosen = val.get(ins.id)
        if chosen is not None:
            if not isinstance(chosen, list) or len(chosen) != len(ins.delar):
                raise RequestError(f"Utsläppspotterna för «{ins.namn}» ska vara en per del.")
            for d, p in zip(ins.delar, chosen):
                if p is not None and (not isinstance(p, str) or p not in known):
                    raise PortfoljError(f'Utsläppspotten {p!r} finns inte i kommunens register.')
                d.pott = p
        targets = mal.get(ins.id) or []
        if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            raise RequestError('mal_for ska ge en lista med id per analys.')
        ins.mal_for = tuple(targets)
        insatser.append(ins)
    result = portfolj.compute_portfolio(insatser, potter)
    return jsonify({'markdown': portfolj.render_portfolio(result), 'warnings': result['warnings']})
