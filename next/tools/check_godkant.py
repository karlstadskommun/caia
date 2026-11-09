"""Run the S21 comparison (caia.godkant) against saved runs.

    python tools/check_godkant.py <run-dir>... [--power]

A run is a directory run_batch wrote (or any directory below one) with a
history.json and a kalkyl.md. The inputs the engine ran on are read back
from the kalkyl step's "Indata per drivare" lines, the history up to the
kalkyl step is what the extraction saw. Runs are deduplicated on their
content, so a directory copied twice counts once.

Without --power: every number the comparison marks, per run. Each one is a
false warning or a misreading of the extraction; read the extraction's own
note (kallor) in the run to tell which. With --power: change one number in
one driver at a time and count how often the comparison catches it.

Used when godkant.py, the extraction prompt or the step prompts change
(docs/RUNBOOK.md). The measurement of 2026-10-09 is in
docs/security-review-2026-10.md, S21.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from caia import godkant  # noqa: E402
from caia.calc.schema import Triple  # noqa: E402
from caia.pipeline import BRIDGE  # noqa: E402

NUM = r"-?\d[\d ]*(?:,\d+)?"
LINE = re.compile(
    rf"^  - (?P<name>.+?): A0 (?P<a0>{NUM}) ?(?P<a0u>.*?), EF0 (?P<ef0>{NUM}) ?(?P<ef0u>[^;]*); "
    rf"ΔA (?P<da>.+?), ΔEF (?P<def>.+?); "
    rf"(?:BAU-trend A (?P<ga>.+?)/år, EF (?P<gef>.+?)/år; )?"
    rf"klimatfaktorer territoriell (?P<terr>{NUM}), konsumtion (?P<cons>{NUM}), "
    rf"överlapp (?P<ov>{NUM}); (?P<rest>.*)$")
FIELDS = ("a0", "ef0", "g_a", "g_ef", "delta_a", "delta_ef", "attribution",
          "terr", "cons", "overlap")


def _num(s: str) -> float:
    return float(s.strip().replace(" ", "").replace(",", "."))


def _band(s: str):
    """'-92 % (-75 till -100)' or '0 %' -> (min, med, max) as shares."""
    m = re.match(rf"^({NUM}) %(?: \(({NUM}) till ({NUM})\))?", s.strip())
    if not m:
        return None
    med = _num(m.group(1)) / 100
    if m.group(2) is None:
        return (med, med, med)
    return (_num(m.group(2)) / 100, med, _num(m.group(3)) / 100)


def indata(kalkyl: str) -> list[dict] | None:
    """The drivers of the kalkyl step's 'Indata per drivare' list."""
    if "Indata per drivare" not in kalkyl:
        return None
    out = []
    for line in kalkyl.split("Indata per drivare", 1)[1].splitlines()[1:]:
        if not line.startswith("  - "):
            if out:
                break
            continue
        m = LINE.match(line)
        if not m:
            continue
        d = {"name": m["name"], "a0": _num(m["a0"]), "a0_unit": m["a0u"].strip(),
             "ef0": _num(m["ef0"]), "ef0_unit": m["ef0u"].strip(),
             "delta_a": _band(m["da"]), "delta_ef": _band(m["def"]),
             "g_a": _band(m["ga"]) if m["ga"] else (0, 0, 0),
             "g_ef": _band(m["gef"]) if m["gef"] else (0, 0, 0),
             "terr": _num(m["terr"]), "cons": _num(m["cons"]), "overlap": _num(m["ov"])}
        am = re.search(r"attribution (.+?)(?:;|$)", m["rest"])
        d["attribution"] = _band(am.group(1)) if am else (1, 1, 1)
        if None not in (d["delta_a"], d["delta_ef"], d["g_a"], d["g_ef"], d["attribution"]):
            out.append(d)
    return out


def load(dirs: list[str]) -> list[dict]:
    runs, seen = [], set()
    for top in dirs:
        for h in sorted(Path(top).rglob("history.json")):
            kal_file = h.parent / "kalkyl.md"
            hist = json.loads(h.read_text(encoding="utf-8"))
            # The history up to the kalkyl step: what the extraction saw.
            cut = next((i + 1 for i in range(len(hist) - 1, -1, -1)
                        if hist[i].get("role") == "user"
                        and str(hist[i].get("content", "")).strip() == BRIDGE["evidens"]), None)
            if cut is None:
                continue
            kal = (hist[cut]["content"] if cut < len(hist) and hist[cut].get("role") == "assistant"
                   else kal_file.read_text(encoding="utf-8") if kal_file.is_file() else "")
            drivers = indata(kal)
            if not drivers:
                continue
            key = hashlib.sha1(json.dumps([hist[:cut], kal], ensure_ascii=False).encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                runs.append({"path": str(h.parent), "history": hist[:cut], "drivers": drivers})
    return runs


def model_of(drivers: list[dict]):
    ds = []
    for d in drivers:
        kw = {f: Triple(*d[f]) if isinstance(d[f], (list, tuple)) else float(d[f]) for f in FIELDS}
        ds.append(SimpleNamespace(name=d["name"], a0_unit=d["a0_unit"], ef0_unit=d["ef0_unit"], **kw))
    return SimpleNamespace(drivers=ds)


def marks(runs: list[dict]) -> int:
    total = 0
    for r in runs:
        for a in godkant.granska(model_of(r["drivers"]), r["history"]):
            total += 1
            print(f"  {r['path']}: {a.drivare[:50]} {a.falt} {a.scenario} {a.varde:g}: {a.problem}")
    return total


def power(runs: list[dict]) -> None:
    for label, fields, change in (
        ("a0 x10", ("a0",), lambda x: x * 10),
        ("ef0 x10", ("ef0",), lambda x: x * 10),
        ("effekt medel x2,21", ("delta_a", "delta_ef"), lambda x: x * 2.21),
        ("effekt medel x1,5", ("delta_a", "delta_ef"), lambda x: x * 1.5),
        ("effekt medel x0,5", ("delta_a", "delta_ef"), lambda x: x * 0.5),
        ("effekt medel x10", ("delta_a", "delta_ef"), lambda x: x * 10),
        ("effekt medel := max", ("delta_a", "delta_ef"), "max"),
        ("effekt alla tre x2,21", ("delta_a", "delta_ef"), "all"),
        ("effekt nollad", ("delta_a",), "zero"),
        ("territoriell 0,05 <-> 1", ("terr",), lambda x: 1.0 if x < 0.5 else 0.05),
        ("konsumtion -0,2", ("cons",), lambda x: max(0.0, x - 0.2)),
    ):
        tried = caught = 0
        for r in runs:
            before = {(a.drivare, a.falt, a.scenario)
                      for a in godkant.granska(model_of(r["drivers"]), r["history"])}
            for i, d in enumerate(r["drivers"]):
                for f in fields:
                    v = d[f]
                    if change == "zero":
                        if not any(d["delta_a"]) and not any(d["delta_ef"]):
                            continue
                        dd = [dict(x) for x in r["drivers"]]
                        dd[i]["delta_a"] = dd[i]["delta_ef"] = (0.0, 0.0, 0.0)
                        got = godkant.granska(model_of(dd), r["history"])
                        tried += 1
                        caught += any(a.drivare == d["name"] and a.falt in ("delta_a", "delta_ef")
                                      and (a.drivare, a.falt, a.scenario) not in before
                                      for a in got)
                        continue
                    if isinstance(v, (list, tuple)):
                        if not v[1]:
                            continue
                        new = list(v)
                        if change == "all":
                            new = [x * 2.21 for x in v]
                        elif change == "max":
                            if abs(v[2] - v[1]) / abs(v[1]) < 0.05:
                                continue
                            new[1] = v[2]
                        else:
                            new[1] = change(v[1])
                        sc = "med"
                    else:
                        if not v and f not in ("terr", "cons", "overlap"):
                            continue
                        new, sc = change(v), ""
                    dd = [dict(x) for x in r["drivers"]]
                    dd[i][f] = new
                    got = godkant.granska(model_of(dd), r["history"])
                    tried += 1
                    caught += any((a.drivare, a.falt, a.scenario) == (d["name"], f, sc)
                                  and (a.drivare, a.falt, a.scenario) not in before for a in got)
        print(f"  {label:24} {caught:3} av {tried}")


def main(argv: list[str]) -> int:
    dirs = [a for a in argv if not a.startswith("--")]
    if not dirs:
        print(__doc__)
        return 2
    runs = load(dirs)
    n = marks(runs)
    print(f"{len(runs)} körningar, {sum(len(r['drivers']) for r in runs)} drivare: {n} markerade tal")
    if "--power" in argv:
        power(runs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
