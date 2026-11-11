#!/usr/bin/env python3
"""
Generates dark_mode.svg and light_mode.svg: a neofetch-style profile card.

  python generate_card.py                 # uses the built-in FAIQ banner
  python generate_card.py --photo portrait.png  # cut-out PNG -> ASCII portrait

Live stats (repos, stars, followers, commits) come from the GitHub API when
GITHUB_TOKEN is set (the included workflow does this). Without a token the
stats show "--" so the card still renders.
"""
import argparse
import html
import json
import datetime
import os
import urllib.request

# ----------------------------------------------------------------------------
# EDIT THIS BLOCK: everything shown on the card
# ----------------------------------------------------------------------------
USERNAME = "kunwarfaiq"
HANDLE = "faiq@kunwarfaiq"

# Set your birthday to show a live "Age" line (updates every day, like an uptime counter).
# Leave as None to hide the line.  Example: datetime.date(2003, 5, 17)
BIRTHDAY = None

# (section title, [(key, value), ...]). Values should stay under ~40 chars.
SECTIONS = [
    (None, [
        ("Name", "Kunwar Faiq Azeem"),
        ("Uni", "DHA Suffa University, Karachi"),
        ("Degree", "BS Data Science, class of 2027"),
        ("CGPA", "3.43 / 4.00"),
        ("Focus", "NLP, Distributed Systems, Deep Learning"),
        ("Role", "Head of Media & Design, ACM"),
        ("Hackathon", "Google Antigravity 2026"),
        ("Looking for", "AI Engineer / Data Scientist roles"),
    ]),
    ("Stack", [
        # TODO: replace these with your real stack
        ("Languages", "Python, SQL"),
        ("Libraries", "PyTorch, scikit-learn, pandas"),
        ("Tools", "Git, Docker, Linux"),
    ]),
    ("Contact", [
        ("GitHub", "github.com/kunwarfaiq"),
        ("LinkedIn", "linkedin.com/in/kunwarfaiq"),
    ]),
    ("GitHub Stats", "STATS"),  # filled from the API
]

WIDTH_CHARS = 58          # width of the right-hand column in characters
ART_ROWS = 34             # height of the ASCII portrait in lines (matches the bio)
ART_FONT = 9              # art font size / line height: small text = more detail in the same space
ART_LINE = 12
FONT_SIZE = 14
LINE_H = 19

THEMES = {
    "dark_mode.svg": dict(
        bg="#161b22", fg="#c9d1d9", key="#ffa657", value="#a5d6ff",
        dots="#616e7c", title="#79c0ff", art="#8b949e", add="#3fb950", sub="#f85149"),
    "light_mode.svg": dict(
        bg="#f6f8fa", fg="#24292f", key="#953800", value="#0a3069",
        dots="#a0a7b0", title="#0550ae", art="#57606a", add="#1a7f37", sub="#cf222e"),
}

# ----------------------------------------------------------------------------
# ASCII art
# ----------------------------------------------------------------------------
LETTERS = {
    "F": ["#######", "##     ", "##     ", "#####  ", "##     ", "##     ", "##     "],
    "A": [" ##### ", "##   ##", "##   ##", "#######", "##   ##", "##   ##", "##   ##"],
    "I": ["#######", "  ###  ", "  ###  ", "  ###  ", "  ###  ", "  ###  ", "#######"],
    "Q": [" ##### ", "##   ##", "##   ##", "##   ##", "## # ##", "##  ## ", " #### #"],
}


def banner_art():
    """FA / IQ in chunky 2x letters."""
    def word(w):
        rows = []
        for r in range(7):
            line = "  ".join(LETTERS[c][r] for c in w)
            doubled = "".join(ch * 2 for ch in line)
            rows += [doubled, doubled]
        return rows
    top, bottom = word("FA"), word("IQ")
    art = top + ["", ""] + bottom
    art += ["", "  >>> data. models. systems. <<<"]
    return art


# Short, sparse ramp (light -> dense). Fewer characters = a cleaner, less cluttered look.
RAMP = " .:-=+*#%@"
HOLLOW = 0.34   # tones below this become blank, which leaves the lit sides hollow


def photo_art(path, rows, dark_theme):
    """ASCII portrait with a fixed number of rows. Transparent pixels
    (alpha < 128) become blank, so a cut-out PNG gives just the person."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps  # pip install pillow numpy

    src = Image.open(path).convert("RGBA")
    w, h = src.size
    cell = ART_FONT * 0.6 / ART_LINE          # character width / height
    cols = int(round(rows * (w / h) / cell))
    src = src.resize((cols, rows), Image.LANCZOS)
    alpha = np.asarray(src)[:, :, 3] > 128

    gray = src.convert("L")
    tone = np.asarray(ImageOps.autocontrast(gray, cutoff=1)).astype(float) / 255.0
    # outlines: gradient magnitude of a lightly blurred copy
    soft = np.asarray(gray.filter(ImageFilter.GaussianBlur(0.6))).astype(float) / 255.0
    gy, gx = np.gradient(soft)
    edge = np.clip(np.hypot(gx, gy) * 6.0, 0, 1)

    base = tone ** 0.7 if dark_theme else 1.0 - tone     # dense = bright (dark bg) / dark (light bg)
    density = np.clip(0.85 * base + 0.25 * edge, 0, 1)
    # carve out the cut-out's own rim a little so the silhouette stays hollow-sided
    n = len(RAMP) - 1
    lines = []
    for y in range(rows):
        row = []
        for x in range(cols):
            d = density[y, x]
            row.append(RAMP[min(n, int(d * (n + 1)))] if (alpha[y, x] and d >= HOLLOW) else " ")
        lines.append("".join(row).rstrip())
    return lines


# ----------------------------------------------------------------------------
# GitHub stats
# ----------------------------------------------------------------------------
def gh(query=None, path=None, token=None):
    headers = {"Authorization": f"bearer {token}", "User-Agent": "profile-card"}
    if query:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query}).encode(), headers=headers)
    else:
        req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def age_string(born, today=None):
    today = today or datetime.date.today()
    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        prev_end = today.replace(day=1) - datetime.timedelta(days=1)
        days += prev_end.day
    if months < 0:
        years -= 1
        months += 12
    def unit(n, word):
        return f"{n} {word}{'' if n == 1 else 's'}"
    return f"{unit(years, 'year')}, {unit(months, 'month')}, {unit(days, 'day')}"


def fetch_loc(token):
    """Lines added / deleted in commits authored by you, across your own non-fork repos."""
    uid = gh(query='{ user(login:"%s"){ id } }' % USERNAME, token=token)["data"]["user"]["id"]
    repos = gh(query='{ user(login:"%s"){ repositories(first:100, ownerAffiliations:OWNER, isFork:false){ nodes{ name } } } }'
               % USERNAME, token=token)["data"]["user"]["repositories"]["nodes"]
    added = deleted = 0
    for repo in repos:
        cursor = None
        for _ in range(50):  # at most 5,000 commits per repo
            after = f', after:"{cursor}"' if cursor else ""
            q = ('{ repository(owner:"%s", name:"%s"){ defaultBranchRef{ target{ ... on Commit{ '
                 'history(first:100, author:{id:"%s"}%s){ pageInfo{ hasNextPage endCursor } '
                 'nodes{ additions deletions } } } } } } }') % (USERNAME, repo["name"], uid, after)
            ref = gh(query=q, token=token)["data"]["repository"]["defaultBranchRef"]
            if not ref:  # empty repo
                break
            hist = ref["target"]["history"]
            for c in hist["nodes"]:
                added += c["additions"]
                deleted += c["deletions"]
            if not hist["pageInfo"]["hasNextPage"]:
                break
            cursor = hist["pageInfo"]["endCursor"]
    return added, deleted


def fetch_stats():
    token = os.environ.get("GITHUB_TOKEN")
    stats = [("Repos", "--"), ("Stars", "--"), ("Commits", "--"), ("Followers", "--"), ("Lines of code", "--")]
    if not token:
        return stats
    try:
        q = """{ user(login:"%s"){
            followers{totalCount}
            repositories(ownerAffiliations:OWNER, isFork:false, first:100){
              totalCount nodes{stargazerCount}}
            contributionsCollection{ totalCommitContributions }
        }}""" % USERNAME
        u = gh(query=q, token=token)["data"]["user"]
        stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
        stats[0] = ("Repos", str(u["repositories"]["totalCount"]))
        stats[1] = ("Stars", str(stars))
        stats[2] = ("Commits", f'{u["contributionsCollection"]["totalCommitContributions"]} (last year)')
        stats[3] = ("Followers", str(u["followers"]["totalCount"]))
    except Exception as e:  # never break the card over a stats failure
        print("stats failed:", e)
    try:
        a, d = fetch_loc(token)
        stats[4] = ("Lines of code", f"{a - d:,} ({a:,}++, {d:,}--)")
    except Exception as e:
        print("lines of code failed:", e)
    return stats


# ----------------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------------
def esc(s):
    return html.escape(s, quote=False)


def field(y, x, key, value, c):
    dots = max(2, WIDTH_CHARS - len(key) - len(value) - 2)
    return (
        f'<text x="{x}" y="{y}" class="m" xml:space="preserve" textLength="{WIDTH_CHARS * FONT_SIZE * 0.6:.1f}" lengthAdjust="spacing">'
        f'<tspan fill="{c["key"]}">{esc(key)}</tspan>'
        f'<tspan fill="{c["dots"]}"> {"." * dots} </tspan>'
        f'<tspan fill="{c["value"]}">{esc(value)}</tspan></text>')


def build(name, c, art, stats):
    char_w = FONT_SIZE * 0.6
    art_x = 20
    art_cols = max(len(l) for l in art)
    col_x = int(art_x + art_cols * ART_FONT * 0.6 + 36)
    width = int(col_x + WIDTH_CHARS * char_w + 24)

    body, y = [], 34
    body.append(
        f'<text x="{col_x}" y="{y}" class="m" xml:space="preserve" textLength="{WIDTH_CHARS * FONT_SIZE * 0.6:.1f}" lengthAdjust="spacing">'
        f'<tspan fill="{c["title"]}" font-weight="bold">{esc(HANDLE)}</tspan>'
        f'<tspan fill="{c["dots"]}"> {"-" * (WIDTH_CHARS - len(HANDLE) - 1)}</tspan></text>')
    y += LINE_H
    for title, rows in SECTIONS:
        if title:
            y += 8
            body.append(
                f'<text x="{col_x}" y="{y}" class="m" xml:space="preserve" textLength="{WIDTH_CHARS * FONT_SIZE * 0.6:.1f}" lengthAdjust="spacing">'
                f'<tspan fill="{c["title"]}" font-weight="bold">- {esc(title)} </tspan>'
                f'<tspan fill="{c["dots"]}">{"-" * (WIDTH_CHARS - len(title) - 3)}</tspan></text>')
            y += LINE_H
        if rows == "STATS":
            rows = stats
        for k, v in rows:
            body.append(field(y, col_x, k, v, c))
            y += LINE_H

    height = max(y + 20, 34 + len(art) * ART_LINE + 20)
    art_svg = [f'<text x="{art_x}" y="34" class="a" fill="{c["art"]}" xml:space="preserve">']
    for i, line in enumerate(art):
        tl = f' textLength="{len(line) * ART_FONT * 0.6:.1f}" lengthAdjust="spacing"' if line else ""
        art_svg.append(f'<tspan x="{art_x}" dy="{0 if i == 0 else ART_LINE}"{tl}>{esc(line) or " "}</tspan>')
    art_svg.append("</text>")

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  .m {{ font: {FONT_SIZE}px "Consolas","Courier New",monospace; fill: {c["fg"]}; }}
  .a {{ font: {ART_FONT}px "Consolas","Courier New",monospace; }}
</style>
<rect width="100%" height="100%" rx="15" fill="{c["bg"]}"/>
{"".join(art_svg)}
{chr(10).join(body)}
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", help="photo to convert to ASCII art")
    args = ap.parse_args()

    stats = fetch_stats()
    if BIRTHDAY:
        SECTIONS[0][1].insert(1, ("Age", age_string(BIRTHDAY)))
    for fname, c in THEMES.items():
        dark = fname.startswith("dark")
        art = photo_art(args.photo, ART_ROWS, dark) if args.photo else banner_art()
        with open(fname, "w", encoding="utf-8") as f:
            f.write(build(fname, c, art, stats))
        print("wrote", fname)


if __name__ == "__main__":
    main()
