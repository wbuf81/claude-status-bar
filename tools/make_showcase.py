#!/usr/bin/env python3
"""Build the README/showcase GIFs from the generated frames in Sources/DaisyFrames.swift.

    .venv/bin/python tools/make_showcase.py

Separate from the debug previews in art/preview/, which are deliberately 6x zoomed for inspecting
individual pixels. These are for the repo page, so they are sized to read as a menu bar
icon rather than as wall art.

One logical pixel already IS one device pixel on a 2x display - that is what makes the sprite crisp -
so the sprite's own dimensions are already a pixel-accurate Retina screenshot. menubar.gif therefore
composites her at 1:1. The per-clip tiles use 2x, an integer factor so they stay crisp, giving roughly
double menu-bar size: small enough to be honest, big enough to actually see.

Produces:
  art/showcase/<clip>.gif   one per clip, 2x, on a theme-neutral grey
  art/showcase/menubar.gif  her cycling states inside a mock menu bar, for honest scale
  art/showcase/all-clips.png  static contact sheet (4x, for DAISY.md)
"""

import base64
import io
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
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
    bar_h = 44
    pad_x = 10
    label_font = None                # default bitmap font; small text is all that is needed
    seq = []
    for name, label in MENUBAR_TOUR:
        frames, fps = data[name]
        # hold each state for roughly a second so the tour is readable
        holds = max(len(frames), int(fps))
        for i in range(holds):
            f = frames[i % len(frames)]
            icon = f                                  # 1:1 - see the note above
            w = pad_x * 2 + icon.width + (170 if label else 0)
            bar = Image.new("RGB", (max(360, w), bar_h), (238, 238, 240))
            d = ImageDraw.Draw(bar)
            d.line([(0, bar_h - 1), (bar.width, bar_h - 1)], fill=(205, 205, 210))
            bar.paste(icon, (pad_x, (bar_h - icon.height) // 2), icon)
            if label:
                d.text((pad_x + icon.width + 6, bar_h // 2 - 5), label, fill=(40, 40, 45),
                       font=label_font)
            seq.append((bar, int(1000 / fps)))
    out = [b.convert("P", palette=Image.ADAPTIVE) for b, _ in seq]
    out[0].save(OUT / "menubar.gif", save_all=True, append_images=out[1:],
                duration=[d for _, d in seq], loop=0, disposal=2)
    print(f"  menubar {out[0].width}x{bar_h} px, {len(out)} frames")

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
