# Security policy

## Reporting a vulnerability

Please do not report security problems in a public issue. Send them to **henric.barkman@karlstad.se**. You will hear back within five working days.

Please include:

- what the problem is and where (file, endpoint or setting),
- how to reproduce it,
- what an attacker could do with it,
- whether you have told anyone else.

Write in Swedish or English. Do not send personal data or other people's credentials, even as proof.

## What is covered

The code and documentation in this repository. A municipality's own installation of CAIA is that municipality's responsibility: report a problem with a particular installation to the municipality that runs it. Problems in the services CAIA uses (OpenRouter, Supabase, Vercel, the language model providers) go to those services.

Security fixes are made in the latest release.

## What an installation is responsible for

Several protections depend on how CAIA is set up, not on the code. [next/INSTALL.md](next/INSTALL.md) and [next/DEPLOY.md](next/DEPLOY.md) describe the setup, and the summary of the October 2026 security review, [docs/security-review-2026-10.md](docs/security-review-2026-10.md), lists what a new installation must do itself. It also lists the two findings that were accepted as risks rather than fixed.

## Svenska

Rapportera inte säkerhetsbrister i ett öppet ärende. Skicka dem till **henric.barkman@karlstad.se**, så hör vi av oss inom fem arbetsdagar. Beskriv vad problemet är och var, hur det kan återskapas, vad en angripare kan göra med det och om du har berättat för någon annan. Skicka inga personuppgifter eller andras inloggningsuppgifter, inte heller som bevis.

Policyn gäller koden och dokumentationen i det här repot. En kommuns egen installation av CAIA är den kommunens ansvar. Vad en installation själv måste göra står i sammanfattningen av säkerhetsgranskningen, [docs/security-review-2026-10.md](docs/security-review-2026-10.md).
