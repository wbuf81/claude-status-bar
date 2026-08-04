#!/usr/bin/env python3
"""Build the GitHub social preview card from the generated frames in Sources/DaisyFrames.swift.

    .venv/bin/python tools/make_social_card.py

Produces art/showcase/social-card.png at 1280x640 - the size GitHub renders a repo's Open Graph
card at, and the size Slack, Discord, X and iMessage scale down from. GitHub has no API for this;
the file has to be uploaded by hand at Settings -> Social preview.

Design constraints that are NOT obvious:

  * She is pixel art on a ~100 px logical grid, so every enlargement is NEAREST and an INTEGER
    factor. A fractional or smoothed scale reintroduces exactly the smearing make_frames.py works
    to avoid, and it shows badly at card size.
  * The card gets thumbnailed hard in chat clients, so the title carries the card and the lineup is
    the supporting detail - not the other way round. All ten clips fit only as 5x2; ten in one row
    forces a 2x zoom, which is smaller than the README tiles and pointless on a 1280 px card.
  * The two rows are split by MEANING, not by the state order: everything she does while Claude is
    working on top, everything she does while waiting underneath. That is the whole app in one
    glance, and it also keeps the two sitting poses (ask, wag) out of adjacent cells.
  * Charcoal background, matching the contact sheet. Her coat is mostly black and tan, so a light
    card would need an outline round her; dark also sits better against Slack/Discord chrome.
  * Under 1 MB - GitHub rejects social previews above that. Flat background, no gradient, so the
    PNG stays in the low hundreds of KB.
"""

import base64
import io
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Pillow required: .venv/bin/pip install Pillow")

ROOT = Path(__file__).resolve().parent.parent
SWIFT = ROOT / "Sources" / "DaisyFrames.swift"
OUT = ROOT / "art" / "showcase" / "social-card.png"

W, H = 1280, 640
BG = (28, 28, 32)
INK = (242, 240, 236)              # title
MUTED = (154, 150, 146)            # tagline + labels
ACCENT = (217, 119, 87)            # Claude orange, for the kicker line

MARGIN = 76
MIN_GAP = 26                       # smallest breathing room between two sprites

TITLE = "Daisy Status Bar"
KICKER = "macOS menu bar  ·  Claude Code"
TAGLINE = "A Bernese Mountain Dog that reacts to what Claude Code is actually doing."
URL = "github.com/wbuf81/daisy-claude-status-bar"

# (clip, label, which frame reads best as a still), one list per row.
#
# Frames are chosen for SILHOUETTE, not for being the prettiest. Ten stills in a grid have to be
# tellable apart at thumbnail size, so: locomotion clips take their most extended pose (a contact
# frame reads as standing still), ask takes the frame with her paw at its highest, wag the one with
# her tail fully swung out, and alert the one with her ears clearly up - otherwise it is drowsy.
WORKING = [
    ("trot",    "thinking",   0),   # extended stride, legs clearly apart
    ("zoomies", "running",    0),   # full airborne gallop, dirt spray
    ("dig",     "editing",    2),   # front paws down in the hole, dirt flying
    ("sniff",   "reading",    0),   # nose flat to the ground
    ("ask",     "permission", 3),   # paw up highest
]
WAITING = [
    ("wag",     "done",       1),   # tail swung out, mouth open
    ("alert",   "ears up",    1),   # head raised, ears perked
    ("drowsy",  "idle",       0),
    ("sleep",   "asleep",     0),
    ("yawn",    "stretching", 2),   # mouth wide, front end stretched down
]
ROWS = [WORKING, WAITING]


def font(names, size):
    """First font that loads, from a list of macOS paths. Falls back to Pillow's bitmap font."""
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


BOLD = ["/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
REG = ["/System/Library/Fonts/SFNS.ttf",
       "/System/Library/Fonts/Helvetica.ttc",
       "/System/Library/Fonts/Supplemental/Arial.ttf"]


def clips() -> dict:
    """Same decode as make_showcase.py: base64 PNGs embedded in the generated Swift."""
    src = SWIFT.read_text()
    out = {}
    for name, _, _ in [c for row in ROWS for c in row]:
        block = src.split(f'"{name}": DaisyClip(')[1]
        arr = block.split("frames: [", 1)[1].split("]", 1)[0]
        b64 = re.findall(r'"([A-Za-z0-9+/=]{100,})"', arr)
        out[name] = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGBA") for b in b64]
    return out


def main() -> int:
    data = clips()
    picks = [[(lbl, data[name][idx]) for name, lbl, idx in row] for row in ROWS]

    # Uniform cell width, sized by the widest sprite in the whole cast, so both rows share one
    # column grid. Packing by each sprite's own width staggers the columns and reads as crooked.
    span = W - 2 * MARGIN
    cols = max(len(r) for r in picks)
    widest = max(im.width for r in picks for _, im in r)
    zoom = max(z for z in range(1, 9) if widest * z * cols + MIN_GAP * (cols - 1) <= span)
    cell = widest * zoom
    gap = (span - cell * cols) // (cols - 1)

    card = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(card)

    f_kick = font(BOLD, 21)
    f_title = font(BOLD, 66)
    f_tag = font(REG, 27)
    f_label = font(REG, 20)
    f_url = font(REG, 19)

    d.text((MARGIN, 44), KICKER, font=f_kick, fill=ACCENT)
    d.text((MARGIN, 74), TITLE, font=f_title, fill=INK)
    d.text((MARGIN, 162), TAGLINE, font=f_tag, fill=MUTED)

    uw = d.textbbox((0, 0), URL, font=f_url)[2]
    d.text((W - MARGIN - uw, 47), URL, font=f_url, fill=(104, 101, 98))

    # Each row is bottom-aligned on its own ground line, with a hairline rule along it. The rule is
    # doing real work: her lying poses are barely half the height of her sitting ones, so with no
    # floor to stand on the short clips read as floating rather than as lying down.
    for r, row in enumerate(picks):
        ground = 344 + r * 202
        d.line([(MARGIN, ground), (W - MARGIN, ground)], fill=(48, 48, 55))
        for c, (lbl, im) in enumerate(row):
            big = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
            x = MARGIN + c * (cell + gap)
            card.paste(big, (x + (cell - big.width) // 2, ground - big.height), big)
            tw = d.textbbox((0, 0), lbl, font=f_label)[2]
            d.text((x + (cell - tw) // 2, ground + 16), lbl, font=f_label, fill=MUTED)

    card.save(OUT)
    kb = OUT.stat().st_size / 1024
    print(f"  {OUT.relative_to(ROOT)}  {card.width}x{card.height}  {kb:.0f} KB  (sprites at {zoom}x)")
    if kb > 1024:
        print("  WARNING: over GitHub's 1 MB social preview limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
