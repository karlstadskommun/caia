# Contributing to CAIA

Karlstads kommun takes issues but not pull requests for now. Contributions are reviewed by CAIA's maintainers at Karlstads kommun.

Write in Swedish or English. Security problems go to [SECURITY.md](SECURITY.md), not to an issue.

## Licence of contributions

CAIA is licensed under the EUPL-1.2. By submitting a contribution you confirm that you have the right to do so, and you agree that it is licensed under the EUPL-1.2 like the rest of the project.

## Before you open a pull request

- **Run the tests** from `next/`: `.venv/bin/python -m pytest -q`. They must pass. Tests marked `karlstad` are skipped in this repository; that is expected.
- **A change to what the language model is told** (a system prompt in `next/src/caia/agents/`, a parameter library or a data file) makes `tests/test_prompt_fingerprints.py` fail. That is deliberate: no unit test catches a changed sentence in a prompt. Such a change has to be tried on the reference packages before and after, which costs money in model calls ([docs/RUNBOOK.md](docs/RUNBOOK.md), "Ändra en prompt"). Describe in the pull request what the change is meant to do; the maintainers run the reference packages and record the new fingerprints.
- **A change to the calculation** (`next/src/caia/calc/`, `kallmarkering.py`, `agents/uppfoljning.py`) updates [docs/METOD.md](docs/METOD.md) in the same pull request. A change to the page's gates, buttons or headings updates [docs/ANVANDARGUIDE.md](docs/ANVANDARGUIDE.md).
- **A method decision** (how something is calculated, what a result counts, what the user must confirm) gets an entry in [docs/DECISIONS.md](docs/DECISIONS.md): the date, the decision, why, and what was rejected.
- **No personal data** in issues, test fixtures or example packages.
- **Add a line to [CHANGELOG.md](CHANGELOG.md)** under *Unreleased*.

## Svenska

Karlstads kommun tar emot ärenden men inte pull requests just nu. Bidragen granskas av CAIA:s förvaltare på Karlstads kommun. Skriv på svenska eller engelska.

Ett bidrag licensieras under EUPL-1.2 som resten av projektet, och den som skickar det intygar att hen har rätt att göra det. Testerna ska gå igenom (`cd next && .venv/bin/python -m pytest -q`). En ändring i det språkmodellen får veta (prompter, parameterbibliotek, datafiler) fäller fingeravtryckstestet med flit och prövas av förvaltarna på referenspaketen enligt RUNBOOK. Ändras beräkningen ändras METOD.md i samma pull request, och ett metodbeslut skrivs i DECISIONS.md. Inga personuppgifter i ärenden eller testdata.
