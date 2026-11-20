#!/usr/bin/env python3
"""Build https://book.ozarland.com/: the book told as LUMO's crossing of the archipelago of control.

    python3 tools/site/build.py [--out build/site]

The text of the book is not changed. Each page of chapters/ and appendices/ is converted to HTML with
pandoc, exactly as written, and framed by the story layer of story/story.json: the place LUMO reaches,
the scene, the state of the lantern, what LUMO carries away, and the way on to the next stop. Only the
navigation is adapted to the site: the "Part" label at the top of a chapter becomes the story header, the
Previous / Contents / Next line at the bottom becomes the road to the next stop, and links between
chapters open the corresponding page of the site.

Requires pandoc. Fails (exit 1) when a page of the book has no story entry, a story entry has no page,
or a link or image of the generated site does not resolve.
"""
import argparse
import html
import json
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/OzarLand/openstack-the-day-after-tomorrow"
SITE = "https://book.ozarland.com/"
BOOK = "OpenStack, the Day After Tomorrow"
SUBTITLE = "Operating Mission-Critical OpenStack Platforms"

BOX_CLASSES = {"Technical note": "box-tech", "Principle": "box-principle", "From the field": "box-field"}
BOX_ICONS = {
    "box-tech": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M14.5 14.5 20 20" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
    "box-principle": '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="16" rx="8" ry="4" fill="currentColor"/><ellipse cx="12" cy="9.5" rx="5" ry="3" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    "box-field": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 3v18M12 8h4M12 12h4" stroke="currentColor" stroke-width="2"/></svg>',
}


def lantern_svg(state, size=56):
    """The lantern drawn for a state of control. The halo's shape carries the state, so it reads in grey too."""
    body = ('<path d="M24 9h8l2 4H22z" fill="currentColor"/><rect x="21" y="13" width="14" height="20" rx="3" '
            'fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M28 18c3 3 3 7 0 10-3-3-3-7 0-10z" '
            'class="flame"/><path d="M21 33h14l-2 4H23z" fill="currentColor"/><path d="M28 9V5" stroke="currentColor" '
            'stroke-width="2.4" stroke-linecap="round"/>')
    halos = {
        "unknown": '<circle cx="28" cy="23" r="21" class="halo" stroke-dasharray="6 9" stroke-width="2"/>',
        "visible": '<circle cx="28" cy="23" r="21" class="halo" stroke-dasharray="0.1 6" stroke-linecap="round" stroke-width="3.4"/>',
        "understood": '<circle cx="28" cy="23" r="21" class="halo" stroke-width="2.4"/>',
        "controlled": '<circle cx="28" cy="23" r="22" class="halo" stroke-width="2"/><circle cx="28" cy="23" r="18" class="halo" stroke-width="2"/>',
        "recoverable": '<path d="M10 33a21 21 0 1 1 8 8" class="halo" stroke-width="2.4"/><path d="M12 45l6-4-6-3" class="halo" stroke-width="2.4" stroke-linejoin="round"/>',
        "sustainable": '<circle cx="28" cy="23" r="21" class="halo" stroke-width="2.4"/><g transform="translate(2 34) scale(.42)"><rect x="21" y="13" width="14" height="20" rx="3" class="halo" stroke-width="4"/></g><g transform="translate(37 34) scale(.42)"><rect x="21" y="13" width="14" height="20" rx="3" class="halo" stroke-width="4"/></g>',
    }
    return (f'<svg class="lantern lantern-{state}" width="{size}" height="{size}" viewBox="0 0 56 56" aria-hidden="true">'
            f'{halos[state]}{body}</svg>')


def page_url(md_path):
    """chapters/01-x.md -> chapters/01-x/ (the site mirrors the repository paths)."""
    return md_path[: -len(".md")] + "/"


def rel(from_url, to_url):
    """Relative address from the page at from_url (a directory URL, '' for the home page) to to_url."""
    depth = from_url.count("/") if from_url else 0
    prefix = "../" * depth
    return (prefix + to_url) or "./"


def strip_navigation(md):
    """Remove the part label above a chapter title and the Previous / Contents / Next line at the end."""
    lines = md.rstrip("\n").split("\n")
    if lines and re.fullmatch(r"\*(Part [IVX]+ — .+|Appendices)\*", lines[0].strip()):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "---":
            tail = "\n".join(lines[i + 1:])
            if "Contents](../README.md)" in tail:
                lines = lines[:i]
            break
    return "\n".join(lines).rstrip() + "\n"


def pandoc(md):
    out = subprocess.run(
        ["pandoc", "--from=markdown-implicit_figures", "--to=html5", "--wrap=none"],
        input=md, capture_output=True, text=True, check=True)
    return out.stdout


def rewrite_links(body, src, url, known):
    """Point links between pages at the site, images at the copied figures, other repository files at GitHub."""
    src_dir = posixpath.dirname(src)

    def fix(match):
        attr, target = match.group(1), html.unescape(match.group(2))
        if re.match(r"^[a-z]+:|^#|^//", target):
            return match.group(0)
        path, _, frag = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(src_dir, path))
        if resolved == "README.md":
            new = rel(url, "") + (f"#{frag}" if frag else "#route")
        elif resolved in known:
            new = rel(url, page_url(resolved)) + (f"#{frag}" if frag else "")
        elif resolved.startswith("assets/"):
            new = rel(url, resolved)
        else:
            new = f"{REPO}/blob/main/{resolved}" + (f"#{frag}" if frag else "")
        return f'{attr}="{html.escape(new)}"'

    return re.sub(r'\b(href|src)="([^"]*)"', fix, body)


def style_boxes(body):
    """Give the three kinds of boxed passage their look; their text is left as written."""
    def fix(match):
        kind = match.group(1)
        cls = BOX_CLASSES[kind]
        return f'<blockquote class="box {cls}"><span class="box-icon">{BOX_ICONS[cls]}</span>\n<p><strong>{kind}'
    return re.sub(r"<blockquote>\s*<p><strong>(Technical note|Principle|From the field)", fix, body)


def figures(body):
    """Figures keep their caption; they get a light plate so that the drawings read on a dark page too."""
    return re.sub(r'<p><img ([^>]*)></p>', r'<p class="figure"><img \1 loading="lazy"></p>', body)


def visible_text(fragment):
    """The words a reader sees, without markup: used to prove that framing the text did not change it."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def removed_lines_are_navigation(md):
    """Only the part label and the Previous / Contents / Next line may be left out of a page."""
    kept = strip_navigation(md).split("\n")
    removed = [line for line in md.split("\n") if line.strip() and line not in kept]
    return all(re.fullmatch(r"\*(Part [IVX]+ — .+|Appendices)\*|---|\[.*\]\(.*\.md\).*", line.strip()) for line in removed)


def head(title, description, url, canonical_path, css_href, icon_href, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{SITE}{canonical_path}">
<link rel="icon" href="{icon_href}" type="image/svg+xml">
<link rel="stylesheet" href="{css_href}">
<meta property="og:site_name" content="OzarLand">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{SITE}{canonical_path}">
{extra}</head>
"""


def topbar(url):
    return f"""<header class="top">
  <div class="wrap">
    <a class="brand" href="{rel(url, '')}"><img src="{rel(url, 'assets/favicon.svg')}" alt="" width="26" height="26">{BOOK}</a>
    <nav aria-label="Main">
      <a href="{rel(url, '')}#route">The route</a>
      <a href="https://ozarland.com/">OzarLand</a>
      <a href="{REPO}">GitHub</a>
    </nav>
  </div>
</header>
"""


def footer(url):
    return f"""<footer>
  <div class="wrap">
    <p>The story layer frames each chapter; the text of the book is published as written, from
    <a href="{REPO}">OzarLand/openstack-the-day-after-tomorrow</a>. An independent, personal contribution to the OpenStack
    community, not a publication of the OpenInfra Foundation, of a publisher, or of any employer or client. Part of
    <a href="https://ozarland.com/">OzarLand</a>.</p>
    <p>Copyright © 2026 Soufian Zaouam. Released under the
    <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache License, Version 2.0</a>.
    <a href="{REPO}/issues/new?template=errata.yml">Report an error</a> ·
    <a href="{REPO}/blob/main/CHANGELOG.md">Changelog</a></p>
  </div>
</footer>
</body>
</html>
"""


def mini_map(story, page, url):
    x, y = page["map"]
    m = story["map"]
    return (f'<a class="minimap" href="{rel(url, "")}#route" aria-label="See this stop on the map of the crossing">'
            f'<img src="{rel(url, m["image"])}" width="{m["width"]}" height="{m["height"]}" alt="">'
            f'<span class="marker here" style="left:{x}%;top:{y}%"></span></a>')


def scene_block(story, page, url):
    part = story["parts"].get(page.get("part", ""), None)
    light = page.get("light")
    stop = page.get("stop")
    solo = not (light or page.get("map") or page.get("kind") == "prelude")
    out = [f'<section class="scene{" solo" if solo else ""}" aria-label="The story">']
    if page.get("image"):
        out.append(f'<figure class="scene-image"><img src="{rel(url, page["image"])}" width="1800" height="1200" '
                   f'alt="{html.escape(page.get("image_alt", ""))}"></figure>')
    out.append('<div class="scene-text">')
    label = []
    if stop:
        label.append(f"Stop {stop} of 20")
    if part and page.get("part") not in ("end", "tools"):
        label.append(html.escape(part["title"]))
    elif page.get("kind") in ("prelude", "opening"):
        label.append("Before the crossing" if page.get("kind") == "prelude" else "The crossing begins")
    elif page.get("kind") == "closing":
        label.append("The end of the crossing")
    if label:
        out.append(f'<p class="scene-kicker">{" · ".join(label)}</p>')
    out.append(f'<p class="place">{html.escape(page["place"])}</p>')
    out.append(f'<p class="narration">{html.escape(page["scene"])}</p>')
    if page.get("keys"):
        out.append('<ul class="keys">')
        for key in page["keys"]:
            cls = BOX_CLASSES[key["label"]]
            out.append(f'<li class="key {cls}"><span class="box-icon">{BOX_ICONS[cls]}</span>'
                       f'<span><strong>{html.escape(key["label"])}</strong> — {html.escape(key["pose"])}</span></li>')
        out.append("</ul>")
    if page.get("carry"):
        out.append(f'<p class="carry"><span>In LUMO\'s satchel:</span> {html.escape(page["carry"])}</p>')
    out.append("</div>")
    if page.get("kind") == "prelude" and not light:
        out.append(f'<div class="scene-side"><img class="portrait" src="{rel(url, "assets/story/lumo.webp")}" width="1200" '
                   'height="600" alt="LUMO, a cartographer in a navy cape, holds a brass lantern at an island crossroads."></div>')
    elif light or page.get("map"):
        out.append('<div class="scene-side">')
        if light:
            state = story["lantern_states"][light]
            note = page.get("light_note", state["meaning"])
            out.append(f'<div class="lantern-card">{lantern_svg(light)}<p><span class="state">Lantern: '
                       f'{state["label"]}</span>{html.escape(note[0].upper() + note[1:])}</p></div>')
        if page.get("map"):
            out.append(mini_map(story, page, url))
        out.append("</div>")
    out.append("</section>")
    return "\n".join(out)


def build_page(story, page, index, pages, known, out_dir):
    src = page["file"]
    url = page_url(src)
    md = (ROOT / src).read_text(encoding="utf-8")
    if not removed_lines_are_navigation(md):
        raise SystemExit(f"{src}: leaving out the navigation would remove text of the book")
    title_match = re.search(r"^# (.+)$", md, re.M)
    title = title_match.group(1).strip() if title_match else page["place"]
    original = pandoc(strip_navigation(md))
    body = figures(style_boxes(rewrite_links(original, src, url, known)))
    if visible_text(body) != visible_text(original):
        raise SystemExit(f"{src}: the published text differs from the book")
    part = story["parts"].get(page.get("part", ""), story["parts"]["end"])
    prev_page = pages[index - 1] if index > 0 else None
    next_page = pages[index + 1] if index + 1 < len(pages) else None

    road = ['<nav class="road" aria-label="The road">']
    if page.get("onward"):
        road.append(f'<p class="onward">{html.escape(page["onward"])}</p>')
    road.append('<div class="road-links">')
    if prev_page:
        road.append(f'<a class="cta" rel="prev" href="{rel(url, page_url(prev_page["file"]))}">← {html.escape(prev_page["place"])}</a>')
    road.append(f'<a class="cta" href="{rel(url, "")}#route">The map</a>')
    if next_page:
        road.append(f'<a class="cta primary" rel="next" href="{rel(url, page_url(next_page["file"]))}">{html.escape(next_page["place"])} →</a>')
    road.append("</div></nav>")

    accent = f'--accent:{part["accent"]};--accent-dark:{part["dark"]}'
    doc = head(f"{title} · {BOOK}", f"{page['place']}: {page['scene'][:150]}", url, url,
               rel(url, "assets/book.css"), rel(url, "assets/favicon.svg"))
    doc += f'<body style="{accent}">\n' + topbar(url)
    doc += '<main class="wrap">\n' + scene_block(story, page, url) + "\n"
    doc += f'<article class="book-text">\n{body}</article>\n' + "\n".join(road) + "\n</main>\n" + footer(url)
    target = out_dir / url / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")


def build_home(story, pages, out_dir):
    url = ""
    m = story["map"]
    markers, route = [], []
    for page in pages:
        if "map" not in page:
            continue
        x, y = page["map"]
        num = page.get("stop") or ("★" if page.get("kind") == "closing" else "⚓")
        markers.append(f'<a class="marker" style="left:{x}%;top:{y}%" href="{page_url(page["file"])}" '
                       f'title="{html.escape(page["place"])}"><span>{num}</span></a>')
    groups = {}
    for page in pages:
        groups.setdefault(page.get("part") or "prelude", []).append(page)
    order = [("prelude", "Before the crossing")] + [(k, story["parts"][k]["title"]) for k in ("I", "II", "III", "IV", "V", "VI", "end", "tools")]
    for key, label in order:
        items = groups.get(key, [])
        if not items:
            continue
        accent = story["parts"].get(key, {"accent": "#6B4220", "dark": "#D9A865"})
        route.append(f'<section class="leg" style="--accent:{accent["accent"]};--accent-dark:{accent["dark"]}"><h3>{html.escape(label)}</h3><ol>')
        for page in items:
            md = (ROOT / page["file"]).read_text(encoding="utf-8")
            t = re.search(r"^# (.+)$", md, re.M)
            chapter = t.group(1).strip() if t else ""
            num = f'<span class="num">{page["stop"]}</span>' if page.get("stop") else '<span class="num dot"></span>'
            place = page["place"].replace("LUMO's Toolbox — ", "")
            route.append(f'<li>{num}<a href="{page_url(page["file"])}"><span class="route-place">{html.escape(place)}</span>'
                         f'<span class="route-chapter">{html.escape(chapter)}</span></a></li>')
        route.append("</ol></section>")
    states = "".join(
        f'<li>{lantern_svg(k, 44)}<span><strong>{v["label"]}</strong> {html.escape(v["meaning"])}</span></li>'
        for k, v in story["lantern_states"].items())
    first = page_url(pages[0]["file"])
    harbour = next(p for p in pages if p.get("kind") == "opening")

    doc = head(f"{BOOK} · {SUBTITLE}",
               "A free book on operating OpenStack in production for years, told as LUMO's crossing of the archipelago of control: twenty stops, from the handover quay to the lighthouse.",
               url, "", "assets/book.css", "assets/favicon.svg",
               f'<meta property="og:type" content="book">\n<meta property="og:image" content="{SITE}assets/story/cover.webp">\n<meta name="twitter:card" content="summary_large_image">\n')
    doc += '<body class="home">\n' + topbar(url)
    doc += f"""<main class="wrap">
<section class="hero" aria-labelledby="title">
  <div class="hero-text">
    <p class="scene-kicker">A story in twenty stops</p>
    <h1 id="title">{BOOK}</h1>
    <p class="subtitle">{SUBTITLE}</p>
    <p class="author">by Soufian Zaouam</p>
    <p class="lead">Most OpenStack material stops where the real work begins: the platform is deployed, the services answer.
    This book is about what comes next, the years during which a platform has to stay stable, observable, upgradable,
    secure and understandable by the people who operate it. Here it is told as a crossing. LUMO, the cartographer of
    OzarLand, walks with an operations team across an archipelago where the mist is the loss of control.</p>
    <p class="actions">
      <a class="cta primary" href="{first}">Begin the crossing</a>
      <a class="cta" href="{page_url(harbour['file'])}">Go straight to the harbour</a>
      <a class="cta" href="#route">See the route</a>
    </p>
  </div>
  <figure class="cover"><img src="assets/story/cover.webp" width="900" height="1350"
    alt="LUMO, a cartographer in a navy cape, holds a lantern and a book on a terrace above a bright island city, where a small team works around a table."></figure>
</section>

<section class="lumo" aria-labelledby="lumo">
  <img src="assets/story/lumo.webp" width="1200" height="600" loading="lazy"
    alt="LUMO, a cartographer in a navy cape with a white cloud emblem, holds a brass lantern at an island crossroads.">
  <div>
    <h2 id="lumo">Meet LUMO</h2>
    <p>LUMO means light in Esperanto. LUMO is the travelling cartographer of OzarLand: curly auburn hair, cartographer's
    goggles, a navy cape with a plain cloud, a leather satchel full of maps, a compass and a brass lantern.</p>
    <p>LUMO looks before acting, asks the right questions, knows when to say stop and passes on what they know. LUMO
    never fixes the platform alone, never decides in the team's place, and never uses magic: the people of the island
    make the decisions. The lantern shows how much of the road is under control.</p>
    <ul class="states">{states}</ul>
  </div>
</section>

<section aria-labelledby="route" class="route-section">
  <h2 id="route">The route</h2>
  <p class="intro">Twenty stops, from the handover quay to the lighthouse, in the order of the book. Each chapter opens
  with the place LUMO reaches; the chapter itself follows, word for word.</p>
  <div class="bigmap"><img src="{m['image']}" width="{m['width']}" height="{m['height']}" loading="lazy" alt="{html.escape(m['alt'])}">
  {''.join(markers)}</div>
  <div class="legs">{''.join(route)}</div>
</section>

<section aria-labelledby="about" class="about">
  <h2 id="about">About the book</h2>
  <p class="intro">Its central thesis is that operating OpenStack in production is not only a technical problem. It is
  also a problem of visibility, stability, organisation, governance and risk management. It draws on more than five
  years of running OpenStack platforms in production; real experience has been generalised into patterns and
  principles, and no client, employer, project or environment is described or identifiable. It assumes a working
  knowledge of OpenStack. It is not an installation guide and does not replace the official documentation.</p>
  <p class="intro">The story is a frame around the text, not a rewrite of it: every chapter is published as written,
  with its technical notes, principles and field passages. The same text can be read as plain Markdown
  <a href="{REPO}#read-the-book-on-github">on GitHub</a>.</p>
  <h3>Citing this book</h3>
  <blockquote class="cite">Zaouam, S. (2026). <em>{BOOK}: {SUBTITLE}</em>. {SITE}</blockquote>
  <p class="intro">Give the date on which you read it. A machine-readable citation is in
  <a href="{REPO}/blob/main/CITATION.cff">CITATION.cff</a>.</p>
</section>
</main>
"""
    doc += footer(url)
    (out_dir / "index.html").write_text(doc, encoding="utf-8")


def check_links(out_dir):
    errors = []
    for page in out_dir.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for target in re.findall(r'\b(?:href|src)="([^"]+)"', text):
            target = html.unescape(target)
            if re.match(r"^[a-z]+:|^#|^//", target):
                continue
            if page.name == "404.html" and target.startswith("/"):
                continue
            path = target.split("#")[0]
            resolved = (page.parent / path).resolve() if path else page
            if resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.exists():
                errors.append(f"{page.relative_to(out_dir)}: {target} does not resolve")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="build/site")
    args = parser.parse_args()
    out_dir = (ROOT / args.out).resolve()

    story = json.loads((ROOT / "story/story.json").read_text(encoding="utf-8"))
    pages = story["pages"]
    known = {p["file"] for p in pages}
    on_disk = {str(p.relative_to(ROOT)) for d in ("chapters", "appendices") for p in (ROOT / d).glob("*.md")}
    problems = [f"{f}: page of the book with no story entry" for f in sorted(on_disk - known)]
    problems += [f"{f}: story entry with no page" for f in sorted(known - on_disk)]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ROOT / "site", out_dir, ignore=shutil.ignore_patterns("index.html"))
    shutil.copytree(ROOT / "assets/figures", out_dir / "assets/figures")
    for index, page in enumerate(pages):
        build_page(story, page, index, pages, known, out_dir)
    build_home(story, pages, out_dir)

    errors = check_links(out_dir)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"{len(pages)} pages of the book, home page and map written to {out_dir.relative_to(ROOT)}: all links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
