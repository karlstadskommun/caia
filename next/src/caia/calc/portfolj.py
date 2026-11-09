"""Portfolio: several actions at once, without counting the same ton twice.

CAIA computes one action at a time, each on a baseline of its own. Added up,
the actions of a plan count the same tons several times wherever they work on
the same emissions: three actions in Karlstad's energy and climate plan claim
93 % of the municipality's own house building between them
(an internal inquiry, October 2026). This module combines the actions on a
shared baseline per emission pot (way B in that inquiry), plus the one
relation it takes from way C, "is a target for".

Per pot, scenario and year:

- A pot is a bounded part of the emissions with a known baseline P, from the
  kommunprofil's register (potter.toml). Pots must not overlap each other.
- An action's drivers on the same pot are added: they are the action's own
  split of its effect, which its evidens step already checked against each
  other.
- The action's share of the pot is s = ΔE / max(E_BAU, P), where ΔE is its
  change before the climate factors (after attribution) and E_BAU its own
  baseline. An action computed on more than the pot (all building, marked on
  house building) takes its own share of the pot; one computed on a part of
  the pot takes its own tons. When E_BAU > P, the rest of its change,
  ΔE - s·P, lies outside the pot and is counted on its own, as before.
- Actions on the same pot multiply: what is left of the pot is P·Π(1 - s).
  The pot's reduction can never exceed the pot, since every s ≤ 1 (an
  action cannot remove more than its own baseline, ΔE ≤ E_BAU).
- A target ("Halvera klimatpåverkan...") and the actions that are its tools
  count as the target on the pot they share. The tools are how the target is
  reached, not a term on top. The target is the ceiling: tools that reach
  further are not counted past it.
- The pot's reduction is shared back on the actions in proportion to each
  one's own claim on the pot (the standard). Beside it stands what an
  order-free rule gives: each action's average contribution over every order
  the actions could be added in (the Shapley value).

Drivers without a pot count as before, added. Nothing here reaches a model.
"""
from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..mode import POTENTIAL, UPPFOLJNING
from .engine import APPENDIX_HEADING, APPENDIX_STAMP, AVG_WINDOW, SCENARIOS, _cum_years, _driver_year, _fmt, avg_years
from .schema import POT_ID, CalcModel, plain

# The words every sum of the actions' own numbers carries, wherever it is
# shown. A sum without them reads as the plan's effect; it is not.
SUM_NOTE = "räknar samma ton flera gånger där åtgärderna verkar på samma utsläpp"

MAX_ACTIONS = 20
_EPS = 1e-9


class PortfoljError(ValueError):
    """A portfolio that cannot be computed. The message is for the user."""


# --- The register of emission pots ------------------------------------------

@dataclass(frozen=True)
class Pott:
    id: str
    namn: str
    baslinje: float      # ton CO2e per year in the baseline year
    ar: int              # the baseline year
    kalla: str
    trend: float = 0.0   # yearly change, -0.02 = 2 % less per year
    perspektiv: str = ""
    anmarkning: str = ""

    def ton(self, year: int) -> float:
        return self.baslinje * (1.0 + self.trend) ** (year - self.ar)

    def public(self) -> dict:
        return {'id': self.id, 'namn': self.namn, 'baslinje': self.baslinje, 'ar': self.ar,
                'kalla': self.kalla, 'trend': self.trend, 'perspektiv': self.perspektiv,
                'anmarkning': self.anmarkning}


def load_potter(path: Path) -> list[Pott]:
    """Read a profile's potter.toml. No file means no pots: every driver then
    counts on its own, as before. A file that is wrong raises, so a typo in a
    baseline is never a silent zero."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise PortfoljError(f"{path} går inte att läsa: {e}") from e
    out: list[Pott] = []
    for i, p in enumerate(raw.get('pott', []), 1):
        where = f"{path}, pott {i}"
        pid = str(p.get('id', ''))
        if not POT_ID.match(pid):
            raise PortfoljError(f"{where}: id {pid!r} ska vara små bokstäver, siffror, - och _.")
        if any(o.id == pid for o in out):
            raise PortfoljError(f"{where}: id {pid!r} finns två gånger.")
        for key in ('namn', 'kalla'):
            if not str(p.get(key, '')).strip():
                raise PortfoljError(f"{where}: {key} saknas.")
        try:
            base = float(p['baslinje'])
            year = int(p['ar'])
            trend = float(p.get('trend', 0.0))
        except (KeyError, TypeError, ValueError) as e:
            raise PortfoljError(f"{where}: baslinje och ar måste vara tal ({e}).") from e
        if not (math.isfinite(base) and base > 0):
            raise PortfoljError(f"{where}: baslinjen måste vara större än 0 ton.")
        if not -1.0 < trend <= 1.0:
            raise PortfoljError(f"{where}: trenden {trend} ska skrivas som andel per år, -0.02.")
        out.append(Pott(id=pid, namn=plain(p['namn']), baslinje=base, ar=year,
                        kalla=plain(p['kalla']), trend=trend,
                        perspektiv=plain(p.get('perspektiv', '')),
                        anmarkning=plain(p.get('anmarkning', ''))))
    return out


# --- What the portfolio reads of an action -----------------------------------

@dataclass(frozen=True)
class Rad:
    """One driver, one scenario, one year, as the engine computed it (ton)."""
    e_bau: float
    basis: float          # ΔE before the climate factors, after attribution
    terr: float
    cons: float
    net: float
    attribution: float = 1.0


@dataclass
class Del:
    """One driver of an action."""
    namn: str
    rader: dict[str, dict[int, Rad]]   # scenario -> year -> row
    pott: str | None = None

    def years(self) -> set[int]:
        return set(self.rader['med'])


@dataclass
class Insats:
    """One action: one saved analysis."""
    id: str
    namn: str
    mode: str
    delar: list[Del]
    skapad: str = ""
    mal_for: tuple[str, ...] = ()


def delar_from_model(model: CalcModel) -> list[Del]:
    """An action's drivers straight from a CalcModel, with the engine's own
    numbers over the years the appendix prints (cumulative and average)."""
    years = sorted(set(_cum_years(model)) | set(avg_years(model)))
    out = []
    for drv in model.drivers:
        rader = {}
        for sc in SCENARIOS:
            rader[sc] = {}
            for y in years:
                r = _driver_year(drv, sc, y)
                rader[sc][y] = Rad(r.e_bau, r.basis, r.terr, r.cons, r.net, r.attribution)
        out.append(Del(namn=drv.name, rader=rader, pott=drv.pot))
    return out


# --- Reading the engine's appendix out of a saved report ---------------------
#
# A saved row holds the report as text, not the engine's numbers. The
# appendix at its end is written by the engine (calc.engine.render_appendix)
# and copied into the report unchanged (caia.appendix), so its tables hold
# every number the portfolio needs: E_BAU, ΔE and the three perspectives per
# driver, scenario and year. Reports from before 2026-09-30 have an appendix
# the language model wrote, without the stamp, and are not read.

# The tool was called Zaid until 2026-10-08, and the engine's stamp said so.
# Reports saved before the rename carry the old name in an appendix the
# engine wrote all the same.
_STAMPS = (APPENDIX_STAMP, APPENDIX_STAMP.replace("CAIA:s", "Zaids"))
_DRIVER = re.compile(r'^Drivare \d+: (.*)$')
_SCENARIO = re.compile(r'^Scenario (medel|min|max):$')
# The engine writes the pot as the last field of the Indata line
# (calc.engine._inputs). Anchored at the end, so a unit text the model wrote
# earlier on the line ("ton; utsläppspott x;") cannot set it.
_POT_IN_INPUTS = re.compile(r'; utsläppspott ([a-z0-9][a-z0-9_-]{0,40})\.?\s*$')
_CELL_SPLIT = re.compile(r'(?<!\\)\|')
_SCENARIO_KEY = {'medel': 'med', 'min': 'min', 'max': 'max'}
_COLUMNS = {'e_bau': 'E_BAU (ton)', 'basis': 'ΔE (ton)', 'terr': 'Territoriell',
            'cons': 'Konsumtion', 'net': 'Netto', 'attribution': 'Attribution'}
_MODE_LINES = {'Medel effekt/år är samma summa delad med': UPPFOLJNING,
               'Medel effekt/år är summan av netto': POTENTIAL}


def _tal(cell: str) -> float:
    s = cell.strip()
    pct = s.endswith('%')
    s = s.rstrip('%').replace(' ', '').replace(' ', '').replace(',', '.')
    v = float(s)
    if not math.isfinite(v):
        raise ValueError(cell)
    return v / 100.0 if pct else v


@dataclass
class Bilaga:
    mode: str
    delar: list[Del] = field(default_factory=list)


def parse_appendix(markdown: str) -> Bilaga | None:
    """The engine's appendix in a saved report, read back to numbers, or
    None when the report has none (or one this function cannot read whole).

    Line based and linear in the length of the text. Rounding: the appendix
    shows tons with two decimals under 10, one under 1 000, whole above, so a
    number read back is within half a unit of the last shown place."""
    if not markdown:
        return None
    start = markdown.find(APPENDIX_HEADING)
    if start < 0:
        return None
    lines = markdown[start:].splitlines()
    if not any(stamp in ln for ln in lines[:6] for stamp in _STAMPS):
        return None
    mode = next((m for ln in lines[:40] for key, m in _MODE_LINES.items() if key in ln), None)
    if mode is None:
        return None
    delar: list[Del] = []
    cur: Del | None = None
    sc = None
    cols: dict[str, int] | None = None
    width = 0
    try:
        for ln in lines[1:]:
            if ln.startswith('Summering, netto'):
                break
            m = _DRIVER.match(ln)
            if m:
                cur = Del(namn=plain(m.group(1)), rader={})
                delar.append(cur)
                sc = cols = None
                continue
            if cur is None:
                continue
            if ln.startswith('Indata:'):
                pm = _POT_IN_INPUTS.search(ln)
                cur.pott = pm.group(1) if pm else None
                continue
            m = _SCENARIO.match(ln)
            if m:
                sc = _SCENARIO_KEY[m.group(1)]
                cur.rader[sc] = {}
                cols = None
                continue
            if sc is None or not ln.startswith('|'):
                continue
            cells = [c.strip() for c in _CELL_SPLIT.split(ln)[1:-1]]
            if cells and cells[0] == 'År':
                width = len(cells)
                cols = {k: cells.index(h) for k, h in _COLUMNS.items() if h in cells}
                if not set(_COLUMNS) - {'attribution'} <= set(cols):
                    return None
                continue
            if cols is None or not cells or not cells[0].isdigit():
                continue
            if len(cells) != width:
                # A row that does not have the header's cells would be read
                # with its numbers under the wrong columns.
                return None
            vals = {k: _tal(cells[i]) for k, i in cols.items()}
            cur.rader[sc][int(cells[0])] = Rad(
                e_bau=vals['e_bau'], basis=vals['basis'], terr=vals['terr'], cons=vals['cons'],
                net=vals['net'], attribution=vals.get('attribution', 1.0))
    except (ValueError, IndexError, KeyError):
        return None
    for d in delar:
        if set(d.rader) != set(SCENARIOS) or not d.rader['med']:
            return None
        if any(set(d.rader[s]) != set(d.rader['med']) for s in SCENARIOS):
            return None
    return Bilaga(mode=mode, delar=delar)


# --- One run per action -------------------------------------------------------

def _action_key(name: str) -> str:
    return ' '.join(re.sub(r'[^\w]+', ' ', name.lower()).split())


def duplicate_runs(insatser: list[Insats]) -> list[list[Insats]]:
    """Groups of runs of the same action (same name, case and punctuation
    aside). Logistikstödet 40.2 was run five times with 131 to 5 815 ton a
    year: a portfolio that took two of them would count one action twice,
    with a spread larger than every overlap correction."""
    groups: dict[str, list[Insats]] = {}
    for ins in insatser:
        groups.setdefault(_action_key(ins.namn), []).append(ins)
    return [g for g in groups.values() if len(g) > 1]


def duplicate_message(groups: list[list[Insats]]) -> str:
    parts = []
    for g in groups:
        dates = ", ".join((i.skapad or "")[:10] or "okänt datum" for i in g)
        parts.append(f"«{g[0].namn}» ({len(g)} körningar: {dates})")
    return ("Samma åtgärd finns med flera gånger: " + "; ".join(parts) + ". En portfölj "
            "räknar en körning per åtgärd, eftersom två körningar av samma åtgärd kan ge "
            "mycket olika tal och båda annars räknas. Välj en körning av varje åtgärd.")


# --- The computation ----------------------------------------------------------

def _shapley(p: float, s: list[float]) -> list[float]:
    """Each unit's Shapley value in the game v(S) = p·(1 - Π_{u∈S}(1 - s_u)).

    Adding unit i to a set S gains p·s_i·Π_{S}(1 - s_u), so the value is
    p·s_i·Σ_k w_k·e_k, with e_k the elementary symmetric polynomial of degree
    k in the others' (1 - s_u) and w_k = k!(n-k-1)!/n! the share of orders in
    which i comes after exactly k of them. Exact, and quadratic in n."""
    n = len(s)
    out = []
    for i in range(n):
        e = [1.0] + [0.0] * (n - 1)
        for j in range(n):
            if j == i:
                continue
            q = 1.0 - s[j]
            for k in range(n - 1, 0, -1):
                e[k] += e[k - 1] * q
        w = sum(e[k] * math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                for k in range(n))
        out.append(p * s[i] * w)
    return out


def _validate(insatser: list[Insats], potter: dict[str, Pott]) -> None:
    if len(insatser) < 2:
        raise PortfoljError("Välj minst två analyser. En portfölj av en åtgärd är analysen själv.")
    if len(insatser) > MAX_ACTIONS:
        raise PortfoljError(f"Välj högst {MAX_ACTIONS} analyser åt gången.")
    ids = [i.id for i in insatser]
    if len(set(ids)) != len(ids):
        raise PortfoljError("Samma analys är vald två gånger.")
    dup = duplicate_runs(insatser)
    if dup:
        raise PortfoljError(duplicate_message(dup))
    if len({i.mode for i in insatser}) > 1:
        raise PortfoljError(
            "Portföljen blandar prognos och uppföljning. De räknar olika år och "
            "svarar på olika frågor, så de kan inte läggas i samma portfölj.")
    for ins in insatser:
        for d in ins.delar:
            if d.pott is not None and d.pott not in potter:
                raise PortfoljError(f"Utsläppspotten {d.pott!r} finns inte i kommunens register.")
    by_id = {i.id: i for i in insatser}
    tools_of: dict[str, str] = {}
    for ins in insatser:
        for t in ins.mal_for:
            if t == ins.id:
                raise PortfoljError(f"«{ins.namn}» kan inte vara ett mål för sig själv.")
            if t not in by_id:
                raise PortfoljError(f"«{ins.namn}» är mål för en åtgärd som inte finns i portföljen.")
            if t in tools_of and tools_of[t] != ins.id:
                raise PortfoljError(
                    f"«{by_id[t].namn}» är verktyg för två mål ({by_id[tools_of[t]].namn} och "
                    f"{ins.namn}). Välj ett av dem.")
            tools_of[t] = ins.id
    for tool, target in tools_of.items():
        if by_id[tool].mal_for:
            raise PortfoljError(
                f"«{by_id[tool].namn}» är både ett mål och ett verktyg för målet "
                f"«{by_id[target].namn}». Ett mål i ett mål räknas inte; välj en nivå.")


def _years(insatser: list[Insats]) -> tuple[list[int], list[int]]:
    """(the years every driver has, the years the average runs over)."""
    sets = [d.years() for i in insatser for d in i.delar]
    if not sets:
        raise PortfoljError("Ingen av de valda analyserna har några delar att räkna på.")
    common = sorted(set.intersection(*sets))
    if not common:
        raise PortfoljError("Analyserna har inga gemensamma år att räkna portföljen över.")
    if insatser[0].mode == UPPFOLJNING:
        return common, common
    window = list(range(AVG_WINDOW[0], AVG_WINDOW[1] + 1))
    if not set(window) <= set(common):
        raise PortfoljError(f"Någon analys saknar åren {AVG_WINDOW[0]}–{AVG_WINDOW[1]}.")
    return common, window


def compute_portfolio(insatser: list[Insats], potter: list[Pott] | dict[str, Pott]) -> dict:
    """The portfolio's numbers, per pot, action, scenario and year.

    Returns {'years', 'window', 'mode', 'pots': {pot_id: {...}},
    'actions': {action_id: {...}}, 'total': {...}, 'warnings': [...]}.
    Every 'alloc' sums to the pot's 'reduction' in every scenario and year,
    under both rules."""
    if not isinstance(potter, dict):
        potter = {p.id: p for p in potter}
    _validate(insatser, potter)
    years, window = _years(insatser)
    by_id = {i.id: i for i in insatser}
    target_of = {t: ins.id for ins in insatser for t in ins.mal_for}

    def zeros():
        return {sc: {y: 0.0 for y in years} for sc in SCENARIOS}

    actions = {i.id: {'own_net': zeros(), 'std_net': zeros(), 'alt_net': zeros(),
                      'own_terr': zeros(), 'own_cons': zeros(),
                      'std_terr': zeros(), 'std_cons': zeros(),
                      'pots': set(), 'unmarked': [], 'in_target': {}, 'outside': {}}
               for i in insatser}
    pots: dict[str, dict] = {}
    notes: list[str] = []

    for ins in insatser:
        a = actions[ins.id]
        for d in ins.delar:
            for sc in SCENARIOS:
                for y in years:
                    r = d.rader[sc][y]
                    a['own_net'][sc][y] += r.net
                    a['own_terr'][sc][y] += r.terr
                    a['own_cons'][sc][y] += r.cons
                    if d.pott is None:
                        # Not on a pot: counted as before, on its own.
                        for k, v in (('std_net', r.net), ('alt_net', r.net),
                                     ('std_terr', r.terr), ('std_cons', r.cons)):
                            a[k][sc][y] += v
            if d.pott is None:
                a['unmarked'].append(d.namn)
            else:
                a['pots'].add(d.pott)

    pot_ids = sorted({d.pott for i in insatser for d in i.delar if d.pott is not None},
                     key=lambda p: list(potter).index(p))
    for pid in pot_ids:
        pot = potter[pid]
        on_pot = [i for i in insatser if any(d.pott == pid for d in i.delar)]
        here = {i.id for i in on_pot}
        # A target counts for its tools only where both are on the pot.
        groups = {t: [v for v in on_pot if target_of.get(v.id) == t]
                  for t in here if any(target_of.get(v.id) == t for v in on_pot)}
        in_group = {v.id: t for t, vs in groups.items() for v in vs}
        units = [i.id for i in on_pot if i.id not in in_group]
        for v in on_pot:
            t = target_of.get(v.id)
            if t is not None and t not in here:
                notes.append(
                    f"OBS: «{v.namn}» är verktyg för målet «{by_id[t].namn}», men målet har "
                    f"inget på {pot.namn}. Där räknas «{v.namn}» som en egen åtgärd.")
        res = {'pot': pot, 'actions': [i.id for i in on_pot], 'groups': groups,
               'P': zeros(), 'claims': zeros(), 'reduction': zeros(),
               'claim': {i.id: zeros() for i in on_pot},
               'alloc_std': {i.id: zeros() for i in on_pot},
               'alloc_alt': {i.id: zeros() for i in on_pot},
               'share': {i.id: zeros() for i in on_pot},
               'own_bau': {i.id: zeros() for i in on_pot},
               'tools_share': {t: zeros() for t in groups},
               'fallback': False, 'mixed': False}
        for sc in SCENARIOS:
            for y in years:
                p = pot.ton(y)
                res['P'][sc][y] = p
                s, basis = {}, {}
                for ins in on_pot:
                    rows = [d.rader[sc][y] for d in ins.delar if d.pott == pid]
                    b = sum(r.basis for r in rows)
                    e = sum(r.e_bau for r in rows)
                    denom = max(e, p)
                    # ΔE ≤ E_BAU by construction (no delta below -100 %, no
                    # attribution above 1), so s ≤ 1. Held there anyway: a
                    # share above 1 would turn 1 - s negative and let the pot
                    # give more than itself.
                    s[ins.id] = min(b / denom, 1.0) if denom > 0 else 0.0
                    basis[ins.id] = b
                    res['own_bau'][ins.id][sc][y] = e
                    res['share'][ins.id][sc][y] = s[ins.id]
                    res['claim'][ins.id][sc][y] = s[ins.id] * p
                res['claims'][sc][y] = sum(res['claim'][i][sc][y] for i in here)
                for t, vs in groups.items():
                    res['tools_share'][t][sc][y] = 1.0 - math.prod(1.0 - s[v.id] for v in vs)
                keep = math.prod(1.0 - s[u] for u in units)
                reduction = p * (1.0 - keep)
                res['reduction'][sc][y] = reduction
                claims = [s[u] * p for u in units]
                total_claim = sum(claims)
                alt = _shapley(p, [s[u] for u in units])
                same_sign = all(c >= 0 for c in claims) or all(c <= 0 for c in claims)
                if same_sign and abs(total_claim) > _EPS:
                    std = [reduction * c / total_claim for c in claims]
                else:
                    # A share of a sum of gains and costs is not a share: with
                    # +500 and -300 on the pot the cut would be credited 875,
                    # more than it did, and near cancellation the shares run
                    # off to millions. The order-free rule stays defined.
                    std = alt
                    if not same_sign:
                        res['mixed'] = True
                    elif abs(reduction) > _EPS:
                        res['fallback'] = True
                for u, v_std, v_alt in zip(units, std, alt):
                    res['alloc_std'][u][sc][y] = v_std
                    res['alloc_alt'][u][sc][y] = v_alt
                # Back on each action: its change on the pot is replaced by
                # what the pot gives it, the part outside the pot stays, and
                # the climate factors keep their proportions.
                for ins in on_pot:
                    b = basis[ins.id]
                    outside = b - s[ins.id] * p
                    a = actions[ins.id]
                    rows = [d.rader[sc][y] for d in ins.delar if d.pott == pid]
                    net = sum(r.net for r in rows)
                    terr = sum(r.terr for r in rows)
                    cons = sum(r.cons for r in rows)
                    for key, alloc in (('std', res['alloc_std']), ('alt', res['alloc_alt'])):
                        f = (alloc[ins.id][sc][y] + outside) / b if abs(b) > _EPS else 0.0
                        a[f'{key}_net'][sc][y] += net * f
                        if key == 'std':
                            a['std_terr'][sc][y] += terr * f
                            a['std_cons'][sc][y] += cons * f
                    if outside > _EPS:
                        a['outside'].setdefault(pid, zeros())[sc][y] = outside
                    if ins.id in in_group:
                        a['in_target'][pid] = in_group[ins.id]
        pots[pid] = res

    warnings = _warnings(insatser, pots, window, by_id) + notes
    for res in pots.values():
        if res['mixed']:
            warnings.append(
                f"OBS: på {res['pot'].namn} finns både åtgärder som minskar och åtgärder som ökar "
                "utsläppen. En ökning räknas på det som minskningarna lämnat kvar, och "
                "portföljens tal fördelas där efter tillskott i alla ordningar i båda "
                "kolumnerna, eftersom en andel av en summa av plus och minus inte går att läsa.")
        if res['fallback']:
            warnings.append(
                f"OBS: på {res['pot'].namn} tar vinster och kostnader nästan ut varandra, så "
                "fördelningen efter egen effekt går inte att räkna. Där står fördelningen "
                "efter tillskott i alla ordningar i båda kolumnerna.")
    unmarked = [(by_id[i].namn, a['unmarked']) for i, a in actions.items() if a['unmarked']]
    if unmarked:
        warnings.append(
            "OBS: delar utan utsläppspott räknas som i dag, var för sig och adderade: "
            + "; ".join(f"«{n}» ({', '.join(ds)})" for n, ds in unmarked)
            + ". Verkar de på samma utsläpp som något annat i portföljen syns det inte här.")

    total = {k: zeros() for k in ('own_net', 'std_net', 'alt_net')}
    for a in actions.values():
        for k in total:
            for sc in SCENARIOS:
                for y in years:
                    total[k][sc][y] += a[k][sc][y]
    return {'years': years, 'window': window, 'mode': insatser[0].mode,
            'insatser': insatser, 'pots': pots, 'actions': actions, 'total': total,
            'warnings': warnings}


def _win(years: list[int]) -> str:
    return f"medel {years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])


def _mean(series: dict[int, float], years: list[int]) -> float:
    return sum(series[y] for y in years) / len(years)


def _warnings(insatser, pots, window, by_id) -> list[str]:
    out = []
    for pid, res in pots.items():
        pot = res['pot']
        worst = max(window, key=lambda y: res['claims']['med'][y] / res['P']['med'][y])
        share = res['claims']['med'][worst] / res['P']['med'][worst]
        claims_w = _mean(res['claims']['med'], window)
        red_w = _mean(res['reduction']['med'], window)
        reducing = all(v >= 0 for i in res['actions'] for v in res['share'][i]['med'].values())
        if (reducing and share <= 1.0 + _EPS and len(res['actions']) > 1
                and _fmt(claims_w) != _fmt(red_w)):
            out.append(
                f"OBS: åtgärderna på {pot.namn} räknar var för sig med {_fmt(claims_w)} ton per år "
                f"av pottens utsläpp ({_win(window)}). Portföljen räknar dem på samma utsläpp, "
                f"så att varje åtgärd tar sin andel av det de andra lämnat kvar: tillsammans "
                f"{_fmt(red_w)} ton. Skillnaden, {_fmt(claims_w - red_w)} ton, är de ton som "
                "annars räknas flera gånger. Verkar åtgärderna i stället på var sin del av "
                "potten räknar portföljen för lite, och då bör potten delas i två.")
        if share > 1.0 + _EPS:
            out.append(
                f"VARNING: åtgärderna på {pot.namn} gör tillsammans anspråk på "
                f"{_pct(share)} av pottens utsläpp {worst} (medel), mer än hela potten. Mer än "
                "potten går inte att minska, så summan av deras egna tal räknar samma ton "
                f"flera gånger. Portföljen räknar {_pct(res['reduction']['med'][worst] / res['P']['med'][worst])}.")
        for iid in res['actions']:
            over = [y for y in window if res['own_bau'][iid]['med'][y] > res['P']['med'][y] + _EPS]
            if over:
                y = over[-1]
                out.append(
                    f"OBS: «{by_id[iid].namn}» räknar på {_fmt(res['own_bau'][iid]['med'][y])} ton "
                    f"utsläpp {y}, mer än hela {pot.namn} ({_fmt(res['P']['med'][y])} ton). Den har "
                    "räknats på något större än potten. På potten räknas dess andel av sina egna "
                    "utsläpp; resten av effekten ligger utanför potten och räknas som i dag.")
        outside = [iid for iid in res['actions']
                   if any(_outside_of(by_id[iid], pid, res, y) > _EPS for y in window)]
        if len(outside) > 1:
            names = ", ".join(f"«{by_id[i].namn}»" for i in outside)
            out.append(
                f"OBS: {names} räknar alla på mer än {pot.namn}. Det de räknar utanför potten "
                "läggs till var för sig, som i analyserna, och kan vara samma ton. Portföljen "
                "kontrollerar bara överlappet inom potten.")
        for t, vs in res['groups'].items():
            y = window[-1]
            target = res['share'][t]['med'][y]
            tools = res['tools_share'][t]['med'][y]
            names = ", ".join(f"«{v.namn}»" for v in vs)
            if tools < target - 1e-6:
                out.append(
                    f"OBS: målet «{by_id[t].namn}» räknar med {_pct(target)} av {pot.namn} {y}. "
                    f"Verktygen {names} ger tillsammans {_pct(tools)}. Portföljen räknar målets "
                    "tal; resten förutsätter att målet nås med mer än verktygen i portföljen.")
            elif tools > target + 1e-6:
                out.append(
                    f"OBS: verktygen {names} ger tillsammans {_pct(tools)} av {pot.namn} {y}, mer "
                    f"än målet «{by_id[t].namn}» ({_pct(target)}). Målet är taket, så portföljen "
                    "räknar inte längre än målet.")
        if insatser[0].mode == UPPFOLJNING:
            att = 0.0
            for iid in res['actions']:
                rows = [d.rader['med'][window[0]] for d in by_id[iid].delar if d.pott == pid]
                att += max((r.attribution for r in rows), default=0.0)
            if att > 1.0 + _EPS:
                out.append(
                    f"VARNING: insatserna på {pot.namn} tillskriver sig tillsammans {_pct(att)} av "
                    "förändringen de mäter (attributionerna adderade, en analys utan "
                    "attribution räknas som 100 procent). Mäter de samma förändring kan inte mer "
                    "än 100 procent av den bero på insatserna tillsammans. Pröva "
                    "attributionerna mot varandra.")
    # F3: in follow-up the window is the years every analysis has, which can
    # be fewer than an analysis' own.
    if insatser[0].mode == UPPFOLJNING:
        for ins in insatser:
            own = sorted(set().union(*(d.years() for d in ins.delar)))
            if own != window:
                out.append(
                    f"OBS: «{ins.namn}» räknar {_years_txt(own)} i sin analys. Portföljen räknar "
                    f"bara de år alla analyser har ({_years_txt(window)}), så talen här är inte "
                    "analysens eget medel.")
    return out


def _years_txt(years: list[int]) -> str:
    return f"åren {years[0]}–{years[-1]}" if len(years) > 1 else f"året {years[0]}"


def _outside_of(ins: Insats, pid: str, res: dict, y: int) -> float:
    b = sum(d.rader['med'][y].basis for d in ins.delar if d.pott == pid)
    return b - res['claim'][ins.id]['med'][y]


# --- Text ----------------------------------------------------------------------

def _pct(x: float) -> str:
    v = round(x * 100)
    return f"{v} %"


def _span(lo: float, mid: float, hi: float) -> str:
    return f"{_fmt(mid)} ({_fmt(lo)} till {_fmt(hi)})"


def _cell(text: str) -> str:
    return plain(text).replace('|', '\\|')


def render_portfolio(result: dict) -> str:
    """The portfolio as text for the page: totals first, then each pot and
    each action, with the rule that shared the pot back stated beside the
    numbers. Every sum of the actions' own numbers says that it counts the
    same tons several times."""
    years, window = result['years'], result['window']
    win = f"{window[0]}–{window[-1]}" if len(window) > 1 else str(window[0])
    ins = result['insatser']
    by_id = {i.id: i for i in ins}
    tot = result['total']

    def mean3(series):
        return [_mean(series[sc], window) for sc in ('min', 'med', 'max')]

    own, std, alt = mean3(tot['own_net']), mean3(tot['std_net']), mean3(tot['alt_net'])
    # The row says what the portfolio checked, and what it only added.
    added = []
    if any(a['unmarked'] for a in result['actions'].values()):
        added.append("delar utan utsläppspott")
    if any(a['outside'] for a in result['actions'].values()):
        added.append("delar utanför potten")
    portfolio_label = ("Portföljen, där åtgärder på samma utsläppspott inte räknas två gånger"
                       if result['pots'] else "Portföljen")
    if added:
        portfolio_label += f" ({' och '.join(added)} är adderade som i analyserna)"
    mode_line = ("Uppföljning av genomförda åtgärder." if result['mode'] == UPPFOLJNING
                 else "Prognos för planerade åtgärder.")
    lines = [
        f"## Portfölj: {len(ins)} åtgärder",
        "",
        f"{mode_line} Netto i ton CO2e per år, medel {win}, med lågt och högt scenario inom "
        "parentes.",
        "",
        "| | Medel per år |",
        "|---|---|",
        f"| Summa av åtgärdernas egna tal (summan {SUM_NOTE}) | {_span(*own)} |",
        f"| {portfolio_label} | {_span(*std)} |",
        f"| Skillnad | {_fmt(own[1] - std[1])} |",
        "",
    ]
    if result['warnings']:
        lines += ["### Att läsa först", ""] + [f"- {w}" for w in result['warnings']] + [""]

    lines += ["### Per utsläppspott", "",
              "En utsläppspott är en avgränsad del av utsläppen, med ett känt utsläpp per år. "
              "Åtgärder på samma pott räknas tillsammans: varje åtgärd minskar det som de andra "
              "lämnat kvar, så tillsammans kan de aldrig minska mer än hela potten. Talen gäller "
              "utsläppen före fördelningen på territoriellt och konsumtionsbaserat.", ""]
    if not result['pots']:
        lines += ["Ingen del av analyserna är kopplad till en utsläppspott, så portföljen är "
                  "summan av åtgärdernas egna tal. Den summan räknar samma ton flera gånger där "
                  "åtgärderna verkar på samma utsläpp.", ""]
    for pid, res in result['pots'].items():
        pot = res['pot']
        lines += [f"#### {_cell(pot.namn)}", "",
                  f"Pottens utsläpp: {_fmt(pot.baslinje)} ton CO2e per år {pot.ar}"
                  + (f", {pot.trend * 100:+.1f} % per år".replace('.', ',') if pot.trend else
                     ", samma alla år")
                  + (f" ({_cell(pot.perspektiv)})" if pot.perspektiv else "") + f". Källa: {_cell(pot.kalla.rstrip('.'))}."]
        if pot.anmarkning:
            lines.append(_cell(pot.anmarkning))
        names = []
        for iid in res['actions']:
            t = next((t for t, vs in res['groups'].items() if any(v.id == iid for v in vs)), None)
            names.append(f"«{_cell(by_id[iid].namn)}»"
                         + (f" (verktyg för målet «{_cell(by_id[t].namn)}»)" if t else "")
                         + (" (mål)" if iid in res['groups'] else ""))
        lines += ["", "Åtgärder på potten: " + ", ".join(names) + ".", "",
                  f"| År | Pottens utsläpp | Åtgärdernas egna tal på potten, adderade "
                  f"(summan {SUM_NOTE}) | Portföljen | Portföljens andel av potten |",
                  "|---|---|---|---|---|"]
        for y in years:
            p = res['P']['med'][y]
            lines.append(
                f"| {y} | {_fmt(p)} | {_fmt(res['claims']['med'][y])} ({_pct(res['claims']['med'][y] / p)}) "
                f"| {_span(res['reduction']['min'][y], res['reduction']['med'][y], res['reduction']['max'][y])} "
                f"| {_pct(res['reduction']['med'][y] / p)} |")
        lines += ["", "Medelscenariot, låg och hög inom parentes. Ton CO2e per år.", ""]

    lines += ["### Per åtgärd", "",
              f"Netto i ton CO2e per år, medel {win}, medelscenariot.", "",
              "| Åtgärd | Analysens eget tal | I portföljen | Med den andra fördelningsregeln | Kommentar |",
              "|---|---|---|---|---|"]
    for i in ins:
        a = result['actions'][i.id]
        comment = []
        for pid, t in a['in_target'].items():
            comment.append(f"ingår i målet «{_cell(by_id[t].namn)}» på "
                           f"{_cell(result['pots'][pid]['pot'].namn)}")
        if a['outside']:
            comment.append("en del av effekten ligger utanför potten och räknas som i dag")
        if a['unmarked']:
            comment.append("delar utan pott räknas som i dag")
        if not a['pots']:
            comment.append("ingen del på en pott")
        lines.append(
            f"| «{_cell(i.namn)}» ({(i.skapad or '')[:10] or 'okänt datum'}) "
            f"| {_fmt(_mean(a['own_net']['med'], window))} | {_fmt(_mean(a['std_net']['med'], window))} "
            f"| {_fmt(_mean(a['alt_net']['med'], window))} | {'; '.join(comment)} |")
    lines.append(
        f"| Summa | {_fmt(own[1])} (summan {SUM_NOTE}) | {_fmt(std[1])} | {_fmt(alt[1])} | |")
    lines += ["",
              "**Fördelningsregeln.** Det portföljen ger på en pott fördelas tillbaka på "
              "åtgärderna i proportion till hur mycket var och en tar av potten på egen hand "
              "(kolumnen I portföljen). Den andra regeln ger varje åtgärd vad den i genomsnitt "
              "tillför, räknat i alla ordningar som åtgärderna kan läggas till i: när två "
              "åtgärder överlappar delar de lika på överlappet. Båda summerar till portföljen. "
              "Regeln ändrar bara fördelningen mellan åtgärderna, inte portföljens tal. Ett mål "
              "och dess verktyg räknas som målet: verktygen står med 0 på potten och målet med "
              "hela gruppens del.",
              ""]
    lines += ["### Så räknar portföljen", "",
              "- Varje analys räknas som förut. Portföljen läser talen ur analysens tekniska "
              "bilaga, år för år och i alla tre scenarierna.",
              "- På en utsläppspott tar varje åtgärd en andel: sin minskning delad med det största "
              "av sina egna utsläpp och pottens. Har en analys räknat på mer än potten, räknas "
              "på potten bara dess andel; resten av effekten ligger utanför potten.",
              "- Åtgärderna på samma pott multipliceras: kvar blir pottens utsläpp gånger "
              "(1 minus andelen) för varje åtgärd. Halverar en åtgärd utsläppen och en annan "
              "sänker dem 28 procent blir det tillsammans 64 procent, inte 78.",
              "- Ett mål och verktygen för det räknas som målet. Målet är taket.",
              "- Delar utan pott, och den del av en åtgärd som ligger utanför potten, läggs till "
              "som i analysen. Där kontrollerar portföljen inget överlapp.",
              "- Nettot räknas sedan med analysens egna klimatfaktorer (territoriellt, "
              "konsumtionsbaserat, överlapp), så nettot kan skilja sig från pottens tal.",
              f"- En portfölj räknar en körning per åtgärd. Medel per år räknas över {win}."]
    return "\n".join(lines)
