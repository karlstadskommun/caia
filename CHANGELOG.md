# Changelog

Every release of CAIA is recorded here, newest first. Version numbers follow [Semantic Versioning](https://semver.org/): a change to the HTTP API in [docs/API.md](docs/API.md) that can break an existing client is a new major version, a new feature a new minor version, and a fix a new patch version. A change that moves the numbers an analysis gives (a prompt, the calculation, a parameter library) is described in its own line, whatever the version step.

## Unreleased

## [1.0.0] - 2026-11-09

The first public release.

- The web app and the seven-step pipeline: action profile, emission sources, baseline, evidence per driver, calculation, quality review and report. The first four steps are approved or corrected by the user.
- Two analysis modes: forecast (potentialläge) and follow-up of an intervention already made (uppföljningsläge).
- A deterministic calculation in Python (`caia.calc`) with three scenarios, phasing, attribution, territorial and consumption-based emissions, and warnings when the input does not hold together.
- Source marking: every number the calculation rests on carries its origin, checked against the parameter library and data files, and the report shows it under *Talens ursprung*.
- A comparison of the numbers the calculation used with the assumptions the user approved.
- Several actions counted together per emission pot (portfolio), so that the same tonnes are not counted twice.
- The report in three layers on the page, and the HTTP API the page uses ([docs/API.md](docs/API.md)).
- Municipality profiles, with `exempel` as the template for a new municipality.
- Login with Supabase or a shared password, rate limits per user, and the measures from the security review of October 2026.

CAIA was developed at Karlstads kommun from December 2025 and was called Zaid until October 2026. That history is kept in the municipality's internal repository; this repository starts a new history.
