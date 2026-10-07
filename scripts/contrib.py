#!/usr/bin/env python3
"""Renders the contribution graph panel from GitHub's contribution calendar.

Usage: python3 scripts/contrib.py <user> <out.svg> [--demo]
Needs GITHUB_TOKEN in the environment (the Actions token is enough). Standard library only.
Days are bucketed by local calendar day in CONTRIB_TZ (default America/New_York).
"""
import datetime as dt
import json
import os
import random
import re
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

BG, BG2, BG4 = "#1d2021", "#3c3836", "#665c54"
FG, FG0, FG4, GREY = "#ebdbb2", "#fbf1c7", "#a89984", "#928374"
GREEN, BLUE, AQUA = "#b8bb26", "#83a598", "#8ec07c"
LEVELS = [BG2, "#575619", "#79740e", "#98971a", GREEN]
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
W, CW = 1000, 7.8
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# GitHub usernames: 1-39 chars, alphanumeric or single hyphens, no leading/trailing hyphen.
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
MAX_RESPONSE = 5_000_000  # bytes; the real calendar response is a few dozen KB


def load_tz():
    name = os.environ.get("CONTRIB_TZ", "America/New_York")
    try:
        return ZoneInfo(name)
    except Exception:
        print(f"warning: bad CONTRIB_TZ {name!r}, using America/New_York", file=sys.stderr)
        return ZoneInfo("America/New_York")


TZ = load_tz()

QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
contributionsCollection(from:$from,to:$to){contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""


def window():
    """Last 365 calendar days in TZ, offset-aware so GitHub splits days at local midnight."""
    now = dt.datetime.now(TZ).replace(microsecond=0)
    start = dt.datetime.combine(now.date() - dt.timedelta(days=364), dt.time(), TZ)
    return start, now


def parse_day(d):
    """Validate one day from the API so nothing unexpected reaches the SVG."""
    date = dt.date.fromisoformat(str(d["date"]))
    count = int(d["contributionCount"])
    weekday = int(d["weekday"])
    if count < 0 or not 0 <= weekday <= 6:
        raise ValueError(f"unexpected day data: {d!r}")
    return date, count, weekday


def fetch(login):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    start, end = window()
    variables = {"login": login, "from": start.isoformat(), "to": end.isoformat()}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json", "User-Agent": "contrib.py"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise SystemExit("GraphQL response unexpectedly large")
    data = json.loads(raw)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    user = (data.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"user {login!r} not found")
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    today = end.date()
    out = []
    for w in weeks:
        days = [parse_day(d) for d in w["contributionDays"]]
        days = [d for d in days if d[0] <= today]     # never show "tomorrow"
        if days:
            out.append(days)
    if not out:
        raise SystemExit("no contribution data returned")
    return out


def demo():
    rng = random.Random(1729)
    end = dt.datetime.now(TZ).date()
    start = end - dt.timedelta(days=364 + (end.weekday() + 1) % 7)
    weeks, week = [], []
    day = start
    while day <= end:
        busy = rng.random() < 0.55
        week.append((day, rng.choice([1, 1, 2, 3, 4, 6, 9]) if busy else 0, (day.weekday() + 1) % 7))
        if len(week) == 7:
            weeks.append(week); week = []
        day += dt.timedelta(days=1)
    if week:
        weeks.append(week)
    return weeks


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def mono(x, y, s, fill, size=13, cw=None, anchor=None, weight=None):
    attrs = f' font-size="{size}" fill="{fill}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    if cw:
        keep = [(i, c) for i, c in enumerate(s) if c != " "]
        xs = " ".join(f"{x + i*cw:.1f}" for i, _ in keep)
        return f'<text x="{xs}" y="{y}"{attrs}>{esc("".join(c for _, c in keep))}</text>'
    return f'<text x="{x}" y="{y}"{attrs}>{esc(s)}</text>'


def line(x, y, parts, size=13, cw=CW):
    out, col = [], 0
    for p in parts:
        out.append(mono(round(x + col*cw, 1), y, p[0], p[1], size, cw=cw, weight=p[2] if len(p) > 2 else None))
        col += len(p[0])
    return "".join(out)


def stats(days):
    total = sum(c for _, c, _ in days)
    longest = run = 0
    for _, c, _ in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    tail = days[:-1] if days and days[-1][1] == 0 else days     # today (local) may still be empty
    for _, c, _ in reversed(tail):
        if not c:
            break
        current += 1
    by_wd = [0]*7
    for _, c, wd in days:
        by_wd[wd] += c
    best = max(days, key=lambda d: d[1])
    return total, current, longest, WEEKDAYS[by_wd.index(max(by_wd))], best


def levels(days):
    nz = sorted(c for _, c, _ in days if c)
    if not nz:
        return lambda c: 0
    q = [nz[int(len(nz)*f)] for f in (0.25, 0.5, 0.75)]
    return lambda c: 0 if c == 0 else 1 + sum(c > t for t in q)


def render(weeks, login):
    H = 366
    days = [d for w in weeks for d in w]
    total, current, longest, busiest, best = stats(days)
    lvl = levels(days)

    # prompt that types itself once
    pre = [("simon@stonybrook", GREEN, 700), (":", FG), ("~", BLUE, 700), ("$ ", FG)]
    cmd = f"python3 contrib.py --user {login}"
    x0 = 18 + sum(len(p[0]) for p in pre)*CW
    n = len(cmd)
    dur, begin = n/24, 0.4
    vals = ";".join(f"{i*CW:.1f}" for i in range(n + 1))
    xs = ";".join(f"{x0 + i*CW:.1f}" for i in range(n + 1))
    kts = ";".join(f"{i/n:.4f}" for i in range(n + 1))
    t1 = begin + dur + 0.35
    s = [line(18, 30, pre),
         f'<clipPath id="ty"><rect x="{x0 - 1:.1f}" y="17" width="0" height="18"><animate attributeName="width" '
         f'values="{vals}" keyTimes="{kts}" dur="{dur:.2f}s" begin="{begin}s" calcMode="discrete" fill="freeze"/></rect></clipPath>',
         f'<g clip-path="url(#ty)">{mono(x0, 30, cmd, FG, 13, cw=CW)}</g>',
         f'<rect x="{x0:.1f}" y="19" width="7.2" height="14" fill="{FG}"><animate attributeName="x" values="{xs}" '
         f'keyTimes="{kts}" dur="{dur:.2f}s" begin="{begin}s" calcMode="discrete" fill="freeze"/>'
         f'<set attributeName="opacity" to="0" begin="{t1 - 0.1:.2f}s"/></rect>']

    out = [line(18, 56, [("[contrib.py] ", AQUA), (f"{total:,}", FG0, 700), (" contributions in the last year", FG),
                         ("  ·  streak ", GREY), (f"{current}d", FG0, 700), (f" (best {longest}d)", GREY),
                         ("  ·  busiest ", GREY), (busiest, FG0, 700)], 12, 7.2)]

    # calendar heatmap
    gx, gy, pitch, cell = 60, 94, 16, 12.5
    last_month = None
    for wi, week in enumerate(weeks):
        month = week[0][0].month
        if month != last_month and week[0][0].day <= 7:
            out.append(mono(gx + wi*pitch, gy - 8, week[0][0].strftime("%b"), GREY, 10))
        last_month = month
        for day, c, wd in week:
            out.append(f'<rect class="c" x="{gx + wi*pitch}" y="{gy + wd*pitch}" width="{cell}" height="{cell}" rx="2" '
                       f'fill="{LEVELS[lvl(c)]}" style="animation-delay:{t1 + wi*0.018:.2f}s">'
                       f'<title>{esc(day)} · {int(c)}</title></rect>')
    for wd in (1, 3, 5):
        out.append(mono(gx - 10, gy + wd*pitch + 10, WEEKDAYS[wd], GREY, 10, anchor="end"))
    ly = gy + 7*pitch + 16
    right = gx + len(weeks)*pitch - 3.5
    out.append(mono(right - 5*pitch - 8, ly, "less", GREY, 10, anchor="end"))
    for i, colr in enumerate(LEVELS):
        out.append(f'<rect x="{right - (5 - i)*pitch + 3.5:.1f}" y="{ly - 10}" width="{cell}" height="{cell}" rx="2" fill="{colr}"/>')
    out.append(mono(right + 6, ly, "more", GREY, 10))
    out.append(line(gx, ly, [("max ", GREY), (str(best[1]), FG0), (f" on {best[0]:%Y-%m-%d}", GREY)], 10, 6.2))

    # last 31 days
    recent = days[-31:]
    cx0, cy0, cw_, ch_ = gx, ly + 34, right - gx, 82
    top = max(1, max(c for _, c, _ in recent))
    pts = [(cx0 + i/max(1, len(recent) - 1)*cw_, cy0 + ch_ - c/top*ch_) for i, (_, c, _) in enumerate(recent)]
    out.append(line(cx0, cy0 - 10, [("last 31 days", FG4)], 11, 6.6))
    for q in range(3):
        y = cy0 + ch_*q/2
        out.append(f'<line x1="{cx0}" x2="{cx0 + cw_:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{BG2}"/>')
    out.append(mono(cx0 - 10, cy0 + 4, str(top), GREY, 10, anchor="end"))
    out.append(mono(cx0 - 10, cy0 + ch_ + 4, "0", GREY, 10, anchor="end"))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f} {cy0 + ch_}L" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + f"L{pts[-1][0]:.1f} {cy0 + ch_}Z"
    d_start = t1 + len(weeks)*0.018
    out.append(f'<path class="ar" d="{area}" fill="url(#gf)" style="animation-delay:{d_start + 0.6:.2f}s"/>')
    out.append(f'<polyline class="ln" pathLength="1" points="{poly}" fill="none" stroke="{GREEN}" stroke-width="2" '
               f'stroke-linejoin="round" style="animation-delay:{d_start:.2f}s"/>')
    out.append(f'<g class="ar" style="animation-delay:{d_start + 0.8:.2f}s">'
               + "".join(f'<rect x="{x - 1.5:.1f}" y="{y - 1.5:.1f}" width="3" height="3" fill="{FG0}"/>' for x, y in pts) + "</g>")
    last = len(recent) - 1
    for i in (0, 15, 30):
        if i <= last:
            out.append(mono(pts[i][0], cy0 + ch_ + 16, f"{recent[i][0]:%m-%d}",
                            GREY, 10, anchor="middle" if 0 < i < last else ("start" if i == 0 else "end")))

    css = """
.o{animation:show .35s ease-out both}.c{animation:show .4s ease-out both}.ar{animation:show .6s ease-out both}
@keyframes show{from{opacity:0}to{opacity:1}}
.ln{stroke-dasharray:1 1;stroke-dashoffset:1;animation:ln 1.4s ease-out both}
@keyframes ln{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
"""
    label = f"{total} contributions in the last year; current streak {current} days, longest {longest} days"
    return "".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-label="{esc(label)}" font-family="{FONT}">',
        f"<style>{css}</style>",
        f'<defs><clipPath id="card"><rect width="{W}" height="{H}" rx="8"/></clipPath>'
        f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN}" stop-opacity=".28"/>'
        f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient></defs>',
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{BG}"/>',
        "".join(s), f'<g class="o" style="animation-delay:{t1:.2f}s">{"".join(out)}</g>', "</g></svg>"])


def write_atomic(path, text):
    """Write to a temp file then rename, so a failed run never leaves a half-written SVG."""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--demo"]
    if len(args) != 2:
        raise SystemExit(__doc__)
    login, path = args
    if not LOGIN_RE.match(login):
        raise SystemExit(f"invalid GitHub username: {login!r}")
    if not path.endswith(".svg"):
        raise SystemExit("output path must end in .svg")
    weeks = demo() if "--demo" in sys.argv else fetch(login)
    write_atomic(path, render(weeks, login))
    print(f"wrote {path}")
