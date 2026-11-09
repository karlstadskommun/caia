"""Kommunprofil: everything that makes an installation Karlstad, or another kommun.

A municipality switches profile; it does not edit code. A profile is a folder:

    kommuner/<slug>/
        kommun.toml             name, place, county, plan, local context text
        parameters_library.md   the parameter library, incl. the section-12
                                register that names the data files
        data/                   the municipality's own data files

Selection, in order:
    CAIA_KOMMUN_DIR   path to a profile folder anywhere on disk (lets an
                      installation keep its profile outside the repo, so a
                      `git pull` of new code never touches it)
    CAIA_KOMMUN       slug of a profile bundled under src/caia/kommuner/
    (neither)         an error. There is no default: another kommun's install that
                      forgot the variable used to come up as Karlstad, with
                      Karlstad's data and plan in every answer, and nothing
                      on screen said so.

Everything municipality-specific that an agent, the data layer or the web page
says comes from here. `tests/test_kommunprofil.py` runs the whole pipeline on
the bundled "exempel" profile and fails if the word Karlstad reaches a model
or the page outside the one origin line (the software is Karlstad's).

Run `python -m caia.kommun` to check the active profile.
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

BUNDLED_DIR = Path(__file__).parent / "kommuner"

# Placeholders in the agent prompts. `@@` never occurs in the prompts
# otherwise, and a token that survives rendering is refused by
# api_client.complete before it reaches a model.
_TOKENS = {
    "@@KOMMUN@@": "namn",
    "@@ORT@@": "ort",
    "@@PLAN@@": "plan",
    "@@LOKAL_KONTEXT@@": "lokal_kontext",
}
UNRENDERED = re.compile(r"@@[A-Z_]+@@")

_REQUIRED = ("namn", "ort", "lan", "plan", "lokal_kontext")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class KommunProfilError(RuntimeError):
    """The profile is missing or incomplete. The message says what to fix."""


@dataclass(frozen=True)
class Kommun:
    slug: str
    namn: str            # "Karlstads kommun"
    ort: str             # "Karlstad"; also the column name in the consumption export
    lan: str             # "Värmlands län", as written in the national emissions export
    plan: str            # "Karlstads energi- och klimatplan"
    lokal_kontext: str   # the paragraph the agents get about the municipality
    root: Path

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def parameters_file(self) -> Path:
        return self.root / "parameters_library.md"

    @property
    def potter_file(self) -> Path:
        """The register of emission pots the portfolio counts on. Optional:
        without it every action in a portfolio counts on its own."""
        return self.root / "potter.toml"

    def render(self, template: str) -> str:
        """Fill the @@...@@ placeholders in an agent prompt."""
        out = template
        for token, attr in _TOKENS.items():
            out = out.replace(token, getattr(self, attr))
        left = UNRENDERED.search(out)
        if left:
            raise KommunProfilError(f"okänd platshållare {left.group(0)} i en prompt")
        return out

    def public(self) -> dict:
        """What the web page may know about the profile."""
        return {"slug": self.slug, "namn": self.namn, "ort": self.ort, "plan": self.plan}


def load(root: Path) -> Kommun:
    """Read and validate one profile folder."""
    root = Path(root)
    toml_path = root / "kommun.toml"
    if not toml_path.is_file():
        raise KommunProfilError(f"{toml_path} saknas. En kommunprofil är en mapp med kommun.toml, "
                                "parameters_library.md och data/.")
    try:
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise KommunProfilError(f"{toml_path} går inte att läsa: {e}") from e
    missing = [k for k in _REQUIRED if not str(raw.get(k, "")).strip()]
    if missing:
        raise KommunProfilError(f"{toml_path} saknar {', '.join(missing)}")
    wrong_type = [k for k in _REQUIRED if not isinstance(raw[k], str)]
    if wrong_type:
        raise KommunProfilError(f"{toml_path}: {', '.join(wrong_type)} ska vara text")
    if not (root / "parameters_library.md").is_file():
        raise KommunProfilError(f"{root / 'parameters_library.md'} saknas")
    return Kommun(
        slug=str(raw.get("slug") or root.name),
        namn=raw["namn"].strip(),
        ort=raw["ort"].strip(),
        lan=raw["lan"].strip(),
        plan=raw["plan"].strip(),
        lokal_kontext=raw["lokal_kontext"].strip(),
        root=root,
    )


def bundled(slug: str) -> Kommun:
    """A profile shipped in src/caia/kommuner/."""
    if not _SLUG.match(slug or ""):
        raise KommunProfilError(f"CAIA_KOMMUN={slug!r} är inget giltigt profilnamn "
                                "(små bokstäver, siffror, - och _)")
    root = BUNDLED_DIR / slug
    if not root.is_dir():
        raise KommunProfilError(f"Kommunprofilen {slug!r} finns inte i {BUNDLED_DIR} "
                                f"(finns: {_bundled_slugs()})")
    return load(root)


def _bundled_slugs() -> str:
    return ", ".join(sorted(p.name for p in BUNDLED_DIR.iterdir() if p.is_dir()))


def from_env() -> Kommun:
    path = os.environ.get("CAIA_KOMMUN_DIR", "").strip()
    if path:
        return load(Path(path))
    slug = os.environ.get("CAIA_KOMMUN", "").strip()
    if not slug:
        raise KommunProfilError(
            "Ingen kommunprofil vald. Sätt CAIA_KOMMUN till en av de medföljande "
            f"profilerna ({_bundled_slugs()}), eller CAIA_KOMMUN_DIR till en egen "
            "profilmapp. Se INSTALL.md, avsnittet om kommunprofilen.")
    return bundled(slug)


_active: Kommun | None = None


def active() -> Kommun:
    """The profile this process runs with. Read once from the environment."""
    global _active
    if _active is None:
        _active = from_env()
    return _active


def set_active(kommun: Kommun | None) -> None:
    """Switch profile in-process (tests, batch tools). None = re-read the env."""
    global _active
    _active = kommun


def _report(k: Kommun) -> str:
    # Imported here: the data layer imports this module.
    from caia.data.parameters import get_data_context, parse_file_register, parse_parameter_library

    rows = [r for s in parse_parameter_library() for r in s["rows"]]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["provenance"]] = counts.get(r["provenance"], 0) + 1
    lines = [
        f"Kommunprofil: {k.slug}  ({k.root})",
        f"  namn: {k.namn}",
        f"  ort:  {k.ort}",
        f"  län:  {k.lan}",
        f"  plan: {k.plan}",
        f"Parameterbibliotek: {len(rows)} parametrar, "
        f"{counts.get('lokal', 0)} lokala, {counts.get('datafil', 0)} ur datafil, "
        f"{counts.get('schablon', 0)} schabloner",
        "Datafiler (register i parameterbibliotekets sektion 12):",
    ]
    for name, entry in parse_file_register().items():
        if not entry["read"]:
            mark = "läses ej"
        else:
            mark = "finns" if entry["exists"] else "saknas"
        lines.append(f"  {name:28} {mark:8} {entry['filename']}")
    ctx = get_data_context()
    lines.append(f"Datakontext till agenterna: {len(ctx)} tecken")
    from caia.calc.portfolj import load_potter
    potter = load_potter(k.potter_file)
    lines.append(f"Utsläppspotter för portföljen ({k.potter_file.name}): {len(potter) or 'inga'}")
    for p in potter:
        lines.append(f"  {p.id:20} {p.baslinje:>10,.0f} t/år {p.ar}  {p.namn}".replace(",", " "))
    return "\n".join(lines)


if __name__ == "__main__":
    # `python -m` runs this file as __main__, a second copy of the module. Go
    # through the imported one so the report and the data layer share a profile.
    from caia import kommun as _k
    try:
        print(_report(_k.active()))
    except _k.KommunProfilError as e:
        print(f"FEL: {e}", file=sys.stderr)
        sys.exit(1)
