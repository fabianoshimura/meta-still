"""Render a Sheet as one self-contained HTML page. Pure - no I/O.

Everything is inline: no CDN, no external stylesheet, no web font. The page is
opened from a local folder and must work with no network at all.
"""

from __future__ import annotations

from html import escape

from meta_still.contactsheet.domain.model import ClipEntry, Sheet

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #fbfbfa; --panel: #ffffff; --ink: #1a1a19; --muted: #6b6b68;
  --line: #e4e4e1; --accent: #4a5c8a; --shadow: rgba(0,0,0,.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16161a; --panel: #1e1e23; --ink: #ecece9; --muted: #9a9a96;
    --line: #2e2e35; --accent: #8fa5db; --shadow: rgba(0,0,0,.4);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
}
header {
  position: sticky; top: 0; z-index: 10; background: var(--panel);
  border-bottom: 1px solid var(--line); padding: 14px 20px;
  display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline;
}
h1 { font-size: 16px; margin: 0; font-weight: 600; }
.stats { color: var(--muted); font-size: 13px; }
#search {
  margin-left: auto; padding: 7px 11px; min-width: 220px;
  border: 1px solid var(--line); border-radius: 6px;
  background: var(--bg); color: var(--ink); font: inherit;
}
main { padding: 20px; max-width: 1600px; margin: 0 auto; }
section { margin-bottom: 34px; }
.group {
  font-size: 12px; letter-spacing: .06em; text-transform: uppercase;
  color: var(--muted); border-bottom: 1px solid var(--line);
  padding-bottom: 6px; margin-bottom: 16px;
}
.clip { margin-bottom: 22px; }
.clip-name {
  font-weight: 600; margin-bottom: 7px;
  overflow-wrap: anywhere;
}
.clip-name span { font-weight: 400; color: var(--muted); }
.strip { display: flex; flex-wrap: wrap; gap: 8px; }
.strip a {
  display: block; line-height: 0; border-radius: 5px; overflow: hidden;
  border: 1px solid var(--line); box-shadow: 0 1px 3px var(--shadow);
}
.strip a:hover { border-color: var(--accent); }
.strip img { display: block; width: 232px; height: auto; background: var(--line); }
.empty { color: var(--muted); font-style: italic; }
@media (max-width: 640px) { .strip img { width: 46vw; } }
"""

_SCRIPT = """
const box = document.getElementById('search');
const clips = Array.from(document.querySelectorAll('.clip'));
const sections = Array.from(document.querySelectorAll('section'));
const count = document.getElementById('shown');
box.addEventListener('input', () => {
  const q = box.value.trim().toLowerCase();
  let visible = 0;
  for (const clip of clips) {
    const hit = !q || clip.dataset.name.includes(q) || clip.dataset.group.includes(q);
    clip.hidden = !hit;
    if (hit) visible++;
  }
  for (const section of sections) {
    section.hidden = !section.querySelector('.clip:not([hidden])');
  }
  count.textContent = visible;
});
"""


def render_sheet(sheet: Sheet) -> str:
    parts = [
        "<title>" + escape(sheet.title) + " - contact sheet</title>",
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<style>" + _STYLE + "</style>",
        "<header>",
        "<h1>" + escape(sheet.title) + "</h1>",
        '<div class="stats"><span id="shown">'
        + str(len(sheet.clips))
        + "</span> clips &middot; "
        + str(sheet.total_stills)
        + " stills &middot; "
        + sheet.generated_at.strftime("%Y-%m-%d %H:%M")
        + "</div>",
        '<input id="search" type="search" placeholder="Filter by clip or folder…">',
        "</header>",
        "<main>",
    ]

    if not sheet.clips:
        parts.append('<p class="empty">No thumbnails found in this folder.</p>')

    for group_label, clips in sheet.grouped():
        parts.append("<section>")
        parts.append('<div class="group">' + escape(group_label) + "</div>")
        parts.extend(_render_clip(clip) for clip in clips)
        parts.append("</section>")

    parts.append("</main>")
    parts.append("<script>" + _SCRIPT + "</script>")
    return "\n".join(parts) + "\n"


def _render_clip(clip: ClipEntry) -> str:
    thumbs = "".join(
        '<a href="{href}" title="{label}"><img loading="lazy" src="{src}" alt="{label}"></a>'.format(
            href=escape(still.href, quote=True),
            src=escape(still.preview, quote=True),
            label=escape(still.label, quote=True),
        )
        for still in clip.stills
    )
    return (
        '<div class="clip" data-name="{key}" data-group="{group_key}">'
        '<div class="clip-name">{name} <span>&middot; {count} stills</span></div>'
        '<div class="strip">{thumbs}</div>'
        "</div>"
    ).format(
        key=escape(clip.name.lower(), quote=True),
        group_key=escape(clip.group_label.lower(), quote=True),
        name=escape(clip.name),
        count=len(clip.stills),
        thumbs=thumbs,
    )
