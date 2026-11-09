"""Run one step of a saved analysis again, N times, on exactly the same input.

Answers "which step makes two runs of the same measure differ?". Everything
before the step is held fixed: the conversation is taken from the saved
analysis's history.json, cut just before the step, and every repeat starts
from that same cut. The step then runs N times, and after it the rest of the
chain to and including kalkyl, so every repeat ends in a headline number
(kalkyl_meta.json). The spread of those N numbers is what that step adds.

    CAIA_KOMMUN=<profil> python tools/replay_step.py <analysis-dir> <step> --n 5 --out <dir> \\
        --env /path/to/.env [--parallel 3] [--through kalkyl]

<analysis-dir> is one package's directory from tools/run_batch.py (or an
earlier replay): it needs history.json. <step> is one of intake, emap,
baslinje, evidens, kalkyl, qa, rapport. The steps run through run_batch's
own functions (run_intake, run_steps, post_evidens_split) against the app's
routes, so a repeat makes the same calls the page and run_batch make.

Rerunning intake answers its clarifying questions with the answer the saved
analysis gave (the first user turn after the intake's first question); a
saved intake that never asked anything gets run_batch's generic answer, and
--answer overrides both.

Output, per repeat <out>/<name>-rN/: the files of the steps before the cut,
copied from the saved analysis; the files of the steps that ran (<step>.md,
kalkyl_meta.json); history.json (the cut, then the new turns); usage.jsonl
(one line per model call). In <out>: replay.json (what was replayed, from
where, and a hash of the cut), summary.jsonl (per repeat: net, terr, cons,
cost), run.log, and at the end the spread (tools/compare_runs.py --spread)
and the cost per step.

Costs real model calls: the step and everything after it to kalkyl, per
repeat. Before it starts it prints an estimate from the saved analysis's
own usage.jsonl when there is one; --estimate prints only that and stops.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_batch  # noqa: E402  (puts src on the path)
from caia import api_client  # noqa: E402
from caia.mode import MODES, POTENTIAL  # noqa: E402
from caia.pipeline import BRIDGE, STEPS  # noqa: E402
from compare_runs import collect, format_spread  # noqa: E402

LAST = "kalkyl"  # the chain runs at least this far: it is where the headline is


def pipeline_step_of(usage_step: str | None) -> str:
    """The pipeline step a usage record belongs to: evidens_part and
    evidens_merge are evidens, kalkyl_extract is kalkyl."""
    return (usage_step or "?").split("_")[0]


def cut_before(history: list[dict], step: str) -> list[dict]:
    """The conversation as the step saw it: everything up to and including
    the bridge line that hands over to it. For intake, the measure text."""
    if step not in STEPS:
        raise ValueError(f"okänt steg {step!r}; ett av {', '.join(STEPS)}")
    if not history or history[0].get("role") != "user":
        raise ValueError("historiken börjar inte med åtgärdstexten")
    if step == "intake":
        return history[:1]
    line = BRIDGE[STEPS[STEPS.index(step) - 1]]
    at = [i for i, m in enumerate(history)
          if m.get("role") == "user" and (m.get("content") or "").strip() == line]
    if not at:
        raise ValueError(f"analysen kom aldrig fram till {step}: raden {line!r} saknas")
    return history[: at[-1] + 1]


def intake_answer(history: list[dict]) -> str | None:
    """The answer the saved analysis gave the intake's questions, if it asked."""
    for m in history[2:]:
        if m.get("role") != "user":
            continue
        text = m.get("content") or ""
        return None if text.strip() == BRIDGE["intake"] else text
    return None


def steps_to_run(step: str, through: str) -> list[str]:
    """The steps after the cut, intake excluded (run_intake drives it)."""
    first, last = STEPS.index(step), STEPS.index(through)
    if last < first:
        raise ValueError(f"--through {through} ligger före {step}")
    return [s for s in STEPS[first: last + 1] if s != "intake"]


def estimate(run_dir: Path, steps: set[str]) -> float | None:
    """What the steps cost in the saved analysis, from its usage.jsonl. None
    when it has no calls of those steps (no file, or the analysis is itself a
    replay that started later): an estimate of 0 would read as free."""
    path = run_dir / "usage.jsonl"
    if not path.is_file():
        return None
    usd, found = 0.0, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if pipeline_step_of(rec.get("step")) in steps:
                usd += rec.get("usd") or 0
                found = True
    return usd if found else None


def replay(app, run_dir: Path, step: str, n: int, out: Path, *, through: str = LAST,
           mode: str = POTENTIAL, evidens_mode: str = "split", parallel: int = 1,
           name: str | None = None, answer: str | None = None) -> list[dict]:
    """Run `step` of the analysis in `run_dir` `n` times from the same cut,
    each time on through `through`. Returns one summary row per repeat."""
    source = json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
    prefix = cut_before(source, step)
    later = steps_to_run(step, through)
    name = name or run_dir.name
    if step == "intake" and answer is None:
        answer = intake_answer(source) or run_batch.GENERIC_ANSWER
    kallmarkering_md = None
    if STEPS.index(step) > STEPS.index("kalkyl"):
        meta = run_dir / "kalkyl_meta.json"
        if meta.is_file():
            kallmarkering_md = json.loads(meta.read_text(encoding="utf-8")).get("kallmarkering_md")
    before = list(STEPS[: STEPS.index(step)])
    ran = set(later) | ({"intake"} if step == "intake" else set())

    # Every repeat directory is emptied before it runs, so none may be the
    # analysis being replayed (an earlier repeat replayed into the same --out).
    if any((out / f"{name}-r{i}").resolve() == run_dir.resolve() for i in range(1, n + 1)):
        raise ValueError(f"{run_dir} skulle skrivas över: välj en annan --out eller --name")
    out.mkdir(parents=True, exist_ok=True)
    prefix_json = json.dumps(prefix, ensure_ascii=False, indent=2)
    (out / "replay.json").write_text(json.dumps({
        "source": str(run_dir.resolve()), "step": step, "through": through, "n": n,
        "mode": mode, "evidens": evidens_mode, "steps_run": sorted(ran, key=STEPS.index),
        "cut_turns": len(prefix),
        "cut_sha256": hashlib.sha256(prefix_json.encode("utf-8")).hexdigest(),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log = open(out / "run.log", "a", encoding="utf-8")
    meter = run_batch.UsageMeter()
    api_client.USAGE_LISTENERS.append(meter)

    def one(i: int) -> dict:
        label = f"{name}-r{i}"
        outdir = out / label
        outdir.mkdir(parents=True, exist_ok=True)
        # A repeat directory from an earlier replay into the same --out must
        # not lend this repeat its files: every file a repeat can hold goes,
        # then the steps before the cut are copied in.
        for f in [f"{s}.md" for s in STEPS] + ["kalkyl_meta.json", "history.json", "usage.jsonl"]:
            (outdir / f).unlink(missing_ok=True)
        for s in before:
            for f in (f"{s}.md", "kalkyl_meta.json" if s == "kalkyl" else None):
                if f and (run_dir / f).is_file():
                    shutil.copyfile(run_dir / f, outdir / f)
        say = run_batch.make_say(label, log)
        token = meter.start(label, outdir / "usage.jsonl")
        ok = False
        history = copy.deepcopy(prefix)
        try:
            client = app.test_client()
            ok = True
            if step == "intake":
                ok = run_batch.run_intake(client, history, answer, outdir, say, mode)
            if ok:
                ok = run_batch.run_steps(client, history, later, outdir, say, evidens_mode,
                                         mode, kallmarkering_md=kallmarkering_md)
            if ok:
                run_batch.write_history(outdir, history)
        except Exception as e:  # noqa: BLE001  one repeat's crash must not take the others
            say(f"avbröts: {e!r}")
            run_batch.write_history(outdir, history)
            ok = False
        finally:
            run_batch._PACKAGE.reset(token)
        return _row(i, label, outdir, ok, meter, step)

    pool = ThreadPoolExecutor(max_workers=max(1, parallel))
    try:
        futures = [pool.submit(one, i) for i in range(1, n + 1)]
        rows = [f.result() for f in futures]
    except BaseException:
        # Ctrl-C: the repeats not yet started must not start (each one is
        # paid for); those running finish their current call.
        pool.shutdown(wait=False, cancel_futures=True)
        api_client.USAGE_LISTENERS.remove(meter)
        log.close()
        raise
    pool.shutdown()
    api_client.USAGE_LISTENERS.remove(meter)
    with (out / "summary.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # The spread of this replay only: --out may hold repeats of an earlier
    # one, and a repeat that failed after kalkyl has no number of its own.
    done = collect([out / r["dir"] for r in rows if r["ok"]])
    spread_text = format_spread(done) if done else "Spridning: ingen omkörning blev klar."
    text = "\n\n".join([format_rows(rows, step), spread_text,
                        run_batch.summarize_usage(meter.records)])
    print("\n" + text)
    log.write(text + "\n")
    log.close()
    return rows


def _row(i: int, label: str, outdir: Path, ok: bool, meter: run_batch.UsageMeter,
         step: str) -> dict:
    recs = [r for r in meter.records if r.get("package") == label]
    meta_path = outdir / "kalkyl_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if ok and meta_path.is_file() else {}
    head = meta.get("headline") or {}
    return {
        "rerun": i, "dir": label, "ok": ok, "deterministic": meta.get("deterministic"),
        "net": head.get("net"), "terr": head.get("terr"), "cons": head.get("cons"),
        "year": head.get("year"),
        "usd": round(sum(r.get("usd") or 0 for r in recs), 4),
        "usd_step": round(sum(r.get("usd") or 0 for r in recs
                              if pipeline_step_of(r.get("step")) == step), 4),
        "calls": len(recs),
    }


def format_rows(rows: list[dict], step: str) -> str:
    def num(v):
        return f"{v:9.1f}" if isinstance(v, (int, float)) else f"{'-':>9}"
    lines = [f"Per omkörning av {step} (ton CO2e/år, kostnad i USD till listpris):",
             f"{'omkörning':24} {'net':>9} {'terr':>9} {'cons':>9} {'år':>5} "
             f"{step[:9]:>9} {'totalt':>8}"]
    for r in rows:
        flag = "" if r["ok"] else "  MISSLYCKADES"
        if r["ok"] and r["deterministic"] is not True:
            flag = "  SPRÅKMODELL"
        lines.append(f"{r['dir'][:24]:24} {num(r['net'])} {num(r['terr'])} {num(r['cons'])} "
                     f"{r['year'] or '-':>5} {r['usd_step']:9.2f} {r['usd']:8.2f}{flag}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="a saved analysis (directory with history.json)")
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--n", type=int, default=3, help="repeats (default 3)")
    ap.add_argument("--out", type=Path, default=None, help="required unless --estimate")
    ap.add_argument("--through", choices=STEPS, default=None,
                    help="last step to run (default kalkyl, or the step itself if later)")
    ap.add_argument("--mode", choices=MODES, default=POTENTIAL,
                    help="the mode the saved analysis ran in (default potential)")
    ap.add_argument("--evidens", choices=["split", "single"], default="split")
    ap.add_argument("--parallel", type=int, default=1, help="repeats at the same time")
    ap.add_argument("--name", default=None, help="prefix of the repeat directories")
    ap.add_argument("--answer", default=None, help="answer to the intake's questions")
    ap.add_argument("--estimate", action="store_true",
                    help="print the cost estimate and stop, without any model call")
    ap.add_argument("--env", type=Path, default=None,
                    help=".env file to read OPENROUTER_API_KEY from (never overrides the environment)")
    args = ap.parse_args()

    if args.answer is not None and args.step != "intake":
        print("--answer gäller bara när intake körs om", file=sys.stderr)
        return 2
    through = args.through or (args.step if STEPS.index(args.step) > STEPS.index(LAST) else LAST)
    try:
        source = json.loads((args.run / "history.json").read_text(encoding="utf-8"))
        cut_before(source, args.step)
        later = steps_to_run(args.step, through)
    except (OSError, ValueError) as e:
        print(f"kan inte spela om: {e}", file=sys.stderr)
        return 2
    ran = set(later) | ({"intake"} if args.step == "intake" else set())
    est = estimate(args.run, ran)
    if est is None:
        print("Ingen usage.jsonl i analysen, så ingen kostnadsuppskattning.")
    else:
        print(f"Uppskattat ur analysens usage.jsonl: {est:.2f} USD per omkörning "
              f"({', '.join(sorted(ran, key=STEPS.index))}), {est * args.n:.2f} USD för {args.n}.")
    if args.estimate:
        return 0
    if args.out is None:
        print("--out saknas", file=sys.stderr)
        return 2
    if args.env:
        run_batch.load_env_file(args.env)
    try:
        run_batch.credit_routes.install()
    except run_batch.credit_routes.ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    if not os.environ.get("OPENROUTER_API_KEY") and not api_client.direct_key():
        print("OPENROUTER_API_KEY saknas (sätt i miljön eller via --env)", file=sys.stderr)
        return 2
    A = run_batch.local_app()
    try:
        rows = replay(A.app, args.run, args.step, args.n, args.out, through=through,
                      mode=args.mode, evidens_mode=args.evidens, parallel=args.parallel,
                      name=args.name, answer=args.answer)
    except ValueError as e:
        print(f"kan inte spela om: {e}", file=sys.stderr)
        return 2
    ok = sum(r["ok"] for r in rows)
    print(f"\n{ok}/{len(rows)} omkörningar klara -> {args.out}")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
