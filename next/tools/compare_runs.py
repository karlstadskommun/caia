"""Put two run_batch runs side by side, one line per package, or sum up the
spread over many runs of the same package.

Used when a prompt, the parameter library or a data file changes (see
docs/RUNBOOK.md, "Ändra en prompt"): run the reference packages before and
after, then

    python tools/compare_runs.py <before-dir> <after-dir>

The numbers are the calc's own (kalkyl_meta.json): net effect per year for
the med scenario and the min-max span. A run whose calc fell back to the
language model (deterministic=false) is marked, because its numbers are not
comparable with a deterministic one. Reading the reports is still the job;
this only shows where to start.

Spread over N runs of the same package (tools/replay_step.py, or N run_batch
runs of the same packages):

    python tools/compare_runs.py --spread <dir> [<dir> ...]

Every subdirectory with a kalkyl_meta.json is one run. Runs are grouped by
package: the directory name without a trailing -rN (replay_step names its
repeats <package>-r1, -r2, ...). Per package and per number (net, terr,
cons): min, median, max and max/min. max/min is left out when the smallest
value is zero or below, where a ratio says nothing. Runs whose calc fell back
to the language model are counted but not in the numbers.

A step's own answer over N runs, for a replay that stopped after the step
(replay_step.py --through <step>), or for whole runs side by side:

    python tools/compare_runs.py --step intake|emap|baslinje <dir> [<dir> ...] [--paket <namn>]

Time per request to the page, the evidens merge's answer length against its
cap, and USD per analysis, from run.log and usage.jsonl:

    python tools/compare_runs.py --tid <dir> [<dir> ...] [--paket <namn>]

What these read and how is in tools/step_readout.py. No model calls.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

NUMBERS = ('net', 'terr', 'cons')
_REPEAT = re.compile(r'-r\d+$')


def _meta(run: Path, package: str) -> dict | None:
    path = run / package / 'kalkyl_meta.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def _describe(meta: dict | None) -> str:
    if meta is None:
        return 'ingen kalkyl'
    head = meta.get('headline') or {}
    span = meta.get('span') or {}
    net = head.get('net')
    text = f"{net:>10.1f}" if isinstance(net, (int, float)) else f"{'-':>10}"
    if span:
        text += f"  ({span.get('net_lo')} till {span.get('net_hi')})"
    if meta.get('deterministic') is not True:
        text += '  SPRÅKMODELL'
    return text


def package_of(run_dir_name: str) -> str:
    """The package a run directory belongs to: its name without -rN."""
    return _REPEAT.sub('', run_dir_name)


def collect(dirs: list[Path]) -> dict[str, list[dict]]:
    """Every run's kalkyl_meta.json under `dirs`, by package. A directory
    that is itself a run (has kalkyl_meta.json) counts as one."""
    runs: dict[str, list[dict]] = {}
    for d in dirs:
        if (d / 'kalkyl_meta.json').is_file():
            candidates = [d]
        elif d.is_dir():
            candidates = sorted(p for p in d.iterdir() if p.is_dir())
        else:
            candidates = []
        for run in candidates:
            path = run / 'kalkyl_meta.json'
            if path.is_file():
                meta = json.loads(path.read_text(encoding='utf-8'))
                runs.setdefault(package_of(run.name), []).append(meta)
    return runs


def spread(metas: list[dict]) -> dict:
    """min, median, max and max/min per headline number over the runs whose
    calc was deterministic. `n` is every run, `llm` those left out."""
    det = [m for m in metas if m.get('deterministic') is True]
    out: dict = {'n': len(metas), 'llm': len(metas) - len(det)}
    for key in NUMBERS:
        vals = [(m.get('headline') or {}).get(key) for m in det]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if not vals:
            out[key] = None
            continue
        lo, hi = min(vals), max(vals)
        out[key] = {'n': len(vals), 'min': lo, 'median': statistics.median(vals), 'max': hi,
                    'ratio': hi / lo if lo > 0 else None}
    return out


def format_spread(runs: dict[str, list[dict]]) -> str:
    head = f"{'paket':30} {'mått':5} {'n':>3} {'min':>9} {'median':>9} {'max':>9} {'max/min':>8}"
    lines = ['Spridning, ton CO2e/år (huvudsiffran ur kalkyl_meta.json):', head]
    for package in sorted(runs):
        s = spread(runs[package])
        name = package
        for key in NUMBERS:
            st = s[key]
            if st is None:
                lines.append(f"{name[:30]:30} {key:5} {0:3d} {'-':>9} {'-':>9} {'-':>9} {'-':>8}")
            else:
                ratio = f"{st['ratio']:8.2f}" if st['ratio'] is not None else f"{'-':>8}"
                lines.append(f"{name[:30]:30} {key:5} {st['n']:3d} {st['min']:9.1f} "
                             f"{st['median']:9.1f} {st['max']:9.1f} {ratio}")
            name = ''
        if s['llm']:
            lines.append(f"{'':30} {s['llm']} av {s['n']} körningar räknades av språkmodellen "
                         "och står inte med.")
    return '\n'.join(lines)


def _paket(args: list[str]) -> tuple[list[str], str | None]:
    if '--paket' in args:
        i = args.index('--paket')
        if i + 1 < len(args):
            return args[:i] + args[i + 2:], args[i + 1]
    return args, None


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[1] == '--step':
        import step_readout
        step = argv[2]
        if step not in step_readout.READOUTS:
            print(f"--step tar {', '.join(step_readout.READOUTS)}, inte {step!r}.")
            return 2
        dirs, paket = _paket(argv[3:])
        text = step_readout.step_readout(step, [Path(a) for a in dirs], paket)
        if text is None:
            print(f'Inga körningar med {step_readout.READOUTS[step][0]} hittades.')
            return 1
        print(text)
        return 0
    if len(argv) >= 3 and argv[1] == '--tid':
        import step_readout
        dirs, paket = _paket(argv[2:])
        text = step_readout.time_readout([Path(a) for a in dirs], paket)
        if text is None:
            print('Inga analyser (kataloger med history.json) hittades.')
            return 1
        print(text)
        return 0
    if len(argv) >= 3 and argv[1] == '--spread':
        runs = collect([Path(a) for a in argv[2:]])
        if not runs:
            print('Inga körningar med kalkyl_meta.json hittades.')
            return 1
        print(format_spread(runs))
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    before, after = Path(argv[1]), Path(argv[2])
    packages = sorted({p.name for d in (before, after) if d.is_dir() for p in d.iterdir() if p.is_dir()})
    if not packages:
        print('Inga körningar hittades.')
        return 1
    print(f"{'paket':34} {'före (ton CO2e/år, netto)':42} efter")
    for name in packages:
        print(f"{name:34} {_describe(_meta(before, name)):42} {_describe(_meta(after, name))}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
