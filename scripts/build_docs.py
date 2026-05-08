from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASE_URL = "https://mohamedhossammohamed.github.io/zh_catmut"
OG_IMAGE = f"{BASE_URL}/assets/social/og-image.png"
TODAY = date.today().isoformat()


@dataclass(frozen=True)
class Page:
    source: Path
    output: str
    title: str
    description: str
    priority: str
    nav_label: str | None = None
    landing: bool = False


PAGES = [
    Page(DOCS / "index.md", "index.html", "Home", "Native Zig LUT remapping for large Pandas categorical code buffers.", "1.0", "Home", True),
    Page(DOCS / "README.md", "docs.html", "Documentation", "Documentation map for zh_catmut API, architecture, packaging, and release notes.", "0.9", "Docs"),
    Page(ROOT / "README.md", "README.html", "README", "Package README for zh_catmut installation, quickstart, API, and troubleshooting.", "0.3"),
    Page(DOCS / "architecture.md", "architecture.html", "Architecture", "Python safety layer, C ABI boundary, and Zig native remapping architecture.", "0.8", "Architecture"),
    Page(DOCS / "01-categorical-internals-and-memory.md", "01-categorical-internals-and-memory.html", "Categorical Internals and Memory", "How Pandas categoricals store categories and integer codes, and why large remaps need a dense-code path.", "0.7"),
    Page(DOCS / "02-ffi-zero-copy-architecture.md", "02-ffi-zero-copy-architecture.html", "FFI and C ABI Architecture", "The zh_catmut pointer ownership model, Python gates, native gates, and ABI functions.", "0.7"),
    Page(DOCS / "03-performance-algorithms.md", "03-performance-algorithms.html", "Performance Algorithms", "Dense LUT remapping complexity, validation phases, code widths, and cache behavior.", "0.7"),
    Page(DOCS / "04-build-systems-and-distribution.md", "04-build-systems-and-distribution.html", "Build Systems and Distribution", "How zh_catmut builds Zig shared libraries, platform wheels, and release artifacts.", "0.7"),
    Page(DOCS / "publishing.md", "publishing.html", "Publishing", "PyPI/TestPyPI publishing workflow, trusted publishing setup, and verification checklist.", "0.6", "Publishing"),
    Page(ROOT / "CHANGELOG.md", "changelog.html", "Changelog", "Version history and breaking-change notes for zh_catmut.", "0.8", "Changelog"),
]

NAV = [page for page in PAGES if page.nav_label]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def normalize_href(href: str) -> str:
    if href == "../README.md":
        return "README.html"
    if href == "../CHANGELOG.md":
        return "changelog.html"
    if href == "README.md":
        return "README.html"
    if href == "CHANGELOG.md":
        return "changelog.html"
    if href.endswith(".md"):
        return href[:-3] + ".html"
    return href


def inline_markdown(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(normalize_href(m.group(2)), quote=True)}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def render_table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) < 2:
        return "".join(f"<p>{inline_markdown(line)}</p>" for line in lines)
    header = rows[0]
    body = rows[2:]
    thead = "".join(f"<th>{inline_markdown(cell)}</th>" for cell in header)
    trs = []
    for row in body:
        cells = "".join(f"<td>{inline_markdown(cell)}</td>" for cell in row)
        trs.append(f"<tr>{cells}</tr>")
    return f'<table class="doc-table"><thead><tr>{thead}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def render_markdown(markdown_text: str) -> tuple[str, list[tuple[str, str]], str]:
    lines = markdown_text.splitlines()
    page_title = "Untitled"
    if lines and lines[0].startswith("# "):
        page_title = lines[0][2:].strip()
        lines = lines[1:]

    sections: list[tuple[str, str, list[str]]] = []
    current_title = "Overview"
    current_id = "overview"
    current_chunks: list[str] = []
    headings: list[tuple[str, str]] = []
    paragraph: list[str] = []
    list_stack: list[str] = []
    ordered_stack: list[str] = []
    code_lang: str | None = None
    code_lines: list[str] = []
    table_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            current_chunks.append(f"<p>{inline_markdown(' '.join(part.strip() for part in paragraph))}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_stack
        if list_stack:
            items = "".join(f"<li>{inline_markdown(item)}</li>" for item in list_stack)
            current_chunks.append(f"<ul>{items}</ul>")
            list_stack = []

    def flush_ordered_list() -> None:
        nonlocal ordered_stack
        if ordered_stack:
            items = "".join(f"<li>{inline_markdown(item)}</li>" for item in ordered_stack)
            current_chunks.append(f"<ol>{items}</ol>")
            ordered_stack = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            current_chunks.append(render_table(table_lines))
            table_lines = []

    def flush_all() -> None:
        flush_paragraph()
        flush_list()
        flush_ordered_list()
        flush_table()

    def close_section() -> None:
        if current_chunks or sections:
            sections.append((current_id, current_title, current_chunks.copy()))
            current_chunks.clear()

    for line in lines:
        if code_lang is not None:
            if line.startswith("```"):
                escaped_code = html.escape("\n".join(code_lines))
                if code_lang == "mermaid":
                    current_chunks.append(f'<pre class="mermaid">{escaped_code}</pre>')
                else:
                    lang_class = f' class="language-{html.escape(code_lang, quote=True)}"' if code_lang else ""
                    current_chunks.append(f'<div class="code-panel"><pre data-copy><code{lang_class}>{escaped_code}</code></pre></div>')
                code_lang = None
                code_lines = []
            else:
                code_lines.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith("```"):
            flush_all()
            code_lang = stripped[3:].strip()
            code_lines = []
            continue
        if stripped.startswith("## "):
            flush_all()
            close_section()
            current_title = stripped[3:].strip()
            current_id = slugify(current_title)
            headings.append((current_id, current_title))
            continue
        if stripped.startswith("### "):
            flush_all()
            title = stripped[4:].strip()
            current_chunks.append(f'<h3 id="{slugify(title)}">{inline_markdown(title)}</h3>')
            continue
        if stripped.startswith("|") and "|" in stripped[1:]:
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            table_lines.append(stripped)
            continue
        if table_lines:
            flush_table()
        if stripped.startswith("- "):
            flush_paragraph()
            flush_ordered_list()
            list_stack.append(stripped[2:].strip())
            continue
        ordered_match = re.match(r"\d+\.\s+(.*)", stripped)
        if ordered_match:
            flush_paragraph()
            flush_list()
            ordered_stack.append(ordered_match.group(1))
            continue
        if not stripped:
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            continue
        flush_list()
        flush_ordered_list()
        paragraph.append(stripped)

    flush_all()
    if current_chunks or not sections:
        sections.append((current_id, current_title, current_chunks.copy()))
        if not headings:
            headings.append((current_id, current_title))

    rendered_sections = []
    for section_id, title, chunks in sections:
        body = "\n  ".join(chunks)
        rendered_sections.append(
            f'<section class="doc-section reveal" id="{section_id}">\n'
            f'  <h2>{inline_markdown(title)}</h2>\n'
            f'  {body}\n'
            f'</section>'
        )
    return "\n".join(rendered_sections), headings, page_title


def meta_tags(page: Page, canonical: str) -> str:
    title = f"{page.title} · zh_catmut"
    desc = html.escape(page.description, quote=True)
    return f"""
    <meta name="description" content="{desc}">
    <meta name="robots" content="index,follow">
    <meta name="title" content="{html.escape(title, quote=True)}">
    <link rel="canonical" href="{canonical}">
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="assets/social/og-image.png">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="zh_catmut">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{html.escape(title, quote=True)}">
    <meta property="og:description" content="{desc}">
    <meta property="og:image" content="{OG_IMAGE}">
    <meta property="og:image:secure_url" content="{OG_IMAGE}">
    <meta property="og:image:type" content="image/png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{desc}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@MohamedHz72007">
    <meta name="twitter:creator" content="@MohamedHz72007">
    <meta name="twitter:url" content="{canonical}">
    <meta name="twitter:title" content="{html.escape(title, quote=True)}">
    <meta name="twitter:description" content="{desc}">
    <meta name="twitter:image" content="{OG_IMAGE}">
    <meta name="twitter:image:alt" content="{desc}">""".strip()


def nav_html(active_output: str) -> str:
    links = []
    for page in NAV:
        active = ' aria-current="page"' if page.output == active_output else ""
        links.append(f'<a href="{page.output}"{active}>{html.escape(page.nav_label or page.title)}</a>')
    return "\n".join(links)


def sidebar_html(headings: Iterable[tuple[str, str]]) -> str:
    links = "\n".join(f'<a href="#{section_id}">{html.escape(title)}</a>' for section_id, title in headings)
    return f'<aside class="docs-sidebar reveal" aria-label="Page contents"><strong>On this page</strong><nav>{links}</nav></aside>'


def render_page(page: Page) -> str:
    content, headings, parsed_title = render_markdown(page.source.read_text())
    hero_title = page.title if page.title != "Home" else parsed_title
    canonical = f"{BASE_URL}/" if page.output == "index.html" else f"{BASE_URL}/{page.output}"
    mermaid = "class=\"mermaid\"" in content
    canvas = '<canvas class="particle-canvas" data-particles aria-hidden="true"></canvas>' if page.landing else ""
    body_class = ' class="landing"' if page.landing else ""
    mermaid_script = """
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default" });
    </script>""" if mermaid else ""
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(page.title)} · zh_catmut</title>
    {meta_tags(page, canonical)}
    <link rel="stylesheet" href="assets/css/site.css">
  </head>
  <body{body_class}>
    <a class="skip-link" href="#main">Skip to content</a>
    {canvas}
    <div class="site-shell">
      <header class="nav">
        <div class="nav-inner">
          <a class="brand" href="index.html" aria-label="zh_catmut home">
            <span class="brand-mark" aria-hidden="true"></span>
            <span class="brand-text"><span class="brand-name">zh_catmut</span><span class="brand-subtitle">native categorical remapping</span></span>
          </a>
          <button class="nav-toggle" type="button" data-nav-toggle aria-label="Toggle navigation" aria-expanded="false"><span></span></button>
          <nav class="nav-links" aria-label="Primary navigation">
            {nav_html(page.output)}
          </nav>
        </div>
      </header>
      <main id="main">
        <section class="page-hero">
          <div class="container">
            <div class="reveal">
              <p class="eyebrow"><span class="eyebrow-dot"></span>{html.escape(page.description)}</p>
              <h1>{html.escape(hero_title)}</h1>
            </div>
            <div class="page-meta reveal">
              <div class="meta-box"><strong>Version</strong><span>0.2.0 / ABI 2</span></div>
              <div class="meta-box"><strong>Runtime</strong><span>Python 3.9+, NumPy >= 1.23, Pandas >= 2.0</span></div>
              <div class="meta-box"><strong>Native core</strong><span>Zig shared library through a C ABI</span></div>
            </div>
          </div>
        </section>
        <div class="container docs-layout">
          {sidebar_html(headings)}
          <article class="doc-article">
            {content}
          </article>
        </div>
      </main>
      <footer class="site-footer">
        <div class="footer-inner">
          <span>Apache-2.0 · Generated from Markdown by <code>scripts/build_docs.py</code></span>
          <div class="footer-links">
            <a href="index.html">Home</a>
            <a href="docs.html">Docs</a>
            <a href="changelog.html">Changelog</a>
            <a href="https://github.com/mohamedhossammohamed/zh_catmut">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
    <script src="assets/js/site.js" defer></script>
    {mermaid_script}
  </body>
</html>
"""


def write_sitemap() -> None:
    urls = []
    for page in PAGES:
        loc = f"{BASE_URL}/" if page.output == "index.html" else f"{BASE_URL}/{page.output}"
        urls.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{TODAY}</lastmod>\n"
            f"    <priority>{page.priority}</priority>\n"
            "  </url>"
        )
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def write_favicon() -> None:
    (DOCS / "assets" / "favicon.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#4da3ff"/><stop offset="0.55" stop-color="#f7a13d"/><stop offset="1" stop-color="#46d993"/></linearGradient></defs>
  <rect width="64" height="64" rx="16" fill="#070a12"/>
  <path d="M16 18h32L25 46h23" fill="none" stroke="url(#g)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="44" cy="20" r="5" fill="#46d993"/>
</svg>
"""
    )


def main() -> None:
    write_favicon()
    for page in PAGES:
        (DOCS / page.output).write_text(render_page(page))
    write_sitemap()


if __name__ == "__main__":
    main()
