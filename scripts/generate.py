#!/usr/bin/env python3
"""Generates the terminal profile SVGs. Usage: python3 scripts/generate.py .   (needs numpy)"""
import math, os, sys
import numpy as np

OUT = sys.argv[1]
A = os.path.join(OUT, "assets")
os.makedirs(A, exist_ok=True)

# ------------------------------------------------------------ gruvbox dark
BG, BG1, BG2, BG3, BG4 = "#1d2021", "#282828", "#3c3836", "#504945", "#665c54"
FG, FG0, FG2, FG4, GREY = "#ebdbb2", "#fbf1c7", "#d5c4a1", "#a89984", "#928374"
RED, GREEN, YELLOW, BLUE, PURPLE, AQUA, ORANGE = "#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c", "#fe8019"
RED_D, GREEN_D, YELLOW_D, BLUE_D, PURPLE_D, AQUA_D, ORANGE_D = "#cc241d", "#98971a", "#d79921", "#458588", "#b16286", "#689d6a", "#d65d0e"
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
SEED = 1729
W = 1000
USER, HOST = "simon", "stonybrook"
CW = 7.8          # glyph advance used for 13px text
CWS = 7.2         # glyph advance used for 12px text


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def lerp_hex(a, b, t):
    c = hexrgb(a)*(1 - t) + hexrgb(b)*t
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)


def ramp(stops, t):
    t = min(max(t, 0.0), 1.0)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp_hex(c0, c1, (t - t0)/(t1 - t0) if t1 > t0 else 0)
    return stops[-1][1]


def open_svg(w, h, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(label)}" font-family="{FONT}">')


def frame_bg(w, h):
    return (f'<defs><clipPath id="card"><rect width="{w}" height="{h}" rx="8"/></clipPath></defs>'
            f'<g clip-path="url(#card)"><rect width="{w}" height="{h}" fill="{BG}"/>')


BASE_CSS = """
.o{animation:show .35s ease-out both}
@keyframes show{from{opacity:0}to{opacity:1}}
.blink{animation:blink 1.06s step-end infinite}
@keyframes blink{50%{opacity:0}}
"""


def mono(x, y, s, fill, size=13, cw=None, anchor=None, weight=None, extra=""):
    """With cw every glyph gets its own x, so layout never depends on the installed font."""
    attrs = f' font-size="{size}" fill="{fill}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    if cw:
        keep = [(i, ch) for i, ch in enumerate(s) if ch != " "]
        if not keep:
            return ""
        xs = " ".join(f"{x + i*cw:.1f}".rstrip("0").rstrip(".") for i, _ in keep)
        return f'<text x="{xs}" y="{y}"{attrs}{extra}>{esc("".join(c for _, c in keep))}</text>'
    return f'<text x="{x}" y="{y}"{attrs}{extra}>{esc(s)}</text>'


def line(x, y, parts, size=13, cw=CW):
    """parts: (text, colour[, weight]) laid out on a fixed character grid."""
    out, col = [], 0
    for p in parts:
        text, color = p[0], p[1]
        weight = p[2] if len(p) > 2 else None
        out.append(mono(round(x + col*cw, 1), y, text, color, size, cw=cw, weight=weight))
        col += len(text)
    return "".join(out)


def prompt(x, y, path, cmd, begin, cps=24, uid="p"):
    """Shell prompt whose command types itself out once. Returns (svg, time the output should appear)."""
    pre = [(f"{USER}@{HOST}", GREEN, 700), (":", FG), (path, BLUE, 700), ("$ ", FG)]
    s = line(x, y, pre)
    x0 = x + sum(len(p[0]) for p in pre)*CW
    n = len(cmd)
    dur = n/cps
    vals = ";".join(f"{i*CW:.1f}" for i in range(n + 1))
    xs = ";".join(f"{x0 + i*CW:.1f}" for i in range(n + 1))
    kts = ";".join(f"{i/n:.4f}" for i in range(n + 1))
    s += (f'<clipPath id="{uid}"><rect x="{x0 - 1:.1f}" y="{y - 13}" width="0" height="18">'
          f'<animate attributeName="width" values="{vals}" keyTimes="{kts}" dur="{dur:.2f}s" begin="{begin:.2f}s" '
          f'calcMode="discrete" fill="freeze"/></rect></clipPath>'
          f'<g clip-path="url(#{uid})">{mono(x0, y, cmd, FG, 13, cw=CW)}</g>'
          f'<rect x="{x0:.1f}" y="{y - 11}" width="{CW - 0.6:.1f}" height="14" fill="{FG}">'
          f'<animate attributeName="x" values="{xs}" keyTimes="{kts}" dur="{dur:.2f}s" begin="{begin:.2f}s" '
          f'calcMode="discrete" fill="freeze"/><set attributeName="opacity" to="0" begin="{begin + dur + 0.25:.2f}s"/></rect>')
    return s, begin + dur + 0.35


def idle_prompt(x, y, path="~"):
    pre = [(f"{USER}@{HOST}", GREEN, 700), (":", FG), (path, BLUE, 700), ("$ ", FG)]
    x0 = x + sum(len(p[0]) for p in pre)*CW
    return line(x, y, pre) + f'<rect class="blink" x="{x0:.1f}" y="{y - 11}" width="{CW - 0.6:.1f}" height="14" fill="{FG}"/>'


def tmux(w, y, active):
    h, cw, size = 22, CWS, 12
    s = f'<rect y="{y}" width="{w}" height="{h}" fill="{BG2}"/>'
    lab = " its-Simy "
    s += f'<rect y="{y}" width="{len(lab)*cw:.1f}" height="{h}" fill="{YELLOW}"/>' + line(0, y + 15, [(lab, BG, 700)], size, cw)
    x = len(lab)*cw + 6
    for i, name in enumerate(["neofetch", "stack", "research", "activity"]):
        t = f" {i + 1}:{name}{'*' if i == active else ' '} "
        if i == active:
            s += f'<rect x="{x:.1f}" y="{y}" width="{len(t)*cw:.1f}" height="{h}" fill="{BG3}"/>'
            s += line(x, y + 15, [(t, YELLOW, 700)], size, cw)
        else:
            s += line(x, y + 15, [(t, FG4)], size, cw)
        x += len(t)*cw
    r2, r1 = f" {HOST} ", " seed 1729 "
    x2 = w - len(r2)*cw
    x1 = x2 - len(r1)*cw
    s += f'<rect x="{x1:.1f}" y="{y}" width="{len(r1)*cw:.1f}" height="{h}" fill="{BG3}"/>' + line(x1, y + 15, [(r1, FG)], size, cw)
    s += f'<rect x="{x2:.1f}" y="{y}" width="{len(r2)*cw:.1f}" height="{h}" fill="{FG4}"/>' + line(x2, y + 15, [(r2, BG, 700)], size, cw)
    return s


def frames_css(cls, n, period):
    return (f".{cls}{{opacity:0;animation:{cls} {period:.2f}s step-end infinite}}"
            f"@keyframes {cls}{{0%{{opacity:1}}{100/n:.4f}%{{opacity:0}}100%{{opacity:0}}}}")


def frame_delay(i, n, dt):
    return -((n - i) % n)*dt


# ============================================================== shared model
def iv_fn(k, T, ph):
    tp = np.power(T, 0.3)
    atm = 0.185 + 0.045*(1 - np.exp(-T/0.7)) + 0.03*np.exp(-T/0.4)*np.sin(ph)
    skew = -(0.09 + 0.025*np.cos(ph))/tp
    curv = (0.38 + 0.08*np.sin(ph + 1.1))/tp
    return atm + skew*k + curv*k*k


ATM3M = float(iv_fn(0.0, 0.25, 0.0))
MU, NPATH, NSTEP, S0 = 0.07, 2000, 252, 100.0
sig = round(ATM3M, 4)
rng = np.random.default_rng(SEED)
dt = 1/NSTEP
Z = rng.standard_normal((NPATH, NSTEP))
logS = np.cumsum((MU - 0.5*sig*sig)*dt + sig*math.sqrt(dt)*Z, axis=1)
PATHS = S0*np.exp(np.hstack([np.zeros((NPATH, 1)), logS]))
ST = PATHS[:, -1]
RET = ST/S0 - 1
Q05 = np.quantile(RET, 0.05)
MC = dict(mean=float(ST.mean()), sd=float(ST.std()), med=float(np.median(ST)), pup=float((ST > S0).mean()),
          var95=float(-Q05), es95=float(-RET[RET <= Q05].mean()),
          skew=float(((ST - ST.mean())**3).mean()/ST.std()**3),
          kurt=float(((ST - ST.mean())**4).mean()/ST.std()**4 - 3))


# ================================================================== HERO
def catmull(P, n):
    P = np.vstack([P[0], P, P[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5*((2*p1) + (-p0 + p2)*t + (2*p0 - 5*p1 + 4*p2 - p3)*t*t + (-p0 + 3*p1 - 3*p2 + p3)*t**3))
    out.append(P[-2])
    return np.array(out)


def sculpture(bx0, by0, bw, bh, NF, DT):
    """A surface of revolution drawn with flowing text, perspective-scaled glyphs, seamless loop."""
    WORD, BIN, L = "its-Simy", "01010011", 8
    P = np.array([(0.86, -0.93), (0.60, -0.87), (0.38, -0.73), (0.24, -0.47), (0.17, -0.15), (0.18, 0.20),
                  (0.28, 0.52), (0.50, 0.82), (0.80, 0.94), (1.03, 0.84), (1.13, 0.60), (1.14, 0.22), (1.13, -0.16),
                  (1.12, -0.50)])
    NS = 60
    prof = catmull(P, NS)
    seg = np.sqrt(((prof[1:] - prof[:-1])**2).sum(1))
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    s_bin = cum[3*NS + NS//2]
    M = 28
    ds = total/54
    EL, D = math.radians(27), 3.1

    def proj(x, y, z):
        y2 = y*math.cos(EL) + z*math.sin(EL)
        d = z*math.cos(EL) - y*math.sin(EL)
        f = D/(D + d)
        return x*f, y2*f, f

    def points(fi):
        o = fi/NF*L*ds
        th = fi/NF*2*math.pi/M
        pts = []
        for m in range(M):
            phi = 2*math.pi*m/M + th + 0.11
            for j in range(-L, int(total/ds) + 2):
                s = j*ds + o
                if s < 0 or s > total:
                    continue
                r = np.interp(s, cum, prof[:, 0])
                y = np.interp(s, cum, prof[:, 1])
                px, py, f = proj(r*math.cos(phi), y, r*math.sin(phi))
                fade = min(1.0, 0.3 + s/0.25)*min(1.0, 0.15 + (total - s)/0.3)
                pts.append((px, py, f, (BIN if s < s_bin else WORD)[j % L], s < s_bin, fade))
        return pts

    p0 = points(0)
    xs = [p[0] for p in p0]; ys = [p[1] for p in p0]; fs = [p[2] for p in p0]
    fmin, fmax = min(fs), max(fs)
    S = min((bw - 30)/(max(xs) - min(xs)), (bh - 30)/(max(ys) - min(ys)))
    cx = bx0 + bw/2 - (max(xs) + min(xs))/2*S
    cy = by0 + bh/2 + (max(ys) + min(ys))/2*S

    cream = [(0, BG2), (0.35, BG4), (0.6, FG4), (0.85, FG), (1, FG0)]
    green = [(0, BG3), (0.25, "#6f7020"), (0.55, GREEN_D), (1, "#dfe25a")]
    out = []
    for fi in range(NF):
        buckets = {}
        for px, py, f, ch, isbin, fade in points(fi):
            b = (f - fmin)/(fmax - fmin)
            lvl = int(round(b*fade*9))
            size = round(7.5*f**1.75*2)/2
            key = (lvl, size, isbin)
            X = round(cx + px*S)
            Y = round(cy - py*S)
            buckets.setdefault(key, []).append((X, Y, ch))
        g = []
        for (lvl, size, isbin) in sorted(buckets, key=lambda k: (k[0], k[1])):
            if lvl == 0:
                continue
            items = buckets[(lvl, size, isbin)]
            col = ramp(green if isbin else cream, lvl/9)
            g.append(f'<text x="{" ".join(str(i[0]) for i in items)}" y="{" ".join(str(i[1]) for i in items)}" '
                     f'font-size="{size:g}" fill="{col}">{esc("".join(i[2] for i in items))}</text>')
        out.append(f'<g class="fr" style="animation-delay:{frame_delay(fi, NF, DT):.2f}s">{"".join(g)}</g>')
    return "".join(out)


def hero():
    H = 568
    NF, DT = 20, 0.13
    p1, t1 = prompt(18, 30, "~", "neofetch", 0.5, cps=14, uid="t1")
    art = sculpture(14, 40, 540, 470, NF, DT)

    ix, iy = 572, 82
    info = line(ix, iy, [(USER, YELLOW, 700), ("@", FG), (HOST, YELLOW, 700)])
    info += line(ix, iy + 20, [("-"*16, FG)])
    fields = [("Name", "Simon Ramirez"), ("School", "Stony Brook University"), ("Major", "Computer Science"),
              ("Focus", "Finance, Backend Systems"), ("Languages", "Java, Python, JavaScript"),
              ("Frontend", "React, Tailwind CSS, HTML, CSS"), ("Tools", "Git, GitHub, VS Code"),
              ("GitHub", "its-Simy"), ("LinkedIn", "simon-ramirezcs"), ("Email", "simon.ramirez@stonybrook.edu")]
    for j, (k_, v_) in enumerate(fields):
        info += line(ix, iy + 46 + j*24, [(k_ + ": ", YELLOW, 700), (v_, FG)])
    by = iy + 46 + len(fields)*24 + 8
    for row, cols in enumerate([[BG1, RED_D, GREEN_D, YELLOW_D, BLUE_D, PURPLE_D, AQUA_D, FG4],
                                [GREY, RED, GREEN, YELLOW, BLUE, PURPLE, AQUA, FG]]):
        for c, colr in enumerate(cols):
            info += f'<rect x="{ix + c*3*CW:.1f}" y="{by + row*20}" width="{3*CW:.1f}" height="20" fill="{colr}"/>'

    css = BASE_CSS + frames_css("fr", NF, NF*DT)
    s = [open_svg(W, H, "Simon Ramirez — terminal profile: neofetch output beside an animated text sculpture"),
         f"<style>{css}</style>", frame_bg(W, H),
         p1,
         f'<g class="o" style="animation-delay:{t1:.2f}s">{art}</g>',
         f'<g class="o" style="animation-delay:{t1 + 0.15:.2f}s">{info}</g>',
         f'<g class="o" style="animation-delay:{t1 + 0.4:.2f}s">{idle_prompt(18, 530)}</g>',
         tmux(W, H - 22, 0), "</g></svg>"]
    return "".join(s)


# ============================================================== RESEARCH
def surface_block(X0, Y0, PW, PH, rx, NF, DUR):
    NK, NT = 21, 13
    ku = np.linspace(-0.3, 0.3, NK)
    sv = np.linspace(math.sqrt(0.08), math.sqrt(2.0), NT)
    KK, SS = np.meshgrid(ku, sv)                 # rows: maturity (front = short), cols: strike
    TT = SS*SS
    XS, YS, ZH = 1.75, 1.0, 1.25
    Xd = KK/0.3*XS
    Yd = (2*(SS - sv[0])/(sv[-1] - sv[0]) - 1)*YS
    phases = [2*math.pi*f/NF for f in range(NF)]
    ivs = [iv_fn(KK, TT, ph) for ph in phases]
    lo = min(v.min() for v in ivs)
    hi = max(v.max() for v in ivs)
    EL = math.radians(27)
    yaws = [math.radians(-30 + 11*math.sin(2*math.pi*f/NF)) for f in range(NF)]
    HEAT = [(0, BLUE_D), (0.22, AQUA), (0.45, GREEN), (0.65, YELLOW), (0.82, ORANGE), (1, RED)]

    def project(X, Y, Zz, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        x1 = X*c - Y*s
        y1 = X*s + Y*c
        z2 = y1*math.sin(EL) + Zz*math.cos(EL)
        d = y1*math.cos(EL) - Zz*math.sin(EL)
        f = 4.0/(4.0 + d)
        return x1*f, z2*f, d

    zb = -ZH/2
    proj = []
    bxs, bys = [], []
    for f in range(NF):
        tn = (ivs[f] - lo)/(hi - lo)
        px, py, d = project(Xd, Yd, (tn - 0.5)*ZH, yaws[f])
        proj.append((px, py, d, tn))
        bxs += [px.min(), px.max()]; bys += [py.min(), py.max()]
        for X in (-XS, XS):
            for Y in (-YS, YS):
                for Zc in ((zb, -zb) if Y > 0 else (zb,)):
                    qx, qy, _ = project(X, Y, Zc, yaws[f])
                    bxs.append(qx); bys.append(qy)
    S = min((PW - 70)/(max(bxs) - min(bxs)), (PH - 50)/(max(bys) - min(bys)))
    cx = X0 + PW/2 - (max(bxs) + min(bxs))/2*S
    cy = Y0 + 8 + PH/2 + (max(bys) + min(bys))/2*S

    def P(px, py):
        return f"{cx + px*S:.1f},{cy - py*S:.1f}"

    def anim(attr, vals):
        vals = vals + [vals[0]]
        return f'<animate attributeName="{attr}" values="{";".join(vals)}" dur="{DUR}s" repeatCount="indefinite"/>'

    out = []
    # floor grid + back walls
    def gl(p0, p1, color, width=1, dash=None):
        vals = []
        for f in range(NF):
            a = project(*p0, yaws[f]); b = project(*p1, yaws[f])
            vals.append(f"{P(a[0], a[1])} {P(b[0], b[1])}")
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{vals[0]}" fill="none" stroke="{color}" stroke-width="{width}"{da}>{anim("points", vals)}</polyline>'
    for X in np.linspace(-XS, XS, 7):
        out.append(gl((X, -YS, zb), (X, YS, zb), BG2))
    for Y in np.linspace(-YS, YS, 5):
        out.append(gl((-XS, Y, zb), (XS, Y, zb), BG2))
    for X in (-XS, XS):
        out.append(gl((X, YS, zb), (X, YS, -zb), BG3, 1, "2 3"))
    out.append(gl((-XS, YS, -zb), (XS, YS, -zb), BG3, 1, "2 3"))

    # quads, far to near
    quads = []
    for a in range(NT - 1):
        for b in range(NK - 1):
            depth = np.mean([proj[f][2][a:a + 2, b:b + 2].mean() for f in range(NF)])
            quads.append((depth, a, b))
    quads.sort(reverse=True)
    for _, a, b in quads:
        pts, fills, strokes = [], [], []
        for f in range(NF):
            px, py, d, tn = proj[f]
            idx = [(a, b), (a, b + 1), (a + 1, b + 1), (a + 1, b)]
            pts.append(" ".join(P(px[i], py[i]) for i in idx))
            t = float(np.mean([tn[i] for i in idx]))
            c = ramp(HEAT, t)
            strokes.append(c)
            fills.append(lerp_hex(c, BG, 0.78))
        out.append(f'<polygon points="{pts[0]}" fill="{fills[0]}" stroke="{strokes[0]}" stroke-width=".9" stroke-linejoin="round">'
                   f'{anim("points", pts)}{anim("fill", fills)}{anim("stroke", strokes)}</polygon>')

    # axis labels that ride with the rotation
    def lab(p, text, dx, dy, anchor="middle"):
        xs_, ys_ = [], []
        for f in range(NF):
            q = project(*p, yaws[f])
            xs_.append(f"{cx + q[0]*S + dx:.1f}"); ys_.append(f"{cy - q[1]*S + dy:.1f}")
        return (f'<text x="{xs_[0]}" y="{ys_[0]}" font-size="11" fill="{GREY}" text-anchor="{anchor}">{esc(text)}'
                f'{anim("x", xs_)}{anim("y", ys_)}</text>')
    out += [lab((0, -YS, zb), "strike K/S", 0, 18), lab((-XS, -YS, zb), "0.74", 0, 16), lab((XS, -YS, zb), "1.35", 0, 16),
            lab((XS, -YS, zb), "1M", 14, 4, "start"), lab((XS, YS, zb), "2Y", 14, 4, "start"),
            lab((XS, 0, zb), "maturity", 14, 4, "start"), lab((-XS, YS, -zb), "σ", 0, -8)]

    # right-hand stdout: frame-synced numbers + animated slices
    log = line(rx, Y0 + 14, [("[vol_surface] ", AQUA), ("quadratic smile, T^-0.3 decay", GREY)], 12, CWS)
    log += line(rx, Y0 + 32, [("grid ", GREY), ("21x13", FG), ("  K/S ", GREY), ("0.74-1.35", FG), ("  T ", GREY), ("1M-2Y", FG)], 12, CWS)
    fr = []
    for f in range(NF):
        atm = float(iv_fn(0.0, 0.25, phases[f]))
        sk = float(iv_fn(math.log(0.9), 0.25, phases[f]) - iv_fn(math.log(1.1), 0.25, phases[f]))
        tm = float(iv_fn(0.0, 0.25, phases[f]) - iv_fn(0.0, 2.0, phases[f]))
        rows = [("frame", f"{f + 1:02d}/{NF}", FG), ("yaw", f"{math.degrees(yaws[f]):+.1f}°", FG),
                ("atm_3m", f"{atm:.4f}", YELLOW), ("skew_3m", f"{sk:+.4f}", AQUA if sk > 0 else RED),
                ("term", f"{tm:+.4f}", AQUA if tm > 0 else RED)]
        body = "".join(line(rx, Y0 + 60 + j*19, [(f"{k_:<9}", GREY), (v_, c_)], 12, CWS) for j, (k_, v_, c_) in enumerate(rows))
        fr.append(f'<g class="sf" style="animation-delay:{frame_delay(f, NF, DUR/NF):.2f}s">{body}</g>')
    log += "".join(fr)

    def mini(x0, y0, w, h, title, xs_list, ys_list, ylo, yhi, xl, xr):
        g = "".join(f'<line x1="{x0}" x2="{x0 + w}" y1="{y0 + h*q/4:.1f}" y2="{y0 + h*q/4:.1f}" stroke="{BG2}"/>' for q in range(5))
        g += line(x0, y0 - 10, [(title, FG4)], 11, 6.6)
        g += mono(x0, y0 + h + 14, xl, GREY, 10)
        g += mono(x0 + w, y0 + h + 14, xr, GREY, 10, anchor="end")
        vals = []
        for xs_, ys_ in zip(xs_list, ys_list):
            vals.append(" ".join(f"{x0 + (a - xs_[0])/(xs_[-1] - xs_[0])*w:.1f},{y0 + h - (b - ylo)/(yhi - ylo)*h:.1f}" for a, b in zip(xs_, ys_)))
        g += f'<polyline points="{vals[0]}" fill="none" stroke="{YELLOW}" stroke-width="1.8">{anim("points", vals)}</polyline>'
        return g
    kx = np.linspace(-0.3, 0.3, 25)
    tx = np.linspace(math.sqrt(0.08), math.sqrt(2.0), 25)
    sm = [iv_fn(kx, 0.25, ph) for ph in phases]
    te = [iv_fn(0.0, tx**2, ph) for ph in phases]
    lo_s, hi_s = min(v.min() for v in sm) - 0.01, max(v.max() for v in sm) + 0.01
    lo_t, hi_t = min(v.min() for v in te) - 0.01, max(v.max() for v in te) + 0.01
    log += mini(rx, Y0 + 186, 160, 120, "smile @ 3M", [np.exp(kx)]*NF, sm, lo_s, hi_s, "0.74", "1.35")
    log += mini(rx + 186, Y0 + 186, 160, 120, "term @ ATM", [tx]*NF, te, lo_t, hi_t, "1M", "2Y")
    # heat legend
    gid = "heat"
    stops = "".join(f'<stop offset="{t}" stop-color="{c}"/>' for t, c in HEAT)
    log += f'<linearGradient id="{gid}" x1="0" x2="1">{stops}</linearGradient>'
    log += f'<rect x="{rx}" y="{Y0 + PH - 26}" width="346" height="6" fill="url(#{gid})"/>'
    log += mono(rx, Y0 + PH - 6, f"σ {lo*100:.1f}%", GREY, 10)
    log += mono(rx + 346, Y0 + PH - 6, f"{hi*100:.1f}%", GREY, 10, anchor="end")
    return "".join(out), log


def mc_block(X0, Y0, start):
    px0, py0, pw, ph = X0 + 40, Y0 + 14, 560, 318
    hx0, hw = px0 + pw + 12, 110
    sx0 = hx0 + hw + 22
    shown = PATHS[:64]
    lo = max(math.floor(min(np.quantile(PATHS, 0.002), shown.min())/10)*10, 40)
    hi = min(math.ceil(max(np.quantile(PATHS, 0.998), shown.max())/10)*10, 220)

    def Y(v):
        return py0 + ph - (min(max(v, lo), hi) - lo)/(hi - lo)*ph

    def X(t):
        return px0 + t/NSTEP*pw

    idx = list(range(0, NSTEP + 1, 3))
    if idx[-1] != NSTEP:
        idx.append(NSTEP)

    def pathd(series):
        return "M" + "L".join(f"{X(t):.1f} {Y(series[t]):.1f}" for t in idx)

    g = ""
    for v in range(int(lo), int(hi) + 1, 20):
        g += f'<line x1="{px0}" x2="{hx0 + hw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{BG2}"/>'
        g += mono(px0 - 8, Y(v) + 4, f"{v}", GREY, 10, anchor="end")
    for t, lab in ((0, "0"), (63, "3M"), (126, "6M"), (189, "9M"), (252, "12M")):
        g += f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{py0}" y2="{py0 + ph}" stroke="{BG2}"/>'
        g += mono(X(t), py0 + ph + 14, lab, GREY, 10, anchor="middle")
    for i, p in enumerate(shown):
        col = AQUA if p[-1] > S0 else RED
        g += (f'<path class="p" pathLength="1" d="{pathd(p)}" stroke="{col}" stroke-opacity=".5" '
              f'style="animation-delay:{start + i*0.012:.3f}s"/>')
    mean = PATHS.mean(0)
    q05, q95 = np.quantile(PATHS, 0.05, axis=0), np.quantile(PATHS, 0.95, axis=0)
    for ser, col, wd in ((q05, YELLOW, 1.6), (q95, YELLOW, 1.6), (mean, FG0, 2)):
        g += f'<path class="p" pathLength="1" d="{pathd(ser)}" stroke="{col}" stroke-width="{wd}" style="animation-delay:{start:.2f}s"/>'
    g += f'<line class="cur" x1="{px0}" x2="{px0}" y1="{py0}" y2="{py0 + ph}" stroke="{YELLOW}" stroke-width="1.5" style="animation-delay:{start:.2f}s"/>'

    bw = 5
    edges_ = np.arange(lo, hi + bw, bw)
    cnt, _ = np.histogram(ST[(ST >= lo) & (ST < hi)], bins=edges_)
    for b_, c in enumerate(cnt):
        if c == 0:
            continue
        y1, y0 = Y(edges_[b_]), Y(edges_[b_ + 1])
        pat = "pa" if edges_[b_] >= S0 else "pr"
        g += (f'<rect class="h" x="{hx0}" y="{y0 + 1:.1f}" width="{c/cnt.max()*hw:.1f}" height="{y1 - y0 - 1.5:.1f}" '
              f'fill="url(#{pat})" style="animation-delay:{start + b_*0.015:.3f}s"/>')
    m_ = math.log(S0) + (MU - sig*sig/2)
    vs = np.linspace(lo, hi, 120)
    dens = np.exp(-(np.log(vs) - m_)**2/(2*sig*sig))/(vs*sig*math.sqrt(2*math.pi))*NPATH*bw/cnt.max()*hw
    g += (f'<path class="dn" pathLength="1" d="M{"L".join(f"{hx0 + d_:.1f} {Y(v):.1f}" for v, d_ in zip(vs, dens))}" '
          f'fill="none" stroke="{FG}" stroke-width="1.2" style="animation-delay:{start:.2f}s"/>')
    ys0, vy = Y(S0), Y(S0*(1 - MC["var95"]))
    g += (f'<line x1="{px0}" x2="{hx0 + hw}" y1="{ys0:.1f}" y2="{ys0:.1f}" stroke="{FG}" stroke-opacity=".45" stroke-dasharray="2 4"/>'
          + mono(hx0 - 6, ys0 - 4, "S0=100", FG, 10, anchor="end")
          + f'<line x1="{hx0}" x2="{hx0 + hw}" y1="{vy:.1f}" y2="{vy:.1f}" stroke="{RED}" stroke-dasharray="3 3"/>'
          + mono(hx0 + hw, vy + 12, "VaR95", RED, 10, anchor="end"))

    stats = [("paths", f"{NPATH}", FG), ("mean", f"{MC['mean']:.2f}", FG), ("sd", f"{MC['sd']:.2f}", FG),
             ("median", f"{MC['med']:.2f}", FG), ("p(S>S0)", f"{MC['pup']*100:.1f}%", AQUA),
             ("VaR95", f"-{MC['var95']*100:.1f}%", RED), ("ES95", f"-{MC['es95']*100:.1f}%", RED),
             ("skew", f"{MC['skew']:.3f}", FG), ("ex_kurt", f"{MC['kurt']:.3f}", FG)]
    st = line(sx0, py0 + 4, [(">>> ", GREY), ("summary(S_T)", FG)], 12, CWS)
    for j, (k_, v_, c_) in enumerate(stats):
        st += (f'<g class="st" style="animation-delay:{start + j*0.06:.2f}s">'
               + line(sx0, py0 + 30 + j*21, [(f"{k_:<9}", GREY), (f"{v_:>8}", c_)], 12, CWS) + "</g>")
    st += line(sx0, py0 + 30 + len(stats)*21 + 8, [("σ ← atm_3m", GREY)], 11, 6.6)
    st += line(sx0, py0 + 30 + len(stats)*21 + 24, [("  frame 01 above", GREY)], 11, 6.6)
    legend = line(px0, py0 + ph + 34, [("━ ", AQUA), ("S_T>S0  ", GREY), ("━ ", RED), ("S_T<S0  ", GREY), ("━ ", FG0),
                                        ("mean  ", GREY), ("━ ", YELLOW), ("5/95 pct", GREY)], 11, 6.6)
    return g + st + legend, pw


def research():
    H = 892
    NF, DUR = 16, 8.0
    p1, t1 = prompt(18, 30, "~/research", "python3 vol_surface.py --animate", 0.4, uid="t1")
    surf, log = surface_block(10, 42, 600, 380, 626, NF, DUR)
    cmd2 = f"python3 monte_carlo.py --paths 2000 --sigma {sig:.4f} --seed 1729"
    p2, t2 = prompt(18, 458, "~/research", cmd2, t1 + 1.2, uid="t2")
    mc, pw = mc_block(10, 470, t2)
    CYC = 11
    css = BASE_CSS + frames_css("sf", NF, DUR) + f"""
.p{{fill:none;stroke-width:1.1;stroke-dasharray:1 1;stroke-dashoffset:1;stroke-linejoin:round;animation:draw {CYC}s linear infinite}}
@keyframes draw{{0%{{stroke-dashoffset:1;opacity:1}}30%{{stroke-dashoffset:0}}88%{{stroke-dashoffset:0;opacity:1}}95%{{opacity:0;stroke-dashoffset:0}}100%{{opacity:0;stroke-dashoffset:1}}}}
.h{{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);animation:grow {CYC}s cubic-bezier(.2,.8,.2,1) infinite}}
@keyframes grow{{0%,30%{{transform:scaleX(0);opacity:1}}40%,88%{{transform:scaleX(1);opacity:1}}95%{{opacity:0;transform:scaleX(1)}}100%{{opacity:0;transform:scaleX(0)}}}}
.dn{{stroke-dasharray:1 1;stroke-dashoffset:1;animation:dn {CYC}s linear infinite}}
@keyframes dn{{0%,38%{{stroke-dashoffset:1;opacity:1}}48%,88%{{stroke-dashoffset:0;opacity:1}}95%{{opacity:0}}100%{{opacity:0;stroke-dashoffset:1}}}}
.st{{opacity:0;animation:st {CYC}s linear infinite}}
@keyframes st{{0%,40%{{opacity:0}}44%,88%{{opacity:1}}95%,100%{{opacity:0}}}}
.cur{{opacity:0;animation:cur {CYC}s linear infinite}}
@keyframes cur{{0%{{transform:translateX(0);opacity:1}}30%{{transform:translateX({pw}px);opacity:1}}33%,100%{{transform:translateX({pw}px);opacity:0}}}}
"""
    pats = "".join(f'<pattern id="{pid}" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="3" height="3" fill="{c}"/></pattern>'
                   for pid, c in (("pa", AQUA), ("pr", RED)))
    s = [open_svg(W, H, "Research: an animated implied volatility surface and a Monte Carlo simulation of price paths"),
         f"<style>{css}</style>", frame_bg(W, H), f"<defs>{pats}</defs>",
         p1, f'<g class="o" style="animation-delay:{t1:.2f}s">{surf}{log}</g>',
         p2, f'<g class="o" style="animation-delay:{t2:.2f}s">{mc}</g>',
         tmux(W, H - 22, 2), "</g></svg>"]
    return "".join(s)


# ================================================================ SYSTEMS
def systems():
    H = 486
    P = 4
    OY = 18
    rng = np.random.default_rng(SEED)
    cx, cy, rx, ry = 500, 240 + OY, 440, 168

    def inside(x, y):
        dx, dy = (x - cx)/rx, (y - cy)/ry
        th = math.atan2(dy, dx)
        rr = 1 + 0.07*math.sin(3*th + 1) + 0.05*math.sin(5*th + 2) + 0.03*math.sin(9*th)
        return dx*dx + dy*dy <= rr*rr, math.sqrt(dx*dx + dy*dy)/rr

    nodes, tries = [], 0
    while len(nodes) < 230 and tries < 40000:
        tries += 1
        x, y = rng.uniform(cx - rx*1.1, cx + rx*1.1), rng.uniform(cy - ry*1.1, cy + ry*1.1)
        ok, rad = inside(x, y)
        if not ok:
            continue
        mind = 16 if rad > 0.82 else 24
        if all((x - a)**2 + (y - b)**2 >= mind*mind for a, b in nodes):
            nodes.append((x, y))
    nodes = np.array(nodes)
    n = len(nodes)
    D = np.sqrt(((nodes[:, None, :] - nodes[None, :, :])**2).sum(-1))
    edges = set()
    for i in range(n):
        for j in np.argsort(D[i])[1:4]:
            edges.add((min(i, j), max(i, j)))
    for _ in range(14):
        i, j = rng.integers(n, size=2)
        if i != j and D[i, j] < 260:
            edges.add((min(i, j), max(i, j)))
    deg = np.zeros(n, int)
    for i, j in edges:
        deg[i] += 1; deg[j] += 1
    lens = np.array([D[i, j] for i, j in edges])

    def line_cells(x0, y0, x1, y1):
        c0, r0, c1, r1 = int(x0//P), int(y0//P), int(x1//P), int(y1//P)
        pts = []
        dc, dr = abs(c1 - c0), -abs(r1 - r0)
        sc, sr = (1 if c0 < c1 else -1), (1 if r0 < r1 else -1)
        err = dc + dr
        while True:
            pts.append((c0, r0))
            if c0 == c1 and r0 == r1:
                break
            e2 = 2*err
            if e2 >= dr: err += dr; c0 += sc
            if e2 <= dc: err += dc; r0 += sr
        return pts

    pal = [YELLOW_D, AQUA_D, BLUE_D, GREEN_D, BG4, ORANGE_D, PURPLE_D]
    pw_ = np.array([0.30, 0.20, 0.20, 0.10, 0.10, 0.06, 0.04])
    bg = {}
    for i, j in edges:
        base = pal[rng.choice(len(pal), p=pw_)]
        for c in line_cells(*nodes[i], *nodes[j]):
            bg[c] = base if rng.random() < 0.72 else pal[rng.choice(len(pal), p=pw_)]
    for x, y in nodes:
        c0, r0 = int(x//P), int(y//P)
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if rng.random() < 0.8:
                    bg[(c0 + dc, r0 + dr)] = pal[rng.choice(len(pal), p=pw_)]

    M = {
        "its-Simy": (500, 238, 6, "core", "hub"),
        "backend": (318, 168, 5, "", "hub"),
        "frontend": (536, 356, 5, "", "hub"),
        "tooling": (712, 150, 5, "", "hub"),
        "Java": (176, 118, 4, "jvm", "leaf"),
        "Python": (196, 290, 4, "scripting", "leaf"),
        "JavaScript": (380, 318, 4, "runtime", "leaf"),
        "React": (430, 404, 4, "ui", "leaf"),
        "Tailwind": (660, 410, 4, "style", "leaf"),
        "HTML5": (752, 330, 4, "markup", "leaf"),
        "CSS3": (640, 296, 4, "style", "leaf"),
        "Git": (862, 112, 4, "vcs", "leaf"),
        "GitHub": (870, 236, 4, "remote", "leaf"),
        "VS Code": (574, 84, 4, "editor", "leaf"),
    }
    M = {k: (v[0], v[1] + OY) + v[2:] for k, v in M.items()}
    E = [("its-Simy", "backend"), ("its-Simy", "frontend"), ("its-Simy", "tooling"),
         ("backend", "frontend"), ("frontend", "tooling"), ("backend", "tooling"),
         ("backend", "Java"), ("backend", "Python"), ("frontend", "JavaScript"), ("frontend", "React"),
         ("frontend", "Tailwind"), ("frontend", "HTML5"), ("frontend", "CSS3"), ("tooling", "Git"),
         ("tooling", "GitHub"), ("tooling", "VS Code"), ("Python", "JavaScript"), ("Git", "GitHub")]

    for name, (x, y, rad, _, _) in M.items():
        c0, r0 = int(x//P), int(y//P)
        for dc in range(-rad - 3, rad + 4):
            for dr in range(-rad - 3, rad + 4):
                if dc*dc + dr*dr <= (rad + 2.5)**2:
                    bg.pop((c0 + dc, r0 + dr), None)
    fg = {}
    for a, b in E:
        xa, ya, ra = M[a][:3]
        xb, yb, rb = M[b][:3]
        for k_, c in enumerate(line_cells(xa, ya, xb, yb)):
            ca, cb = (c[0] - xa//P, c[1] - ya//P), (c[0] - xb//P, c[1] - yb//P)
            if ca[0]**2 + ca[1]**2 <= (ra + 1)**2 or cb[0]**2 + cb[1]**2 <= (rb + 1)**2:
                continue
            fg[c] = FG0 if k_ % 5 == 0 else YELLOW
            for dc, dr in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                bg.pop((c[0] + dc, c[1] + dr), None)
    for name, (x, y, rad, _, kind) in M.items():
        c0, r0 = int(x//P), int(y//P)
        for dc in range(-rad - 1, rad + 2):
            for dr in range(-rad - 1, rad + 2):
                dd = math.sqrt(dc*dc + dr*dr)
                if abs(dd - rad) < 0.6:
                    fg[(c0 + dc, r0 + dr)] = FG0 if (dc + dr) % 2 else (YELLOW if kind == "hub" else AQUA)
                elif dd < rad - 0.6:
                    fg[(c0 + dc, r0 + dr)] = (BLUE_D if kind == "hub" else AQUA_D) if (dc + dr) % 2 else BG

    def pix_paths(cells):
        by = {}
        for (c, r_), color in cells.items():
            by.setdefault(color, []).append(f"M{c*P} {r_*P}h{P}v{P}h-{P}z")
        return "".join(f'<path fill="{color}" d="{"".join(ps)}"/>' for color, ps in by.items())

    flick = [dict(), dict(), dict()]
    for k_ in list(bg.keys()):
        u = rng.random()
        if u < 0.09:
            flick[int(u/0.03)][k_] = bg.pop(k_)

    def pix_hist(x0, y0, values, nb, hcells, title, sub):
        h, _ = np.histogram(values, bins=nb)
        cells = {}
        for b_, v in enumerate(h):
            hh = int(round(v/h.max()*hcells))
            for k_ in range(hh):
                cells[(x0//P + b_*2, y0//P - k_)] = YELLOW if k_ < hh*0.6 else (ORANGE if b_ % 3 == 0 else AQUA)
        return pix_paths(cells) + line(x0, y0 + 18, [(title, GREY)], 10, 6.2) + line(x0, y0 + 30, [(sub, BG4)], 10, 6.2)

    degv = deg[deg > 0]
    glyphs = (pix_hist(28, 128, degv, max(2, degv.max() - degv.min() + 1), 12, "degree", f"μ {degv.mean():.2f}")
              + pix_hist(884, 388, lens, 16, 12, "edge len", f"μ {lens.mean():.0f}px"))

    labels = ""
    for name, (x, y, rad, sub, kind) in M.items():
        right = x < 800
        tx = x + (rad + 3)*P if right else x - (rad + 3)*P
        anchor = None if right else "end"
        size = 13 if kind == "hub" else 12
        color = YELLOW if kind == "hub" else FG0
        wlab = max(len(name)*size*0.62, len(sub)*10*0.62) + 8
        bx = tx - 4 if right else tx - wlab + 4
        labels += f'<rect x="{bx:.0f}" y="{y - 12}" width="{wlab:.0f}" height="{30 if sub else 17}" fill="{BG}" fill-opacity=".88"/>'
        labels += mono(tx, y + 2, name, color, size, anchor=anchor, weight=700)
        if sub:
            labels += mono(tx, y + 14, sub, GREY, 10, anchor=anchor)

    packets = ""
    for k_, (a, b) in enumerate(E):
        xa, ya = M[a][:2]
        xb, yb = M[b][:2]
        dur = math.hypot(xb - xa, yb - ya)/70
        for rep in range(2 if k_ < 6 else 1):
            col = FG0 if rep == 0 else AQUA
            path = f"M{xa} {ya}L{xb} {yb}" if (k_ + rep) % 2 == 0 else f"M{xb} {yb}L{xa} {ya}"
            packets += (f'<rect x="-3" y="-3" width="6" height="6" fill="{col}">'
                        f'<animateMotion path="{path}" dur="{dur:.2f}s" begin="{-rng.uniform(0, dur):.2f}s" repeatCount="indefinite"/></rect>')

    p1, t1 = prompt(18, 30, "~/stack", "python3 graph.py --knn 3 --seed 1729", 0.4, uid="t1")
    css = BASE_CSS + """
.f0{animation:fl 1.3s step-end infinite}.f1{animation:fl 1.9s step-end infinite -.6s}.f2{animation:fl .8s step-end infinite -.3s}
@keyframes fl{0%{opacity:1}40%{opacity:0}55%{opacity:1}80%{opacity:.2}}
"""
    out = (f'<g opacity=".85">{pix_paths(bg)}' + "".join(f'<g class="f{q}">{pix_paths(flick[q])}</g>' for q in range(3)) + "</g>"
           + pix_paths(fg) + packets + labels + glyphs
           + line(18, H - 34, [("[graph.py] ", AQUA), (f"{n} nodes, {len(edges)} edges, k-NN 3 · {len(M)} labelled, {len(E)} links", GREY)], 11, 6.6))
    s = [open_svg(W, H, "Stack drawn as a pixel network graph: Java and Python under backend; JavaScript, React, Tailwind, HTML5 and CSS3 under frontend; Git, GitHub and VS Code under tooling"),
         f"<style>{css}</style>", frame_bg(W, H), p1,
         f'<g class="o" style="animation-delay:{t1:.2f}s">{out}</g>',
         tmux(W, H - 22, 1), "</g></svg>"]
    return "".join(s)


# ============================================================ ACTIVITY/END
def activity():
    H = 64
    p1, t1 = prompt(18, 30, "~", "gh api users/its-Simy", 0.4, uid="t1")
    out = line(18, 52, [("# ", GREY), ("live from github.com: ", GREY), ("stats", FG), (" · ", GREY), ("streak", FG),
                        (" · ", GREY), ("contributions", FG)], 12, CWS)
    return "".join([open_svg(W, H, "gh api users/its-Simy"), f"<style>{BASE_CSS}</style>", frame_bg(W, H), p1,
                    f'<g class="o" style="animation-delay:{t1:.2f}s">{out}</g>', "</g></svg>"])


def footer():
    H = 176
    p1, t1 = prompt(18, 30, "~", "cat ~/.motto", 0.4, uid="t1")
    quote = "Simplicity reveals strength; the less you add, the more it speaks."
    out = (line(18, 58, [(quote, FG0)], 14, 8.4)
           + line(18, 80, [("  — Simon", GREY)])
           + line(18, 110, [("github.com/its-Simy", BLUE), ("  ·  ", BG4), ("linkedin.com/in/simon-ramirezcs", BLUE),
                            ("  ·  ", BG4), ("simon.ramirez@stonybrook.edu", BLUE)], 12, CWS)
           + idle_prompt(18, 140))
    return "".join([open_svg(W, H, "Footer: Simplicity reveals strength; the less you add, the more it speaks. — Simon"),
                    f"<style>{BASE_CSS}</style>", frame_bg(W, H), p1,
                    f'<g class="o" style="animation-delay:{t1:.2f}s">{out}</g>', tmux(W, H - 22, 3), "</g></svg>"])


if __name__ == "__main__":
    for name, fn in (("header.svg", hero), ("systems.svg", systems), ("research.svg", research),
                     ("activity.svg", activity), ("footer.svg", footer)):
        data = fn()
        with open(os.path.join(A, name), "w") as f:
            f.write(data)
        print(f"{name:14s} {len(data)/1024:8.1f} KB")
