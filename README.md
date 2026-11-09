# CAIA: Climate Action Impact Analysis

CAIA estimates the climate effect of a municipal climate action. The user describes the action in a chat, and CAIA produces an action profile, a baseline, assumptions with sources, a calculation in tonnes CO2e per year and a report. The user sees and approves (or corrects) each of the first four steps before the next one runs; the calculation, the quality review and the report then run in one go. The arithmetic is done by ordinary Python code, not by the language model, and the report ends with a section showing where every number came from.

CAIA has two analysis modes, chosen before the analysis starts: *forecast* (potentialläge) for an action that has not been carried out yet, and *follow-up* (uppföljningsläge) for an intervention that has already been made, where the question is what that particular money actually achieved and what remains.

CAIA was developed by Karlstads kommun (the Municipality of Karlstad, Sweden) within Klimatneutrala Karlstad 2030, supported by Viable Cities. This is the first public release, version 1.0.0.

**Language.** The user interface, the prompts and most of the documentation are in Swedish. This README is also available in Swedish: [README.sv.md](README.sv.md).

## Licence

Copyright Karlstads kommun. Licensed under the EUPL.

CAIA is free software under the [European Union Public Licence v. 1.2](LICENSE) (EUPL-1.2). The Swedish text is in [LICENSE.sv.txt](LICENSE.sv.txt); all language versions approved by the European Commission are equally valid. In short: you may use, study, change and share CAIA. If you distribute a changed version, or let others use a changed version over a network, you share your changes under the same licence. The software is provided as is, without warranty (EUPL articles 7 and 8).

The licence covers the code and documentation in this repository. See [Data](#data) for the municipality data that is not included.

## Data

The repository ships with one municipality profile, `exempel` (`next/src/caia/kommuner/exempel/`): a template with national default values and no local data files. A municipality fills in its own values and data files to make a profile of its own (see [Set up for a municipality](#set-up-for-a-municipality)).

Karlstad's own profile (its parameter library and data files) is not part of this release. Some of its data files come from third parties with their own terms. Tests that need Karlstad's profile are marked `karlstad` and are skipped with a reason when it is absent, so the test summary reports a number of skipped tests.

`next/tests/fixtures/` holds saved model output from analyses of Karlstad's actions. The tests and the development server use it. It contains no personal data.

## Repository layout

| Folder | What |
|---|---|
| [`next/`](next/) | The application. A Flask app with a seven-step pipeline against Claude models via OpenRouter. |
| `next/src/caia/kommuner/` | Municipality profiles. `exempel` is the template for a new municipality. |
| [`docs/`](docs/) | Method, user guide, architecture, API, operations, decisions, data format and a summary of the security review (all in Swedish). |
| `clientlibs/` | The versions of the three libraries the page loads, listed for Dependabot. Nothing is installed from here. |

## Quick start on your own computer

Requires Python 3.11 or later and git. Node.js 18 or later is only needed for the tests that run the page's JavaScript; without node they are skipped with a message.

```
git clone https://github.com/karlstadskommun/caia.git caia
cd caia/next
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

**Try the interface without model calls.** The development server answers every step with saved example output, so nothing costs anything:

```
CAIA_KOMMUN=exempel CAIA_DEV_OPEN=1 CAIA_INSECURE_COOKIE=1 .venv/bin/python tools/devserver.py
```

Open http://127.0.0.1:5055. If the page shows a login box, your shell has `SUPABASE_URL` set from before: remove it (`unset SUPABASE_URL`) and start again.

**Run a real analysis.** Requires an API key from [OpenRouter](https://openrouter.ai). An analysis costs a few US dollars (2 to 4 USD in autumn 2026) and takes 10 to 15 minutes:

```
cp .env.example .env        # fill in OPENROUTER_API_KEY, leave CAIA_KOMMUN=exempel
echo 'CAIA_DEV_OPEN=1' >> .env
set -a; . ./.env; set +a
PYTHONPATH=src .venv/bin/flask --app caia.web.app run --port 5000
```

Open http://127.0.0.1:5000. `CAIA_DEV_OPEN=1` turns off login and must only be used on your own computer.

The same analysis without a browser, on one of the reference packages:

```
.venv/bin/python tools/run_batch.py tests/reference/02-aterbruk.md --out /tmp/caia-run --env .env
```

## Set up for a municipality

- **Own server** (Linux, gunicorn, nginx): [next/INSTALL.md](next/INSTALL.md).
- **Vercel**: [next/DEPLOY.md](next/DEPLOY.md).
- **A new municipality profile**: copy `next/src/caia/kommuner/exempel/`, fill it in, and point CAIA at it with `CAIA_KOMMUN` or `CAIA_KOMMUN_DIR`. INSTALL.md step 2, and the data file formats in [docs/DATAFORMAT.md](docs/DATAFORMAT.md).

Before an installation is opened to staff: the text users write is sent to a language model provider outside the municipality (via OpenRouter; with `CAIA_OPENROUTER_REGION=eu` it stays with providers in the EU). Tell users not to write personal data, as the user guide does.

## Documentation (Swedish)

- [docs/METOD.md](docs/METOD.md): what CAIA calculates and what it does not, the formulas, source marking and known limitations. For reviewers who do not read code.
- [docs/ANVANDARGUIDE.md](docs/ANVANDARGUIDE.md): a first analysis and how to read the report. For municipal staff.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): modules, data flow, external services and what they cost.
- [docs/API.md](docs/API.md): every endpoint with input, output, errors and cost. For integrators.
- [docs/RUNBOOK.md](docs/RUNBOOK.md): operations, deploy, rollback, keys, logs, limits, changing a prompt.
- [docs/DECISIONS.md](docs/DECISIONS.md): the main design decisions and why.
- [docs/DATAFORMAT.md](docs/DATAFORMAT.md): the municipality's data files.
- [docs/security-review-2026-10.md](docs/security-review-2026-10.md): summary of the security review of October 2026.

## Known limitations

The method's limitations, with the measured spread between runs, are in [docs/METOD.md](docs/METOD.md#kända-begränsningar). The most important:

- **The language model sets the assumptions.** The calculation is deterministic, but its inputs (shares, factors, time frames) are produced by Claude from the user's description, the parameter library and the municipality's data. Two runs of the same action do not give exactly the same numbers. Every assumption is shown and can be corrected at approval.
- **The sign can come out wrong for actions that avoid emissions.** A positive number is a reduction. An action such as reuse can be modelled by the language model as increased activity and get a minus. The calculation then warns of increased emissions, and the quality review points out the error. Such a result should not be used until the assumption is corrected.
- **The average per year covers 2026 to 2030**, whatever the target year. An action that takes effect late in those years gets a low number, and one that takes effect only afterwards gets zero. The calculation warns in both cases.
- **If CAIA's own calculation cannot read the model's numbers**, the language model calculates instead. The result is then marked `deterministic: false`, and the report says so.
- **An analysis takes 10 to 15 minutes**, each step up to just under five. If the user cancels in the middle of a step, the call continues on the server and is still paid for.
- **Rate limits are counted per server process.** On Vercel each instance has its own counter. That stops a looping client, not a determined abuser; the hard limit is the credit limit on the OpenRouter key.
- **The API has no versioning yet**, beyond the release numbers in [CHANGELOG.md](CHANGELOG.md).
- **Open items from the handover review (September 2026):** the calculation input is not compared automatically with every approved assumption; the extraction takes the first JSON candidate in a model answer; the page has no Content-Security-Policy and loads fonts and libraries from Google and jsDelivr; a parameter library row without a closing pipe shifts its columns; the spread between runs is not shown to the user.

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), not in a public issue.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Contact

henric.barkman@karlstad.se
