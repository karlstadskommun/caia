"""Pin the environment the suite runs in.

The app reads its configuration from the environment at import time, so a
shell that happens to hold production credentials used to change what the
tests tested: test_backend wrote rows into the production `reports` table,
two auth tests failed or passed depending on SUPABASE_* in the shell, and a
CAIA_KOMMUN_DIR exported while following INSTALL.md made 28 tests fail.

Everything below is stripped before any test module imports the app, and the
kommunprofil is pinned to karlstad (tests that want another profile set it
themselves). A copy of the code without Karlstad's profile, as in a public
release that ships only the exempel profile, pins exempel instead and skips
the tests marked `karlstad`: they read Karlstad's parameter library and data. The opt-in suites keep what they need:

    RUN_SUPABASE_IT=1   keeps SUPABASE_*          (tests/test_backend.py, writes to the real project)
    RUN_E2E=1           keeps OPENROUTER_API_KEY  (tests/test_e2e.py, real model calls)

Tests marked `node` run the page's own JavaScript in Node.js. Without node on
PATH they are skipped with a reason that says so, except under CI=true, where
a skip would hide that the page was never tested.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_KEEP = set()
if os.environ.get('RUN_SUPABASE_IT') == '1':
    _KEEP |= {k for k in os.environ if k.startswith('SUPABASE_')}
if os.environ.get('RUN_E2E') == '1':
    _KEEP.add('OPENROUTER_API_KEY')

for _name in list(os.environ):
    if _name in _KEEP:
        continue
    if _name.startswith(('SUPABASE_', 'CAIA_')) or _name in ('OPENROUTER_API_KEY', 'VERCEL'):
        del os.environ[_name]

HAS_KARLSTAD = os.path.isfile(os.path.join(
    os.path.dirname(__file__), '..', 'src', 'caia', 'kommuner', 'karlstad', 'kommun.toml'))
os.environ['CAIA_KOMMUN'] = 'karlstad' if HAS_KARLSTAD else 'exempel'

from caia import kommun  # noqa: E402

kommun.set_active(None)


def pytest_configure(config):
    config.addinivalue_line('markers', 'node: runs the page script in Node.js')
    config.addinivalue_line('markers', "karlstad: reads Karlstad's kommunprofil; "
                                       'skipped when the profile is not in the tree')


def pytest_collection_modifyitems(config, items):
    if not HAS_KARLSTAD:
        no_profile = pytest.mark.skip(reason='Karlstads kommunprofil finns inte i den här '
                                             'utgåvan; testet läser dess parameterbibliotek och data.')
        for item in items:
            if 'karlstad' in item.keywords:
                item.add_marker(no_profile)
    if shutil.which('node') or os.environ.get('CI') == 'true':
        return
    skip = pytest.mark.skip(reason='node saknas, så sidans JavaScript testas inte. '
                                   'Installera Node.js 18 eller senare.')
    for item in items:
        if 'node' in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """The rate limiter counts per client IP in process, and every test
    client is 127.0.0.1, so without this the suite throttles itself."""
    from caia.web import app as A
    A._rate_hits.clear()
    A._report_hits.clear()
    A._login_failures.clear()
    yield
