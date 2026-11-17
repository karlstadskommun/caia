"""Run the full CAIA pipeline headless on one or more intake packages.

Built for ex-post evaluation of Karlstad's driftsmedel (the programme's final
report, autumn 2026): each measure is a markdown "intake package" that already
contains everything the analyst knows. The intake agent still asks its
clarifying questions; we answer them with the package's own answer block so
the run is reproducible and nobody has to sit at the chat.

Usage:

    CAIA_KOMMUN=<profil> OPENROUTER_API_KEY=... python tools/run_batch.py <package.md> [<package.md> ...] --out <dir>

With CAIA_ANTHROPIC_KEYS set (comma-separated, in order), each call tries
those Anthropic keys first and OpenRouter last (tools/credit_routes.py).
CAIA_ANTHROPIC_API_KEY sends every call to one Anthropic key with no
fallback; set one of the two, not both.
usage.jsonl then says which route served each call.

Each package becomes <dir>/<stem>/{intake,emap,baslinje,evidens,kalkyl,qa,rapport}.md
plus kalkyl_meta.json (headline numbers, deterministic flag) and history.json
(the exact conversation the agents saw). A run.log records timing per step.
usage.jsonl has one line per model call (step, model, effort, tokens, seconds,
estimated USD at list price), and the run ends with a cost summary per step
and in total, printed and appended to run.log.
rapport.md ends with the section *Talens ursprung* from the kalkyl step, as a
report from the web page does; history.json holds the report as the model
step returned it, without the section.

Package format: plain markdown. If it contains a line `## Svar till intake-agenten`,
the text after it (to end of file or next `## `) is used as the answer to every
clarifying question the intake agent asks. Otherwise a generic "make assumptions
and proceed" answer is used. The text before that heading is the measure text.

Follow-up of a measure that has been carried out (driftsmedel): --mode
uppfoljning. Every step then gets the follow-up rules (caia/agents/
uppfoljning.py) and the calc reports realised, remaining and per grant year.

--parallel N runs N packages at a time. Each package is one analysis, as one
user would run it; the log lines carry the package name.

Costs real API calls, roughly 2-3 USD and 5-10 minutes per package; the
summary at the end says what this run cost.
"""
from __future__ import annotations

import argparse
import contextvars
import json
import logging
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from caia import api_client  # noqa: E402
import credit_routes  # noqa: E402  (tools/, beside this file)
from caia.mode import MODES, POTENTIAL  # noqa: E402
from caia.pipeline import BRIDGE, STEPS, with_kallmarkering  # noqa: E402

PIPELINE = list(STEPS[1:])  # intake is driven separately: it asks questions first

GENERIC_ANSWER = (
    "Allt underlag som finns står i beskrivningen ovan. Gör rimliga antaganden "
    "för resten, markera dem tydligt som ANTAGANDE, och skapa åtgärdsprofilen nu."
)
ANSWER_HEADING = re.compile(r"^## Svar till intake-agenten\s*$", re.MULTILINE)
MAX_CLARIFY_ROUNDS = 3


def split_package(text: str) -> tuple[str, str]:
    """Return (measure_text, answer_text)."""
    m = ANSWER_HEADING.search(text)
    if not m:
        return text.strip(), GENERIC_ANSWER
    measure = text[: m.start()].strip()
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    answer = (rest[: nxt.start()] if nxt else rest).strip() or GENERIC_ANSWER
    return measure, answer


def load_env_file(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, no export, no interpolation.
    Never overrides variables already set in the environment."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def post_evidens_split(app, history: list[dict], say, mode: str = POTENTIAL) -> tuple[int, dict]:
    """Drive evidens the way the web client does: plan, one request per driver
    in parallel, then merge. Returns (status, body) shaped like /api/evidens.

    Each worker gets its own test client; the parallelism is real, so the
    wall-clock time logged here is what a user would wait."""
    plan = app.test_client().post("/api/evidens/plan", json={"history": history, "mode": mode}).get_json()
    drivers = plan.get("drivers") or []
    if not drivers:
        say("evidens: no drivers parsed, falling back to the single call")
        resp = app.test_client().post("/api/evidens", json={"history": history, "mode": mode})
        return resp.status_code, resp.get_json()

    def one(d):
        t = time.time()
        resp = app.test_client().post("/api/evidens/part",
                                      json={"history": history, "driver": d["number"], "mode": mode})
        return d, resp.status_code, resp.get_json(), time.time() - t

    # Each part runs in a copy of this thread's context, so its model calls
    # are metered under this package (UsageMeter).
    with ThreadPoolExecutor(max_workers=len(drivers)) as pool:
        futures = [pool.submit(contextvars.copy_context().run, one, d) for d in drivers]
        results = [f.result() for f in futures]
    for d, status, body, secs in results:
        say(f"  evidens part {d['number']} {secs:5.1f}s status={status} {d['name'][:50]}")
    failed = [(d, body) for d, status, body, _ in results if status != 200]
    if failed:
        why = "; ".join(f"drivare {d['number']}: {(b or {}).get('error')}" for d, b in failed)
        return 502, {"error": f"evidens parts failed ({why})"}
    t = time.time()
    resp = app.test_client().post("/api/evidens/merge", json={
        "history": history,
        "mode": mode,
        "parts": [{"number": b["number"], "text": b["text"]} for _, _, b, _ in results],
    })
    body = resp.get_json()
    say(f"  evidens merge {time.time() - t:5.1f}s status={resp.status_code} "
        f"corrected={(body or {}).get('corrected')}")
    for msg in (body or {}).get("skipped") or []:
        say(f"  VARNING evidens: rättelse överhoppad: {msg}")
    return resp.status_code, body


_LOG_LOCK = threading.Lock()

# The package whose model calls are running in this context. Set by
# UsageMeter.start in the thread that runs the package, carried into the
# evidens fan-out by copy_context.
_PACKAGE: contextvars.ContextVar[str | None] = contextvars.ContextVar("caia_batch_package",
                                                                       default=None)


class UsageMeter:
    """Listener on api_client.USAGE_LISTENERS: every model call's usage record,
    by package. Each package's calls go to <outdir>/usage.jsonl as they happen
    (so a run that dies halfway still shows what it cost), and summary() adds
    them up per step at the end."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._files: dict[str, Path] = {}
        self.records: list[dict] = []

    def start(self, package: str, path: Path) -> contextvars.Token:
        """Meter the calls in this context as `package` until the returned
        token is reset. Empties the file: it holds the latest run of the
        package, like the step files beside it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        with self._lock:
            self._files[package] = path
        return _PACKAGE.set(package)

    def __call__(self, rec: dict) -> None:
        package = _PACKAGE.get()
        row = {"package": package, **rec}
        with self._lock:
            self.records.append(row)
            path = self._files.get(package)
            if path is not None:
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize_usage(records: list[dict]) -> str:
    """Per step and in total: calls, tokens, call seconds, estimated USD.
    Seconds are summed per call, so the parallel evidens parts count once
    each, not as the wall time a user waits."""
    if not records:
        return "Kostnad: inga modellanrop mätta."

    def add(acc: dict, r: dict) -> None:
        acc["calls"] += 1
        for k in ("input", "output", "cache_read", "cache_write", "usd"):
            acc[k] += r.get(k) or 0
        acc["seconds"] += r.get("seconds") or 0
        acc["unpriced"] += r.get("usd") is None
        acc["errors"] += "error" in r

    def empty() -> dict:
        return dict(calls=0, input=0, output=0, cache_read=0, cache_write=0,
                    seconds=0.0, usd=0.0, unpriced=0, errors=0)

    by_step: dict[str, dict] = {}
    by_pkg: dict[str, dict] = {}
    by_route: dict[str, dict] = {}
    total = empty()
    for r in records:
        add(by_step.setdefault(r.get("step") or "?", empty()), r)
        add(by_pkg.setdefault(r.get("package") or "?", empty()), r)
        if r.get("route"):
            add(by_route.setdefault(r["route"], empty()), r)
        add(total, r)

    head = f"{'':16} {'anrop':>5} {'in':>9} {'ut':>9} {'cache':>9} {'sek':>7} {'USD':>8}"

    def row(name: str, a: dict) -> str:
        return (f"{name[:16]:16} {a['calls']:5d} {a['input']:9d} {a['output']:9d} "
                f"{a['cache_read'] + a['cache_write']:9d} {a['seconds']:7.0f} {a['usd']:8.2f}")

    lines = ["Kostnad per steg (listpris, uppskattat):", head]
    lines += [row(step, a) for step, a in by_step.items()]
    lines.append(row("totalt", total))
    if len(by_pkg) > 1:
        lines += ["", "Per analys:"] + [row(p, a) for p, a in by_pkg.items()]
    if by_route:
        lines += ["", "Per väg:"] + [row(r, a) for r, a in sorted(by_route.items())]
    if total["unpriced"]:
        lines.append(f"{total['unpriced']} anrop utan pris (fel, eller modell utan rad i "
                     "api_client.PRICES) räknas som 0 USD.")
    if total["errors"]:
        lines.append(f"{total['errors']} anrop slutade med fel, så totalen är en undre gräns: "
                     "ett anrop som fick timeout kan ha debiterats ändå.")
    return "\n".join(lines)


def run_package(client, pkg: Path, outdir: Path, log, evidens_mode: str = "split",
                mode: str = POTENTIAL, meter: UsageMeter | None = None) -> bool:
    if meter is None:
        return _run_package(client, pkg, outdir, log, evidens_mode, mode)
    token = meter.start(pkg.stem, outdir / "usage.jsonl")
    try:
        return _run_package(client, pkg, outdir, log, evidens_mode, mode)
    finally:
        _PACKAGE.reset(token)


def make_say(name: str, log):
    """A log function for one analysis: console and run.log, name first."""
    def say(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {name}: {msg}"
        with _LOG_LOCK:
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()
    return say


def write_history(outdir: Path, history: list[dict]) -> None:
    (outdir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def run_intake(client, history: list[dict], answer: str, outdir: Path, say,
               mode: str = POTENTIAL) -> bool:
    """The intake dialogue on `history` (the measure text, and nothing else
    yet): every clarifying question gets `answer`, up to MAX_CLARIFY_ROUNDS.
    Appends the turns and the bridge line to `history` and writes intake.md.
    False if the intake failed or never completed (history.json is written)."""
    intake = None
    for attempt in range(MAX_CLARIFY_ROUNDS + 1):
        t = time.time()
        resp = client.post("/api/intake", json={"history": history, "mode": mode})
        if resp.status_code != 200:
            say(f"intake failed: {resp.get_data(as_text=True)[:400]}")
            return False
        intake = resp.get_json()
        say(f"intake {time.time() - t:5.1f}s status={intake.get('status')} "
            f"profiles={len(intake.get('profiles') or [])}")
        history.append({"role": "assistant", "content": intake["message"]})
        if intake.get("status") == "complete":
            break
        if attempt >= MAX_CLARIFY_ROUNDS:
            say("intake never completed; aborting this package")
            (outdir / "intake.md").write_text(intake["message"], encoding="utf-8")
            write_history(outdir, history)
            return False
        history.append({"role": "user", "content": answer})

    (outdir / "intake.md").write_text(intake["message"], encoding="utf-8")
    history.append({"role": "user", "content": BRIDGE["intake"]})
    return True


def run_steps(client, history: list[dict], steps: list[str], outdir: Path, say,
              evidens_mode: str = "split", mode: str = POTENTIAL,
              kallmarkering_md: str | None = None) -> bool:
    """Run `steps` (in pipeline order, intake excluded) on `history`, the way
    the page does: each step sees the whole conversation so far, its answer
    and the bridge line are appended. Writes <step>.md per step and
    kalkyl_meta.json. `kallmarkering_md` is the kalkyl step's source section,
    for a run that starts after kalkyl. False on the first failed step
    (history.json is written)."""
    for step in steps:
        t = time.time()
        if step == "evidens" and evidens_mode == "split":
            status, body = post_evidens_split(client.application, history, say, mode)
        else:
            resp = client.post(f"/api/{step}", json={"history": history, "mode": mode})
            status, body = resp.status_code, resp.get_json()
        if status != 200:
            say(f"{step} failed: {json.dumps(body, ensure_ascii=False)[:400]}")
            write_history(outdir, history)
            return False
        out = body["output"]
        # The source section is computed by the kalkyl step, and the report
        # step does not carry it: the page appends it to the report it shows,
        # saves and downloads, so the report file here gets it the same way.
        written = with_kallmarkering(out, kallmarkering_md) if step == "rapport" else out
        (outdir / f"{step}.md").write_text(written, encoding="utf-8")
        if step == "kalkyl":
            kallmarkering_md = body.get("kallmarkering_md")
            meta = {k: v for k, v in body.items() if k != "output"}
            (outdir / "kalkyl_meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            say(f"kalkyl deterministic={meta.get('deterministic')} headline={meta.get('headline')}")
        say(f"{step:9} {time.time() - t:5.1f}s {len(out)} chars")
        history.append({"role": "assistant", "content": out})
        if step in BRIDGE:
            history.append({"role": "user", "content": BRIDGE[step]})
    return True


def _run_package(client, pkg: Path, outdir: Path, log, evidens_mode: str,
                 mode: str) -> bool:
    measure, answer = split_package(pkg.read_text(encoding="utf-8"))
    outdir.mkdir(parents=True, exist_ok=True)
    history = [{"role": "user", "content": measure}]
    started = time.time()
    say = make_say(pkg.stem, log)
    if not run_intake(client, history, answer, outdir, say, mode):
        return False
    if not run_steps(client, history, PIPELINE, outdir, say, evidens_mode, mode):
        return False
    write_history(outdir, history)
    say(f"DONE {time.time() - started:.0f}s")
    return True


def local_app():
    """Import the app for a local run: no Supabase, no password, dev-open
    gate, no rate limit. Sets the environment first, because the app reads it
    at import time. Returns the app module (caia.web.app)."""
    os.environ["SUPABASE_URL"] = ""
    os.environ.setdefault("CAIA_PASSWORD", "")
    os.environ["CAIA_DEV_OPEN"] = "1"
    # The rate limiter guards a shared server per IP. Every test client here is
    # 127.0.0.1, so with --parallel the packages would share one bucket of 20
    # calls a minute and fail on 429 in the evidens fan-out.
    os.environ.setdefault("CAIA_RATE_LIMIT_PER_MIN", "100000")
    os.environ.setdefault("CAIA_RATE_LIMIT_PER_DAY", "100000")
    from caia.web import app as A
    # The app logs a usage line per model call; here usage.jsonl holds the
    # same lines, so keep them off the console.
    logging.getLogger("caia.api_client").setLevel(logging.WARNING)
    return A


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--env", type=Path, default=None,
                    help=".env file to read OPENROUTER_API_KEY from (never overrides the environment)")
    ap.add_argument("--evidens", choices=["split", "single"], default="split",
                    help="split = one call per driver + merge, as the web client runs it; "
                         "single = the old one-call step, kept for comparison runs")
    ap.add_argument("--mode", choices=MODES, default=POTENTIAL,
                    help="potential = expected potential (default); uppfoljning = follow-up "
                         "of a measure that has been carried out")
    ap.add_argument("--parallel", type=int, default=1,
                    help="packages to run at the same time (default 1)")
    args = ap.parse_args()

    if args.env:
        load_env_file(args.env)
    try:
        routed = credit_routes.install()
    except credit_routes.ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    if routed and not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY saknas: den är sista vägen när Anthropic-nycklarna är slut "
              "(sätt i miljön eller via --env)", file=sys.stderr)
        return 2
    if routed:
        print(f"Anthropic-nycklarna först ({len(credit_routes.direct_keys())} i ordning), "
              "sist OpenRouter", file=sys.stderr)
    elif api_client.direct_key():
        # One Anthropic key, straight to Anthropic (api_client.py).
        print("Kör direkt mot Anthropic (CAIA_ANTHROPIC_API_KEY), inte via OpenRouter",
              file=sys.stderr)
    elif not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY saknas (sätt i miljön eller via --env)", file=sys.stderr)
        return 2

    A = local_app()

    args.out.mkdir(parents=True, exist_ok=True)
    missing = [p for p in args.packages if not p.is_file()]
    for pkg in missing:
        print(f"saknas: {pkg}", file=sys.stderr)
    found = [p for p in args.packages if p.is_file()]
    meter = UsageMeter()
    api_client.USAGE_LISTENERS.append(meter)
    with open(args.out / "run.log", "a", encoding="utf-8") as log:
        def one(pkg: Path) -> bool:
            # One package's crash must not take the others' results with it.
            try:
                return run_package(A.app.test_client(), pkg, args.out / pkg.stem, log,
                                   args.evidens, args.mode, meter=meter)
            except Exception as e:  # noqa: BLE001
                print(f"{pkg.stem}: avbröts: {e!r}", file=sys.stderr)
                return False
        try:
            with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
                ok = sum(pool.map(one, found))
        finally:
            api_client.USAGE_LISTENERS.remove(meter)
            summary = summarize_usage(meter.records)
            print("\n" + summary)
            log.write(summary + "\n")
    print(f"\n{ok}/{len(args.packages)} paket klara -> {args.out}")
    return 0 if ok == len(args.packages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
