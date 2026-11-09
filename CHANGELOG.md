# Changelog

Every release of CAIA is recorded here, newest first. Version numbers follow [Semantic Versioning](https://semver.org/): a change to the HTTP API in [docs/API.md](docs/API.md) that can break an existing client is a new major version, a new feature a new minor version, and a fix a new patch version. A change that moves the numbers an analysis gives (a prompt, the calculation, a parameter library) is described in its own line, whatever the version step.

## [1.0.1] - 2026-11-09

Documentation, comments, two lines the batch tool prints and a citation file. No prompt, calculation, parameter or data file changed, so no analysis gives a different number.

- The README says who brought CAIA about and how the code was written, and a `CITATION.cff` gives the repository GitHub's *Cite this repository* button.
- The README says plainly that model calls go through the installer's own OpenRouter account, may reach providers outside the EU by default, and what it takes to keep them in the EU. What the docs say about Karlstad's installation describes Karlstad's settings.

- The docs no longer contradict each other: Vercel's time limit is 300 s everywhere, and a municipality in production needs a paid plan or its own server; the decision to stay in region iad1 is marked as replaced by arn1 and OpenRouter's EU entry (2026-10-08), and the provider behind the EU entry is named the same way everywhere; the start page does tell the user that text goes to an external provider; the follow-up mode has eighteen method rules, not twelve.
- The README's open items no longer list a missing Content-Security-Policy (the page has one) or a parameter-library row that shifts its columns (it does not), and point to what the comparison with the approved assumptions does not catch, which METOD.md now states as the code does it.
- INSTALL.md clones from the public repository; the deploy-key steps for a private repository are gone.
- The batch tools describe their key list neutrally: a list of Anthropic keys tried in order, OpenRouter last.
- Comments name no individuals, and DECISIONS.md names the client once, in its introduction: a decision gives its date and its reason.
- Operational notes that described one installation's shared login project are written generally.

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

CAIA was developed at Karlstads kommun from December 2025 and was called Zaid until October 2026. That history is internal and not public; this repository starts a new history.
