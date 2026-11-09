"""INSTALL.md is what another municipality's IT follows without us in the
room. These tests fail when the code and the guide drift apart: a setting
the code reads that the guide does not mention, a column the code writes that
the SQL does not create, or a timeout the proxy would cut short."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

NEXT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NEXT / 'src'))
INSTALL = (NEXT / 'INSTALL.md').read_text(encoding='utf-8')
SQL = (NEXT / 'deploy' / 'reports.sql').read_text(encoding='utf-8')
APP = (NEXT / 'src' / 'caia' / 'web' / 'app.py').read_text(encoding='utf-8')


def _env_vars_in_code() -> set[str]:
    names = set()
    for path in (NEXT / 'src').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        names |= set(re.findall(r'os\.environ\.get\(\s*["\']([A-Z_]+)["\']', text))
        names |= set(re.findall(r'os\.environ\[\s*["\']([A-Z_]+)["\']', text))
        names |= set(re.findall(r'_count_setting\(\s*["\']([A-Z_]+)["\']', text))
    return names


def _env_vars_in_guide_table() -> set[str]:
    return set(re.findall(r'^\| `([A-Z_]+)` \|', INSTALL, re.MULTILINE))


def test_every_setting_the_code_reads_is_in_the_guide():
    code = _env_vars_in_code()
    assert code, 'found no settings in the code; the regex is stale'
    assert code <= _env_vars_in_guide_table(), code - _env_vars_in_guide_table()


def test_the_guide_lists_no_setting_the_code_does_not_read():
    assert _env_vars_in_guide_table() <= _env_vars_in_code()


def test_env_example_lists_every_setting_the_app_and_tools_read():
    names = set()
    for folder in ('src', 'tools'):
        for path in (NEXT / folder).rglob('*.py'):
            names |= set(re.findall(r'(?:os\.environ(?:\.get)?|_count_setting)[\(\[]\s*["\']([A-Z_]+)["\']',
                                    path.read_text(encoding='utf-8')))
    example = set(re.findall(r'^([A-Z_]+)=', (NEXT / '.env.example').read_text(encoding='utf-8'),
                             re.MULTILINE))
    assert names == example, (names - example, example - names)


def test_the_guide_shows_the_sql_file_verbatim():
    blocks = re.findall(r'```sql\n(.*?)```', INSTALL, re.DOTALL)
    assert blocks == [SQL]


def _sql_columns() -> set[str]:
    body = SQL.split('create table public.reports (', 1)[1].split(');', 1)[0]
    return {line.split()[0] for line in body.strip().splitlines()}


def test_the_table_has_every_column_the_code_writes_and_reads():
    written = APP.split("def create_report", 1)[1].split("supabase_request(", 1)[0]
    written = set(re.findall(r"'(\w+)':", written.split('row = {', 1)[1]))
    listed = re.search(r"'select': '([\w,]+)'", APP).group(1).split(',')
    filtered = {'id', 'user_id'}  # get_report filters on both
    needed = written | set(listed) | filtered
    assert needed <= _sql_columns(), needed - _sql_columns()


def test_saved_reports_are_protected_row_by_row():
    assert 'enable row level security' in SQL
    assert 'grant select, insert, delete on public.reports to authenticated' in SQL
    assert 'to anon' not in SQL
    granted = re.findall(r'grant ([\w, ]+) on public\.reports to (\w+);', SQL)
    assert granted == [('select, insert, delete', 'authenticated')], 'a saved report is never changed'


MIGRATION = (NEXT / 'deploy' / 'migrations' / '2026-10-reports-security.sql').read_text(encoding='utf-8')


def _limits(sql: str) -> dict[str, int]:
    return {col: int(n) for col, n in re.findall(r'char_length\((\w+)\) <= (\d+)', sql)}


def test_the_table_limits_are_the_apps_limits():
    """Security review S7: a row written straight to the API, past the app,
    can be no larger than one the app would save."""
    sys.path.insert(0, str(NEXT / 'src'))
    os.environ.setdefault('CAIA_KOMMUN', 'karlstad')
    from caia.web.app import REPORT_MAX_CHARS
    assert _limits(SQL) == REPORT_MAX_CHARS
    assert _limits(MIGRATION) == REPORT_MAX_CHARS


def test_no_policy_lets_an_anonymous_account_in():
    for sql in (SQL, MIGRATION):
        policies = re.findall(r'create policy .*?;', sql, re.DOTALL)
        assert len(policies) == 3
        for policy in policies:
            assert 'to authenticated' in policy
            assert "'is_anonymous'" in policy, policy.splitlines()[0]


def test_the_migration_leaves_the_table_as_a_new_install_has_it():
    # The policies a new install creates, and Karlstad's old ones removed.
    assert set(re.findall(r'create policy "([^"]+)"', MIGRATION)) == \
        set(re.findall(r'create policy "([^"]+)"', SQL))
    # Every policy on the table goes, whatever its name: policies OR
    # together, so one left behind would keep the table as open as before.
    drop_all = re.search(r'for (\w+) in\s+select policyname from pg_policies\s+'
                         r"where schemaname = 'public' and tablename = 'reports'\s+loop\s+"
                         r"execute format\('drop policy %I on public\.reports', \1\.policyname\);",
                         MIGRATION)
    assert drop_all, 'the migration must drop every policy on reports'
    assert MIGRATION.index(drop_all.group(0)) < MIGRATION.index('create policy')
    assert 'grant select, insert, delete on public.reports to authenticated;' in MIGRATION
    assert 'revoke all on public.reports from anon;' in MIGRATION
    assert MIGRATION.count('not valid') == 4, 'old rows must not stop the migration'


def test_proxy_and_server_outlast_the_model_call():
    from caia.api_client import REQUEST_TIMEOUT_S
    gunicorn = int(re.search(r'--timeout (\d+)', INSTALL).group(1))
    nginx = int(re.search(r'proxy_read_timeout (\d+)s', INSTALL).group(1))
    assert gunicorn > REQUEST_TIMEOUT_S and nginx > REQUEST_TIMEOUT_S
    assert f'{int(REQUEST_TIMEOUT_S)} sekunder' in INSTALL


def test_the_service_starts_the_real_app_object():
    m = re.search(r'--pythonpath (\S+) .* (\S+):(\w+)\n', INSTALL)
    src, module, obj = m.groups()
    assert (NEXT / src / Path(*module.split('.'))).with_suffix('.py').is_file()
    assert re.search(rf'^{obj} = Flask\(', APP, re.MULTILINE)


def test_python_version_floor_matches_what_the_code_needs():
    # kommun.py uses tomllib, which arrived in Python 3.11.
    assert 'import tomllib' in (NEXT / 'src' / 'caia' / 'kommun.py').read_text()
    assert 'Python 3.11 eller senare' in INSTALL
    assert os.path.exists(NEXT / 'requirements.txt')


@pytest.mark.parametrize('name', ['requirements.txt', 'requirements-dev.txt', 'requirements-server.txt'])
def test_every_dependency_is_pinned_exactly(name):
    """With `>=` an install resolved whatever was newest that day: anthropic
    went from the 0.x the code was written against to 1.8, and an update on
    the server re-resolved everything blind."""
    for line in (NEXT / name).read_text().splitlines():
        line = line.split('#')[0].strip()
        if not line or line.startswith('-r '):
            continue
        assert re.fullmatch(r'[A-Za-z0-9_.\-]+(\[[a-z]+\])?==[0-9][0-9A-Za-z.]*', line), (name, line)


def test_the_install_commands_use_the_pinned_server_file():
    assert 'requirements-server.txt' in INSTALL
    assert 'requirements.txt gunicorn' not in INSTALL


def test_the_deploy_pins_a_python_that_compiles_the_parsers():
    """The parsers use possessive quantifiers (security review S3), which
    Python reads from 3.11. Vercel took its default, 3.12, because nothing
    named a version; a lower default would fail every request at import."""
    pinned = (NEXT / '.python-version').read_text(encoding='utf-8').strip()
    assert tuple(int(p) for p in pinned.split('.')[:2]) >= (3, 11), pinned


ALLOWLIST = (NEXT / 'deploy' / 'migrations' / '2026-10-reports-allowlist.sql').read_text(encoding='utf-8')


def test_the_table_limits_bytes_as_well_as_characters():
    """Re-review F2: char_length counts characters, and 300 000 of them can
    be 1.2 MB. The byte limit is twice the character limit, which Swedish
    text never passes, and the app checks the same (app._report_text)."""
    sys.path.insert(0, str(NEXT / 'src'))
    os.environ.setdefault('CAIA_KOMMUN', 'karlstad')
    from caia.web.app import REPORT_MAX_CHARS
    want = {col: 2 * REPORT_MAX_CHARS[col] for col in ('intake_summary', 'formatted_report')}
    for sql in (SQL, ALLOWLIST):
        got = {col: int(n) for col, n in re.findall(r'check \(octet_length\((\w+)\) <= (\d+)\)', sql)}
        assert got == want


def test_only_an_account_on_the_tables_own_list_may_save():
    """Re-review F2: the table is reachable past the app with the public
    key, so the app's allow-list alone let any account in the project save."""
    # The allow-list migration ran while the schema was called zaid, and is
    # kept as it ran; 2026-10-rename-schema-caia.sql moves it to caia.
    for sql, schema in ((SQL, 'caia'), (ALLOWLIST, 'zaid')):
        insert = re.search(r'create policy "reports: spara egna".*?;', sql, re.DOTALL).group(0)
        assert f'{schema}.account_allowed()' in insert
        assert "'is_anonymous'" in insert and 'auth.uid()' in insert
        assert 'security definer set search_path' in sql
        assert f'revoke all on {schema}.allowed from anon, authenticated;' in sql
        assert 'u.email_confirmed_at is not null' in sql
        assert not re.search(rf'^insert into {schema}\.allowed', sql, re.MULTILINE), \
            'the entries are the operator\'s to write; a default would let a stranger\'s domain in'
    assert ALLOWLIST.count('not valid') == 2, 'old rows must not stop the migration'
    assert 'drop policy if exists "reports: spara egna"' in ALLOWLIST


RENAME = (NEXT / 'deploy' / 'migrations' / '2026-10-rename-schema-caia.sql').read_text(encoding='utf-8')


def _sql_code(sql: str) -> str:
    """The statements, without comment lines."""
    return '\n'.join(l for l in sql.splitlines() if not l.lstrip().startswith('--'))


def test_the_schema_rename_rewrites_the_function_in_the_same_transaction():
    """The function's body names the schema and is read at every call, so a
    rename alone makes every save fail. The rewritten function must be the
    one reports.sql creates, or an installation that migrated would check
    accounts differently from a new one."""
    code = _sql_code(RENAME)
    begin, rename, function, commit = (code.index(s) for s in (
        'begin;', 'alter schema zaid rename to caia;', 'create or replace function caia.account_allowed()', 'commit;'))
    assert begin < rename < function < commit
    assert 'zaid' not in code[function:], 'the rewritten function still reads the old schema'

    def body(sql: str) -> str:
        return re.search(r'create or replace function caia\.account_allowed\(\).*?\$\$;', sql, re.DOTALL).group(0)
    assert body(RENAME) == body(SQL)
    assert 'grant execute on function caia.account_allowed() to authenticated;' in code
    assert 'revoke all on function caia.account_allowed() from public, anon;' in code
    assert 'reports' not in code, 'the rename must not touch the table or its rules'
    assert 'raise exception' in code[begin:rename], 'both schemas present must stop the migration'


def test_the_guide_tells_the_operator_to_fill_the_list():
    assert 'insert into caia.allowed (entry) values' in INSTALL
    assert 'caia.allowed' in (NEXT / 'DEPLOY.md').read_text(encoding='utf-8')
