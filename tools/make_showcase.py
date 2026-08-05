#!/usr/bin/env python3
"""Build the README/showcase GIFs from the generated frames in Sources/DaisyFrames.swift.

    .venv/bin/python tools/make_showcase.py

Separate from the debug previews in art/preview/, which are deliberately 6x zoomed for inspecting
individual pixels. These are for the repo page, so they are sized to read as a menu bar
icon rather than as wall art.

One logical pixel already IS one device pixel on a 2x display - that is what makes the sprite crisp -
so the sprite's own dimensions are already a pixel-accurate Retina screenshot. The menu-bar strips
therefore composite her at 1:1. The per-clip tiles use 2x, an integer factor so they stay crisp, giving roughly
double menu-bar size: small enough to be honest, big enough to actually see.

Produces:
  art/showcase/<clip>.gif   one per clip, 2x, on a theme-neutral grey
  art/showcase/menubar-{light,dark}.gif  her cycling states inside a mock menu bar, both appearances
  art/showcase/menubar-states.png  every state as a menu-bar row, light and dark, at 1:1
  art/showcase/all-clips.png  static contact sheet (4x, for DAISY.md)
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
OUT = ROOT / "art" / "showcase"

# 2x the logical grid = what a Retina menu bar physically shows. Integer, so still crisp.
TILE_ZOOM = 2
SHEET_ZOOM = 4
TILE_BG = (150, 150, 155)          # mid grey: legible on both GitHub themes

ORDER = ["sleep", "drowsy", "alert", "yawn", "trot", "zoomies", "dig", "sniff", "ask", "wag"]

# what the mock menu bar walks through, and the label shown beside her
MENUBAR_TOUR = [
    ("drowsy", ""),
    ("trot", "Thinking  0m 4s"),
    ("sniff", "Reading  0m 9s"),
    ("dig", "Editing  0m 14s"),
    ("zoomies", "Running command  0m 21s"),
    ("ask", "Awaiting permission"),
    ("wag", ""),
    ("sleep", ""),
]


def clips() -> dict:
    src = SWIFT.read_text()
    out = {}
    for name in ORDER:
        block = src.split(f'"{name}": DaisyClip(')[1]
        arr = block.split("frames: [", 1)[1].split("]", 1)[0]
        fps = float(re.search(r"fps:\s*([\d.]+)", block).group(1))
        b64 = re.findall(r'"([A-Za-z0-9+/=]{100,})"', arr)
        frames = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGBA") for b in b64]
        out[name] = (frames, fps)
    return out


def bar_font(size):
    """Menu-bar text is 13 pt, so 26 px at 2x. Pillow's default bitmap font looks nothing like
    macOS and was what made the old strip read as a mockup rather than a screenshot."""
    for p in ("/System/Library/Fonts/SFNS.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def neighbours(d, x, y, ink):
    """The status icons that sit to Daisy's right on a real bar: wifi, battery, control centre.

    Drawn rather than screenshotted so the strip carries no personal menu bar contents, and so it
    renders identically on any machine. Deliberately muted — they are context, not the subject.
    """
    # wifi: three arcs over a dot
    for i, r in enumerate((14, 9, 4)):
        d.arc([x - r, y - r + 4, x + r, y + r + 4], start=205, end=335, fill=ink, width=3)
    d.ellipse([x - 2, y + 6, x + 2, y + 10], fill=ink)
    # battery: rounded body, nub, part charge
    bx = x + 34
    d.rounded_rectangle([bx, y - 7, bx + 34, y + 8], radius=4, outline=ink, width=2)
    d.rounded_rectangle([bx + 3, y - 4, bx + 22, y + 5], radius=2, fill=ink)
    d.rounded_rectangle([bx + 36, y - 3, bx + 39, y + 4], radius=2, fill=ink)
    # control centre: two stacked sliders
    cx = bx + 52
    for row, knob in ((y - 5, 8), (y + 5, 18)):
        d.rounded_rectangle([cx, row - 2, cx + 24, row + 2], radius=2, fill=ink)
        d.ellipse([cx + knob - 3, row - 4, cx + knob + 3, row + 4], fill=ink)
    return cx + 30


def save_gif(frames, path, duration_ms, bg):
    out = []
    for f in frames:
        canvas = Image.new("RGB", f.size, bg)
        canvas.paste(f, (0, 0), f)
        out.append(canvas.convert("P", palette=Image.ADAPTIVE))
    out[0].save(path, save_all=True, append_images=out[1:],
                duration=duration_ms, loop=0, disposal=2)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = clips()

    # --- per-clip tiles at menu bar scale
    for name, (frames, fps) in data.items():
        z = [f.resize((f.width * TILE_ZOOM, f.height * TILE_ZOOM), Image.NEAREST) for f in frames]
        save_gif(z, OUT / f"{name}.gif", int(1000 / fps), TILE_BG)
        print(f"  {name:8s} {z[0].width}x{z[0].height} px, {len(z)}f @ {fps:g} fps")

    # --- mock menu bar, for honest scale
    #
    # NOT TILE_ZOOM here. One logical pixel already IS one device pixel on a 2x display, which is the
    # whole point of the sizing: the sprite's 41 px height is 20.5 pt. So the icon goes in at 1:1
    # against a 44 px bar (22 pt at 2x, matching NSStatusBar.system.thickness) and the result is a
    # pixel-accurate Retina screenshot. Zooming the icon here just overflowed the bar.
    #
    # Rendered in BOTH appearances. Daisy is drawn in full colour rather than as a template image
    # (`activeColor` is her own palette when animStyle == .daisy), so unlike the other three styles
    # she does not recolour for a dark bar — the dark strip is there to show honestly how that
    # lands. Her label does adapt, matching `applyTitle`.
    bar_h, pad_x, right_pad = 44, 16, 22
    width = 760
    f_bar = bar_font(26)
    themes = {
        "light": dict(bg=(246, 246, 247), rule=(214, 214, 218), ink=(32, 32, 34),
                      dim=(72, 72, 76)),
        "dark":  dict(bg=(38, 38, 41), rule=(58, 58, 62), ink=(238, 238, 240),
                      dim=(186, 186, 192)),
    }
    for theme, c in themes.items():
        seq = []
        for name, label in MENUBAR_TOUR:
            frames, fps = data[name]
            holds = max(len(frames), int(fps))       # hold ~1 s so the tour is readable
            for i in range(holds):
                icon = frames[i % len(frames)]       # 1:1 - see the note above
                bar = Image.new("RGB", (width, bar_h), c["bg"])
                d = ImageDraw.Draw(bar)
                d.line([(0, bar_h - 1), (width, bar_h - 1)], fill=c["rule"])

                clock = "Wed 3:41 PM"
                cw = d.textbbox((0, 0), clock, font=f_bar)[2]
                d.text((width - right_pad - cw, bar_h // 2 - 14), clock, font=f_bar, fill=c["ink"])
                # neighbours() returns its right edge; place its left edge by working backwards
                nx = width - right_pad - cw - 128
                neighbours(d, nx, bar_h // 2, c["dim"])

                lw = d.textbbox((0, 0), label, font=f_bar)[2] if label else 0
                x = nx - 30 - lw - icon.width - (8 if label else 0)
                bar.paste(icon, (x, (bar_h - icon.height) // 2), icon)
                if label:
                    d.text((x + icon.width + 8, bar_h // 2 - 14), label, font=f_bar, fill=c["ink"])
                seq.append((bar, int(1000 / fps)))
        out = [b.convert("P", palette=Image.ADAPTIVE) for b, _ in seq]
        out[0].save(OUT / f"menubar-{theme}.gif", save_all=True, append_images=out[1:],
                    duration=[d for _, d in seq], loop=0, disposal=2)
        print(f"  menubar-{theme} {width}x{bar_h} px, {len(out)} frames")

    # --- static "every state, in context" sheet
    #
    # The GIFs above are the honest thing but they make you WAIT for the state you care about. This
    # is the same content as a glance: one menu-bar row per state, at 1:1 like the strips, so the
    # sizing claim stays true. Light and dark side by side, since the dropdown offers both and her
    # full-colour sprite behaves differently on each.
    rows = [
        ("trot", "Thinking  0m 4s"), ("sniff", "Reading  0m 9s"), ("dig", "Editing  0m 14s"),
        ("zoomies", "Running command  0m 21s"), ("ask", "Awaiting permission"),
        ("wag", "Done"), ("drowsy", "Idle"), ("sleep", "Asleep"),
    ]
    # col_w fits the longest label ("Running command  0m 21s") plus icon and padding.
    col_w, row_h, gap = 400, 44, 6
    sheet_w, sheet_h = col_w * 2 + gap, row_h * len(rows) + gap * (len(rows) - 1)
    sheet = Image.new("RGB", (sheet_w, sheet_h), (150, 150, 155))
    sd = ImageDraw.Draw(sheet)
    for r, (name, label) in enumerate(rows):
        frames, _ = data[name]
        icon = frames[len(frames) // 2]
        y = r * (row_h + gap)
        for col, theme in enumerate(("light", "dark")):
            c = themes[theme]
            x0 = col * (col_w + gap)
            sd.rectangle([x0, y, x0 + col_w - 1, y + row_h - 1], fill=c["bg"])
            sheet.paste(icon, (x0 + 14, y + (row_h - icon.height) // 2), icon)
            sd.text((x0 + 14 + icon.width + 8, y + row_h // 2 - 14), label,
                    font=f_bar, fill=c["ink"])
    sheet.save(OUT / "menubar-states.png")
    print(f"  menubar-states.png {sheet_w}x{sheet_h}")

    # --- static contact sheet for DAISY.md
    firsts = [(n, data[n][0][0]) for n in ORDER]
    cw = max(i.width for _, i in firsts) * SHEET_ZOOM
    ch = max(i.height for _, i in firsts) * SHEET_ZOOM
    pad, lbl, cols = 10, 13, 5
    rows = (len(firsts) + cols - 1) // cols
    sheet = Image.new("RGB", (pad + cols * (cw + pad), pad + rows * (ch + lbl + pad)), (28, 28, 32))
    d = ImageDraw.Draw(sheet)
    for k, (n, im) in enumerate(firsts):
        r, c = divmod(k, cols)
        x, y = pad + c * (cw + pad), pad + r * (ch + lbl + pad)
        b = im.resize((im.width * SHEET_ZOOM, im.height * SHEET_ZOOM), Image.NEAREST)
        sheet.paste(b, (x + (cw - b.width) // 2, y + (ch - b.height)), b)
        d.text((x + 2, y + ch + 2), n, fill=(150, 150, 160))
    sheet.save(OUT / "all-clips.png")
    print(f"  all-clips.png {sheet.width}x{sheet.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
