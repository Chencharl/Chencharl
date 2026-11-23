#!/usr/bin/env python3
"""Generate profile assets from GitHub's own data: contribution heatmap and a by-year stats card (light + dark)."""
import json, os, sys, urllib.request, urllib.parse, datetime as dt

LOGIN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY_OWNER", "")
OUT = sys.argv[2] if len(sys.argv) > 2 else "dist"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
QUERY = """query($login:String!){ user(login:$login){ contributionsCollection{ contributionCalendar{
  totalContributions weeks{ contributionDays{ date contributionCount contributionLevel } } } } } }"""

def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-heatmap"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]["contributionsCollection"]["contributionCalendar"]

LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
THEMES = {
    "light": dict(bg="#ffffff", fg="#1f2328", muted="#59636e", cells=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]),
    "dark":  dict(bg="#0d1117", fg="#e6edf3", muted="#8b949e", cells=["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]),
}

def render(cal, theme):
    t = THEMES[theme]; weeks = cal["weeks"]
    cell, gap, left, top = 11, 3, 34, 30
    pitch = cell + gap
    w = left + len(weeks) * pitch + 10
    h = top + 7 * pitch + 36
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10">',
         f'<rect width="{w}" height="{h}" rx="6" fill="{t["bg"]}"/>',
         f'<text x="{left}" y="16" font-size="12" font-weight="600" fill="{t["fg"]}">{cal["totalContributions"]} contributions in the last year</text>']
    last_month = None
    for wi, wk in enumerate(weeks):
        x = left + wi * pitch
        for d in wk["contributionDays"]:
            date = dt.date.fromisoformat(d["date"]); y = top + date.weekday_sun() if False else None
            dow = (date.weekday() + 1) % 7  # Sunday=0
            y = top + dow * pitch
            lvl = LEVELS.index(d["contributionLevel"])
            o.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{t["cells"][lvl]}"><title>{d["contributionCount"]} on {d["date"]}</title></rect>')
        first = dt.date.fromisoformat(wk["contributionDays"][0]["date"])
        if first.month != last_month and (wi == 0 or first.day <= 7):
            if wi > 0 or first.day <= 7:
                o.append(f'<text x="{x}" y="{top-6}" fill="{t["muted"]}">{first.strftime("%b")}</text>')
            last_month = first.month
    for lbl, dow in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        o.append(f'<text x="0" y="{top + dow*pitch + 9}" fill="{t["muted"]}">{lbl}</text>')
    lx = w - 10 - 5 * pitch - 60
    ly = h - 12
    o.append(f'<text x="{lx-30}" y="{ly}" fill="{t["muted"]}">Less</text>')
    for i, c in enumerate(t["cells"]):
        o.append(f'<rect x="{lx + i*pitch}" y="{ly-9}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    o.append(f'<text x="{lx + 5*pitch + 2}" y="{ly}" fill="{t["muted"]}">More</text>')
    o.append("</svg>")
    return "\n".join(o)


YEAR_QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
  contributionsCollection(from:$from,to:$to){ contributionCalendar{ totalContributions }
  totalPullRequestContributions totalRepositoryContributions } } }"""

def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-assets"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]

def fetch_years():
    this = dt.date.today().year
    out = []
    for y in range(this - 2, this + 1):
        d = gql(YEAR_QUERY, {"login": LOGIN, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        out.append((y, d["contributionCalendar"]["totalContributions"], d["totalPullRequestContributions"], d["totalRepositoryContributions"]))
    return out

def fetch_merged_public():
    q = urllib.parse.quote(f"author:{LOGIN} is:pr is:merged is:public")
    req = urllib.request.Request(f"https://api.github.com/search/issues?q={q}&per_page=1",
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-assets"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["total_count"]

def render_stats(years, last_year_total, merged, theme):
    t = THEMES[theme]; accent = "#2F81F7" if theme == "light" else "#58a6ff"
    w, h = 420, 190
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<rect width="{w}" height="{h}" rx="6" fill="{t["bg"]}"/>',
         f'<text x="22" y="30" font-size="16" font-weight="600" fill="{accent}">Contributions by year</text>']
    mx = max(v for _, v, _, _ in years) or 1
    bar_w, gap, x0, base, hmax = 90, 40, 50, 150, 84
    for i, (y, v, prs, repos) in enumerate(years):
        x = x0 + i * (bar_w + gap)
        bh = max(3, round(hmax * v / mx))
        o.append(f'<rect x="{x}" y="{base-bh}" width="{bar_w}" height="{bh}" rx="4" fill="{accent}" opacity="{0.55 + 0.45*(i+1)/len(years):.2f}"/>')
        o.append(f'<text x="{x+bar_w/2}" y="{base-bh-6}" font-size="13" font-weight="600" text-anchor="middle" fill="{t["fg"]}">{v}</text>')
        o.append(f'<text x="{x+bar_w/2}" y="{base+16}" font-size="11" text-anchor="middle" fill="{t["muted"]}">{y}</text>')
    o.append("</svg>")
    return "\n".join(o)

def render_activity(cal, theme, days=31):
    """Area line chart of daily contributions for the last `days` days (same data as the profile calendar)."""
    t = THEMES[theme]; line = "#39d353" if theme == "dark" else "#2da44e"
    pts = [d for wk in cal["weeks"] for d in wk["contributionDays"]][-days:]
    w, h, l, r, top, bot = 900, 300, 50, 20, 44, 40
    mx = max(max(d["contributionCount"] for d in pts), 1)
    xs = [l + i * (w - l - r) / (len(pts) - 1) for i in range(len(pts))]
    ys = [h - bot - (d["contributionCount"] / mx) * (h - top - bot) for d in pts]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="11">',
         f'<rect width="{w}" height="{h}" rx="6" fill="{t["bg"]}"/>',
         f'<text x="{w/2}" y="24" font-size="15" font-weight="600" text-anchor="middle" fill="{t["fg"]}">Contributions, last {days} days</text>']
    steps = 4
    for k in range(steps + 1):
        v = round(mx * k / steps); y = h - bot - (v / mx) * (h - top - bot)
        o.append(f'<line x1="{l}" y1="{y:.1f}" x2="{w-r}" y2="{y:.1f}" stroke="{t["muted"]}" stroke-opacity="0.25" stroke-dasharray="3 4"/>')
        o.append(f'<text x="{l-8}" y="{y+4:.1f}" text-anchor="end" fill="{t["muted"]}">{v}</text>')
    path = " ".join(f'{"M" if i==0 else "L"}{x:.1f},{y:.1f}' for i,(x,y) in enumerate(zip(xs,ys)))
    o.append(f'<path d="{path} L{xs[-1]:.1f},{h-bot} L{xs[0]:.1f},{h-bot} Z" fill="{line}" fill-opacity="0.18"/>')
    o.append(f'<path d="{path}" fill="none" stroke="{line}" stroke-width="2.5" stroke-linejoin="round"/>')
    for i,(x,y,d) in enumerate(zip(xs,ys,pts)):
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{t["bg"]}" stroke="{line}" stroke-width="2"><title>{d["contributionCount"]} on {d["date"]}</title></circle>')
        if i % 3 == 0 or i == len(pts)-1:
            o.append(f'<text x="{x:.1f}" y="{h-bot+16}" text-anchor="middle" fill="{t["muted"]}">{dt.date.fromisoformat(d["date"]).strftime("%b %d")}</text>')
    o.append("</svg>")
    return "\n".join(o)

LANG_QUERY = """query($login:String!,$after:String){ user(login:$login){ repositories(first:100, after:$after, ownerAffiliations:OWNER, isFork:false){
  pageInfo{ hasNextPage endCursor } nodes{ name isPrivate languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } } } } }"""
SKIP = {"Jupyter Notebook", "TeX", "HTML", "CSS", "SCSS", "Makefile", "Dockerfile"}

def fetch_languages():
    after, bytes_by, repos_by, colors, n = None, {}, {}, {}, 0
    while True:
        d = gql(LANG_QUERY, {"login": LOGIN, "after": after})["user"]["repositories"]
        for r in d["nodes"]:
            n += 1
            for e in r["languages"]["edges"]:
                nm = e["node"]["name"]
                if nm in SKIP: continue
                bytes_by[nm] = bytes_by.get(nm, 0) + e["size"]
                repos_by[nm] = repos_by.get(nm, 0) + 1
                colors[nm] = e["node"]["color"] or "#8b949e"
        if not d["pageInfo"]["hasNextPage"]: break
        after = d["pageInfo"]["endCursor"]
    return n, bytes_by, repos_by, colors

def render_languages(n, bytes_by, repos_by, colors, theme, top=7):
    t = THEMES[theme]; accent = "#2F81F7" if theme == "light" else "#58a6ff"
    items = sorted(bytes_by.items(), key=lambda kv: -kv[1])[:top]
    total = sum(bytes_by.values()) or 1
    w, row, top_y = 420, 22, 52
    h = top_y + row * len(items) + 16
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="12">',
         f'<rect width="{w}" height="{h}" rx="6" fill="{t["bg"]}"/>',
         f'<text x="22" y="30" font-size="16" font-weight="600" fill="{accent}">Languages across {n} repositories</text>']
    bar_x, bar_w = 120, 180
    for i, (nm, b) in enumerate(items):
        y = top_y + i * row
        pct = 100 * b / total
        o.append(f'<text x="22" y="{y+11}" fill="{t["fg"]}">{nm}</text>')
        o.append(f'<rect x="{bar_x}" y="{y+2}" width="{bar_w}" height="10" rx="5" fill="{t["cells"][0]}"/>')
        o.append(f'<rect x="{bar_x}" y="{y+2}" width="{max(4, round(bar_w*pct/100))}" height="10" rx="5" fill="{colors[nm]}"/>')
        o.append(f'<text x="{bar_x+bar_w+10}" y="{y+11}" fill="{t["fg"]}" font-weight="600">{pct:.1f}%</text>')
        o.append(f'<text x="{bar_x+bar_w+58}" y="{y+11}" fill="{t["muted"]}">{repos_by[nm]} repo{"s" if repos_by[nm]!=1 else ""}</text>')
    o.append("</svg>")
    return "\n".join(o)

def _esc(x):
    return str(x).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def render_wave(cal, theme, name="Chen Yang", role="Biostatistician · Applied ML · LC-MS RNA Sequencing", org="The RNA Institute"):
    """Profile card: name, role, affiliation on the left; smoothed one-year contribution curve on the right."""
    t = THEMES[theme]
    border = "#d0d7de" if theme == "light" else "#30363d"
    accent = "#0969da" if theme == "light" else "#58a6ff"
    green = "#2da44e" if theme == "light" else "#3fb950"
    weeks = [sum(d["contributionCount"] for d in wk["contributionDays"]) for wk in cal["weeks"]]
    sm = [sum(weeks[max(0,i-1):i+2]) / len(weeks[max(0,i-1):i+2]) for i in range(len(weeks))]
    w, h = 900, 220
    gx0, gx1, gy0, gy1 = 400, 862, 54, 172
    mx = max(max(sm), 1)
    xs = [gx0 + i * (gx1 - gx0) / (len(sm) - 1) for i in range(len(sm))]
    ys = [gy1 - (v / mx) * (gy1 - gy0) for v in sm]
    d = f"M{xs[0]:.1f},{ys[0]:.1f}"
    for i in range(1, len(xs)):
        cx = (xs[i-1] + xs[i]) / 2
        d += f" C{cx:.1f},{ys[i-1]:.1f} {cx:.1f},{ys[i]:.1f} {xs[i]:.1f},{ys[i]:.1f}"
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
         '<defs>',
         f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{green}" stop-opacity="0.45"/><stop offset="1" stop-color="{green}" stop-opacity="0.02"/></linearGradient>',
         f'<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2F81F7"/><stop offset="1" stop-color="#7C3AED"/></linearGradient>',
         '</defs>',
         f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{t["bg"]}" stroke="{border}"/>',
         f'<rect x="0.5" y="0.5" width="{w-1}" height="4" rx="2" fill="url(#bar)"/>',
         f'<text x="32" y="66" font-size="28" font-weight="700" fill="{accent}">{_esc(name)}</text>',
         f'<text x="32" y="94" font-size="14" fill="{t["fg"]}">{_esc(role)}</text>']
    bx, by = 32, 112
    o.append(f'<rect x="{bx}" y="{by+4}" width="16" height="11" rx="2" fill="none" stroke="{t["muted"]}" stroke-width="1.6"/>')
    o.append(f'<path d="M{bx+5},{by+4} V{by+2} a1.5,1.5 0 0 1 1.5,-1.5 h3 a1.5,1.5 0 0 1 1.5,1.5 V{by+4}" fill="none" stroke="{t["muted"]}" stroke-width="1.6"/>')
    o.append(f'<line x1="{bx}" y1="{by+9}" x2="{bx+16}" y2="{by+9}" stroke="{t["muted"]}" stroke-width="1.2"/>')
    o.append(f'<text x="{bx+24}" y="{by+13}" font-size="14" fill="{t["fg"]}">{_esc(org)}</text>')
    # right: gridlines, area, line, axis, months
    o.append(f'<text x="{gx1}" y="{gy0-16}" font-size="11" text-anchor="end" fill="{t["muted"]}">Contributions · last 12 months</text>')
    for k in range(4):
        y = gy1 - k * (gy1 - gy0) / 3
        o.append(f'<line x1="{gx0}" y1="{y:.1f}" x2="{gx1}" y2="{y:.1f}" stroke="{border}" stroke-dasharray="2 4"/>')
    o.append(f'<path d="{d} L{xs[-1]:.1f},{gy1} L{xs[0]:.1f},{gy1} Z" fill="url(#area)"/>')
    o.append(f'<path d="{d}" fill="none" stroke="{green}" stroke-width="2.5" stroke-linejoin="round"/>')
    o.append(f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" fill="{green}" stroke="{t["bg"]}" stroke-width="2"/>')
    last_m = None
    for i, wk in enumerate(cal["weeks"]):
        m = dt.date.fromisoformat(wk["contributionDays"][0]["date"]).strftime("%b")
        if m != last_m:
            if last_m is not None:
                o.append(f'<text x="{xs[i]:.1f}" y="{gy1+18}" font-size="10" text-anchor="middle" fill="{t["muted"]}">{m}</text>')
            last_m = m
    o.append("</svg>")
    return "\n".join(o)

REPO_QUERY = """query($owner:String!,$name:String!){ repository(owner:$owner,name:$name){
  name description url homepageUrl pushedAt primaryLanguage{ name color } licenseInfo{ spdxId }
  languages(first:3, orderBy:{field:SIZE, direction:DESC}){ edges{ node{ name color } } } } }"""

def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width and cur:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur: lines.append(cur)
    return lines

def render_repo_card(repo, theme, tags=()):
    t = THEMES[theme]
    border = "#d0d7de" if theme == "light" else "#30363d"
    accent = "#0969da" if theme == "light" else "#58a6ff"
    chip_bg = "#ddf4ff" if theme == "light" else "#1f2a3a"
    w, h = 440, 150
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" fill="{t["bg"]}" stroke="{border}"/>',
         # repo icon
         f'<path transform="translate(20,20) scale(1.1)" fill="{t["muted"]}" d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>',
         f'<text x="44" y="33" font-size="15" font-weight="600" fill="{accent}">{_esc(repo["name"])}</text>']
    lines = _wrap(repo["description"] or "", 60)[:3]
    for i, ln in enumerate(lines):
        o.append(f'<text x="20" y="{58 + i*17}" font-size="12" fill="{t["fg"]}">{_esc(ln)}</text>')
    # footer: language dot, tags, updated
    y = h - 18; x = 20
    pl = repo.get("primaryLanguage")
    if pl:
        o.append(f'<circle cx="{x+5}" cy="{y-4}" r="5" fill="{pl["color"] or t["muted"]}"/>')
        o.append(f'<text x="{x+16}" y="{y}" font-size="12" fill="{t["fg"]}">{_esc(pl["name"])}</text>')
        x += 16 + 7 * len(pl["name"]) + 18
    for tag in tags:
        tw = 7 * len(tag) + 14
        o.append(f'<rect x="{x}" y="{y-13}" width="{tw}" height="18" rx="9" fill="{chip_bg}"/>')
        o.append(f'<text x="{x+tw/2}" y="{y}" font-size="11" text-anchor="middle" fill="{accent}">{_esc(tag)}</text>')
        x += tw + 6
    upd = dt.datetime.fromisoformat(repo["pushedAt"].replace("Z","+00:00")).strftime("%b %Y")
    o.append(f'<text x="{w-20}" y="{y}" font-size="11" text-anchor="end" fill="{t["muted"]}">Updated {upd}</text>')
    o.append("</svg>")
    return "\n".join(o)

FEATURED = [
    ("replicateshift", ("Deep Sets", "Conformal")),
    ("rna-layout-tool", ("SVG", "Live demo")),
    ("Trade_bo", ("React", "Live demo")),
    ("Research_hunter", ("Semantic Scholar",)),
    ("psychic-rotary-phone", ("R", "Causal mediation")),
    ("cautious-octo-eureka", ("PyTorch", "Adversarial")),
]

if __name__ == "__main__":
    cal = fetch()
    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(OUT, f"heatmap-{theme}.svg"), "w") as f:
            f.write(render(cal, theme))
    for theme in THEMES:
        with open(os.path.join(OUT, f"activity-{theme}.svg"), "w") as f:
            f.write(render_activity(cal, theme))
        with open(os.path.join(OUT, f"wave-{theme}.svg"), "w") as f:
            f.write(render_wave(cal, theme))
    for rname, tags in FEATURED:
        repo = gql(REPO_QUERY, {"owner": LOGIN, "name": rname})["repository"]
        for theme in THEMES:
            with open(os.path.join(OUT, f"repo-{rname}-{theme}.svg"), "w") as f:
                f.write(render_repo_card(repo, theme, tags))
    n, bb, rb, cc = fetch_languages()
    for theme in THEMES:
        with open(os.path.join(OUT, f"languages-{theme}.svg"), "w") as f:
            f.write(render_languages(n, bb, rb, cc, theme))
    print("languages:", n, "repos", sorted(((k, rb[k]) for k in bb), key=lambda kv: -bb[kv[0]]))
    years = fetch_years(); merged = fetch_merged_public()
    for theme in THEMES:
        with open(os.path.join(OUT, f"stats-{theme}.svg"), "w") as f:
            f.write(render_stats(years, cal["totalContributions"], merged, theme))
    print("heatmap:", cal["totalContributions"], "contributions,", len(cal["weeks"]), "weeks; years:", years, "merged public:", merged)
