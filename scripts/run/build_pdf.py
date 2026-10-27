"""Combine all project Markdown documents into ONE PDF (cover + contents, page numbers, clickable outline).

Markdown -> HTML (python-markdown) -> PDF (Microsoft Edge headless, no extra install) -> page numbers and outline
(pypdf + reportlab). Two passes so that the contents page can show real page numbers.
Usage: envs\\modern312\\Scripts\\python scripts\\run\\build_pdf.py     -> docs/ISBL_complete_documentation.pdf"""
import datetime
import html
import io
import os
import re
import subprocess
import sys
import tempfile

import markdown
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "ISBL_complete_documentation.pdf")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TITLE = "Statement-level bug localization (ISBL): complete project documentation"

# (file, short description) in reading order; docs/architecture.md is empty and left out
DOCS = [
    ("docs/REPORT.md", "Illustrated report: pipelines, metrics with formulas, Lang-1 and Lang-2 results"),
    ("docs/experiments.md", "Experiments on Lang-1, Lang-2, Lang-3: IR models, SFL formulas, hybrid ranking"),
    ("docs/literature.md", "Literature scan for metrics and methods"),
    ("docs/reproduction.md", "Reproduction status and answers to the plan's questions"),
    ("docs/baseline.md", "Baseline metadata: pinned versions and commands"),
    ("docs/environment-audit.md", "Environment audit and blockers"),
    ("README.md", "Repository README: layout, setup, how to run"),
]

CSS = """
@page { size: A4; margin: 15mm 13mm 17mm 13mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.8pt; line-height: 1.42; color: #1a1a1a; }
section.doc { page-break-before: always; }
section.cover { page-break-after: always; }
h1 { font-size: 19pt; color: #1F3864; border-bottom: 2px solid #1F3864; padding-bottom: 3px; margin: 0 0 8px 0; }
h2 { font-size: 13.5pt; color: #1F3864; margin: 16px 0 5px 0; border-bottom: 1px solid #c9d3e6; padding-bottom: 2px; }
h3 { font-size: 11.2pt; color: #2F5597; margin: 12px 0 4px 0; }
h4 { font-size: 10pt; color: #2F5597; margin: 9px 0 3px 0; }
h1, h2, h3, h4 { page-break-after: avoid; }
p { margin: 4px 0 6px 0; }
ul, ol { margin: 3px 0 6px 0; padding-left: 20px; }
li { margin: 1px 0; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px 0; font-size: 8pt; line-height: 1.3; }
th code { background: rgba(255,255,255,0.22); color: #fff; }
th { background: #1F3864; color: #fff; text-align: left; padding: 3px 5px; border: 1px solid #1F3864; }
td { border: 1px solid #b9c2d3; padding: 2.5px 5px; vertical-align: top; word-break: normal; overflow-wrap: break-word; }
table.wide { font-size: 7.1pt; }
table.wide th, table.wide td { padding: 2px 3px; }
.nw { white-space: nowrap; }
tr { page-break-inside: avoid; }
tr:nth-child(even) td { background: #f5f7fb; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.4pt; background: #f1f1f1; padding: 0 2px; border-radius: 2px; word-break: break-word; }
pre { background: #f6f7f9; border: 1px solid #d5d9e0; border-radius: 3px; padding: 6px 8px; margin: 6px 0 9px 0; white-space: pre-wrap; word-break: break-word; font-size: 8pt; line-height: 1.32; }
pre code { background: none; padding: 0; font-size: 8pt; }
blockquote { margin: 7px 0; padding: 5px 11px; border-left: 4px solid #BF9000; background: #fff8e5; }
blockquote p { margin: 2px 0; }
img { display: block; max-width: 100%; max-height: 235mm; height: auto; margin: 8px auto; page-break-inside: avoid; }
a { color: #0563C1; text-decoration: none; }
hr { border: 0; border-top: 1px solid #cfd6e4; margin: 10px 0; }
.marker { color: #fff; font-size: 1px; line-height: 1px; }
.cover h1 { font-size: 26pt; border: 0; margin-top: 60mm; }
.cover .sub { font-size: 12pt; color: #444; margin-bottom: 14mm; }
.cover table { font-size: 10pt; }
.cover .note { font-size: 9pt; color: #555; margin-top: 10mm; }
"""


def _reindent_lists(text):
    """GitHub accepts 2-3 space nested lists, python-markdown needs 4: re-indent list items outside code fences."""
    out, fence = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
        if not fence:
            line = re.sub(r"^ {2,3}(?=(?:\d+\.|[-*]) )", "    ", line)
        out.append(line)
    return "\n".join(out)


def _post(body):
    """Mark tables with many columns as 'wide' (smaller font) and keep bug names such as Lang-1 on one line."""
    def table(m):
        head = m.group(0)
        n = len(re.findall(r"<th", head.split("</tr>")[0]))
        return head.replace("<table>", '<table class="wide">', 1) if n >= 9 else head
    body = re.sub(r"<table>.*?</tr>", table, body, flags=re.S)
    parts = re.split(r"(<[^>]+>)", body)
    for i, seg in enumerate(parts):
        if not seg.startswith("<"):
            parts[i] = re.sub(r"(?<![\w-])((?:Lang|LANG)-\d+)(?![\w-])", r'<span class="nw">\1</span>', seg)
    return "".join(parts)


def md_to_html(rel):
    path = os.path.join(ROOT, rel)
    text = _reindent_lists(open(path, encoding="utf-8").read())
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "nl2br"], output_format="html5")
    base = os.path.dirname(path)

    def fix(m):
        src = m.group(2)
        if re.match(r"^(https?:|file:|data:)", src):
            return m.group(0)
        absf = os.path.normpath(os.path.join(base, src)).replace("\\", "/")
        return '%ssrc="file:///%s"' % (m.group(1), absf)

    return _post(re.sub(r'(<img [^>]*?)src="([^"]+)"', lambda m: fix(m), body))


def headings(rel):
    """H1/H2 titles of a markdown file (for the outline)."""
    out = []
    in_code = False
    for line in open(os.path.join(ROOT, rel), encoding="utf-8"):
        if line.startswith("```"):
            in_code = not in_code
        m = re.match(r"^(#{1,2}) (.+?)\s*$", line)
        if m and not in_code:
            out.append((len(m.group(1)), re.sub(r"[`*_]", "", m.group(2))))
    return out


def build_html(start_pages=None):
    today = datetime.date(2026, 10, 27).isoformat()
    rows = []
    for i, (rel, desc) in enumerate(DOCS, start=1):
        pg = ("%d" % start_pages[i - 1]) if start_pages else "..."
        rows.append("<tr><td>%d</td><td><b>%s</b><br>%s</td><td><code>%s</code></td><td>%s</td></tr>"
                    % (i, html.escape(os.path.basename(rel)), html.escape(desc), html.escape(rel), pg))
    cover = ('<section class="cover"><h1>%s</h1><div class="sub">Reproduction of Li, Yue, Lan, Cui, IEEE SMC 2023, on Defects4J '
             'Lang-1, Lang-2 and Lang-3 (Windows, no WSL)<br>Compiled %s</div>'
             '<table><tr><th>#</th><th>Document</th><th>Source file</th><th>Page</th></tr>%s</table>'
             '<div class="note">All documents of the repository are combined in this order. Status: the pipeline works end to end and is '
             'tested, the paper\'s own results are <b>not</b> reproduced (3 of 373 bugs run). '
             'docs/architecture.md is empty and not included.</div></section>' % (html.escape(TITLE), today, "".join(rows)))
    parts = [cover]
    for i, (rel, _) in enumerate(DOCS, start=1):
        parts.append('<section class="doc"><span class="marker">DOCSTART-%d</span>%s</section>' % (i, md_to_html(rel)))
    return ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (html.escape(TITLE), CSS, "".join(parts)))


def render(html_text, pdf_path):
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "combined.html")
        open(hp, "w", encoding="utf-8").write(html_text)
        uri = "file:///" + hp.replace("\\", "/")
        cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
               "--virtual-time-budget=20000", "--print-to-pdf=" + pdf_path, uri]
        subprocess.run(cmd, check=True, timeout=240, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 1000:
        raise RuntimeError("Edge did not produce a PDF")


def find_starts(reader):
    starts = {}
    for p, page in enumerate(reader.pages):
        txt = page.extract_text() or ""
        for m in re.finditer(r"DOCSTART-(\d+)", txt):
            starts.setdefault(int(m.group(1)), p)
    return [starts[i] for i in range(1, len(DOCS) + 1)]


def finish(raw_pdf, final_pdf, starts):
    reader = PdfReader(raw_pdf)
    n = len(reader.pages)
    texts = [(reader.pages[p].extract_text() or "") for p in range(n)]   # read BEFORE the overlay is merged
    writer = PdfWriter()
    for p, page in enumerate(reader.pages):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(w / 2.0, 20, "Page %d of %d" % (p + 1, n))
        c.drawString(37, 20, "ISBL bug localization - project documentation")
        c.save()
        buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
        writer.add_page(page)
    # outline: one entry per document and its H2 sections (located by text on the pages of that document)
    bounds = starts + [n]
    for i, (rel, desc) in enumerate(DOCS):
        top = writer.add_outline_item("%d. %s" % (i + 1, os.path.basename(rel)), starts[i])
        for lvl, title in headings(rel):
            if lvl != 2:
                continue
            key = re.sub(r"\s+", " ", title)[:40]
            for p in range(starts[i], bounds[i + 1]):
                if key in re.sub(r"\s+", " ", texts[p]):
                    writer.add_outline_item(title[:90], p, parent=top)
                    break
    writer.add_metadata({"/Title": TITLE, "/Subject": "ISBL reproduction project: combined Markdown documentation"})
    writer.page_mode = "/UseOutlines"
    with open(final_pdf, "wb") as f:
        writer.write(f)
    return n


def main():
    with tempfile.TemporaryDirectory() as td:
        raw1, raw2 = os.path.join(td, "pass1.pdf"), os.path.join(td, "pass2.pdf")
        render(build_html(None), raw1)
        starts = find_starts(PdfReader(raw1))
        render(build_html([s + 1 for s in starts]), raw2)       # contents now shows real page numbers
        starts2 = find_starts(PdfReader(raw2))
        if starts2 != starts:
            print("note: page numbers shifted between passes:", starts, starts2)
        n = finish(raw2, OUT, starts2)
    print("wrote", OUT, "-", n, "pages; documents start on pages", [s + 1 for s in starts2])


if __name__ == "__main__":
    main()
