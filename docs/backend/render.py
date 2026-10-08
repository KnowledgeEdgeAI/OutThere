"""Render the backend Markdown docs with Python's standard library."""
from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parent
PAGES = [('design', 'index', 'Overview'), ('protocol', 'protocol', 'Events'),
         ('schema', 'schema', 'Database'), ('mobile', 'mobile', 'Mobile'),
         ('implementation', 'implementation', 'Build order')]

def inline(text):
    tokens = []
    def stash(value):
        tokens.append(value)
        return f'\x00{len(tokens)-1}\x00'
    text = re.sub(r'`([^`]+)`', lambda m: stash('<code>'+html.escape(m[1])+'</code>'), text)
    text = html.escape(text)
    def link(m):
        url = m[2]
        if url.endswith('.md'):
            url = ('index' if url == 'design.md' else url[:-3]) + '.html'
        return f'<a href="{url}">{m[1]}</a>'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], text)

def render(source):
    lines = source.splitlines(); output = []; toc = []; i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1; continue
        if line.startswith('```'):
            lang = line[3:]; block = []; i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                block.append(lines[i]); i += 1
            if lang == 'mermaid':
                output.append('<div class="architecture" aria-label="Architecture">'
                    '<div><strong>Mobile</strong><span>Screens · SQLite · outbox</span></div>'
                    '<span class="connector" aria-hidden="true">↔</span>'
                    '<div><strong>Application server</strong><span>Access · product rules · sync</span></div>'
                    '<span class="connector" aria-hidden="true">↔</span>'
                    '<div><strong>PostgreSQL</strong><span>Shared state · delivery · jobs</span></div>'
                    '<p>Worker → PostgreSQL, push &amp; media processing<br>Mobile ↔ private storage over HTTPS · Server → Places</p></div>')
            else:
                output.append('<pre><code>'+html.escape('\n'.join(block))+'</code></pre>')
            i += 1; continue
        if line.startswith('#'):
            level = len(line)-len(line.lstrip('#')); title = line[level:].strip()
            anchor = re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')
            if level == 2 or (level == 3 and title.startswith(('Chat ↔ Live', 'Ripple:', 'Discovery without'))): toc.append((anchor,title))
            output.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>'); i += 1; continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [x.strip() for x in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', x) for x in cells): rows.append(cells)
                i += 1
            output.append('<div class="table" tabindex="0" role="region" aria-label="Details table"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>'); continue
        if re.match(r'(- |\d+\. )',line):
            ordered = line[0].isdigit(); tag = 'ol' if ordered else 'ul'; items=[]
            while i < len(lines) and re.match(r'(- |\d+\. )',lines[i]):
                items.append(re.sub(r'^(- |\d+\. )','',lines[i])); i += 1
            output.append(f'<{tag}>'+''.join('<li>'+inline(x)+'</li>' for x in items)+f'</{tag}>'); continue
        paragraph = [line]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'(#|\||```|- |\d+\. )',lines[i]):
            paragraph.append(lines[i]); i += 1
        output.append('<p>'+inline(' '.join(paragraph))+'</p>')
    return '\n'.join(output), toc

CSS = '''
:root{color-scheme:light;--ink:#243b34;--muted:#64756c;--line:#dce3dc;--paper:#fafbf8;--soft:#eff3ed;--accent:#31664e}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.75 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:var(--accent);text-underline-offset:4px}a:hover{text-decoration-thickness:2px}a:focus-visible,summary:focus-visible,.table:focus-visible{outline:3px solid #a47748;outline-offset:4px}.shell{max-width:1240px;margin:auto;padding:32px 36px 72px}.brand{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);display:flex;justify-content:space-between;gap:20px}.brand a{letter-spacing:0;text-transform:none}nav.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0 38px;padding-bottom:22px;border-bottom:1px solid var(--line)}.tabs a{text-decoration:none;color:var(--muted);padding:7px 15px;border-radius:24px;font-size:13px}.tabs a:hover{background:var(--soft)}.tabs a[aria-current]{background:var(--ink);color:white}.layout{display:grid;grid-template-columns:190px minmax(0,1fr);gap:48px}aside{align-self:start;position:sticky;top:28px;font-size:12px}aside p{color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-size:10px;margin-top:0}aside a{display:block;text-decoration:none;padding:5px 0;color:var(--muted);line-height:1.5}article{min-width:0;max-width:880px}h1{font-size:clamp(30px,4vw,46px);line-height:1.14;letter-spacing:-.045em;font-weight:600;margin:0 0 24px;max-width:760px}h1+p{font-size:19px;line-height:1.6;color:var(--muted);margin-bottom:24px}h2{font-size:25px;line-height:1.3;letter-spacing:-.025em;font-weight:600;margin:48px 0 18px;padding-top:26px;border-top:1px solid var(--line)}h3{font-size:19px;font-weight:600;letter-spacing:-.015em;margin:32px 0 12px}p{margin:14px 0}li{padding-left:3px;margin:10px 0}ul,ol{padding-left:22px}strong{font-weight:600}code{font:12px/1.6 ui-monospace,SFMono-Regular,monospace;overflow-wrap:anywhere;background:var(--soft);border-radius:4px;padding:2px 5px}pre{padding:20px;background:var(--soft);border:1px solid var(--line);border-radius:10px;overflow:auto}pre code{padding:0;overflow-wrap:normal}.table{overflow-x:auto;border:1px solid var(--line);border-radius:10px;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.65}th,td{text-align:left;vertical-align:top;padding:13px 16px;border-bottom:1px solid var(--line)}th{font-weight:600;background:var(--soft)}th:first-child,td:first-child{min-width:150px}tr:last-child td{border-bottom:0}.architecture{display:grid;grid-template-columns:1fr auto 1.3fr auto 1fr;gap:12px;align-items:center;padding:24px 20px;border:1px solid var(--line);border-radius:12px;background:white;margin:24px 0}.architecture div{font-size:13px;text-align:center}.architecture span{display:block;font-size:11px;color:var(--muted)}.architecture .connector{font-size:19px}.architecture p{grid-column:1/-1;text-align:center;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:14px;margin:10px 0 0}footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.skip{position:absolute;left:20px;top:-100px;background:white;padding:10px}.skip:focus{top:10px}@media(max-width:900px){.layout{grid-template-columns:1fr;gap:24px}aside{position:static;border-bottom:1px solid var(--line);padding-bottom:20px}aside nav{display:flex;flex-wrap:wrap;gap:4px 18px}aside p{margin-bottom:8px}}@media(max-width:600px){.shell{padding:22px 18px 48px}.brand{font-size:10px}.tabs a{padding:6px 10px}.architecture{padding:18px 10px;gap:6px}.architecture strong{font-size:11px}.architecture span{font-size:10px}th,td{padding:10px 12px}h2{font-size:23px}h1+p{font-size:17px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{aside,.tabs,.brand a,.skip{display:none}.layout{display:block}.shell{padding:0}body{background:white;font-size:11px}h2{break-after:avoid}tr,pre,.architecture{break-inside:avoid}}
'''

def build():
    for src, dest, label in PAGES:
        body, toc = render((ROOT/f'{src}.md').read_text())
        tabs=''.join(f'<a href="{d}.html"'+(' aria-current="page"' if d==dest else '')+f'>{name}</a>' for _,d,name in PAGES)
        short_titles = {'Keep device choices on the device': 'Local settings', 'Fewer records, fewer things to keep in sync': 'Storage principles', 'Chat ↔ Live: one set of records': 'Chat and Live', 'Ripple: a soft ask before a plan': 'Ripple', 'Discovery without a profile interest score': 'Discovery', 'Precedence and platform references': 'Decisions and references'}
        contents=''.join(f'<a href="#{anchor}">{html.escape(short_titles.get(title, title))}</a>' for anchor,title in toc)
        page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="OutThere backend design: simple coordination for intimate and casual plans."><title>OutThere — {label}</title><style>{CSS}</style></head>
<body><a class="skip" href="#content">Skip to content</a><div class="shell"><header class="brand"><span>OutThere / Backend design</span><a href="../../index.html">View prototype ↗</a></header><nav class="tabs" aria-label="Design documents">{tabs}</nav><div class="layout"><aside><p>On this page</p><nav aria-label="Page sections">{contents}</nav></aside><article id="content">{body}<footer>Target design · 7 October 2026 · <a href="{src}.md">Markdown source</a><br>Implementation is in progress. See Build order for the verified scope.</footer></article></div></div></body></html>'''
        (ROOT/f'{dest}.html').write_text(page)

if __name__ == '__main__':
    build()
