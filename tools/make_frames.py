#!/usr/bin/env python3
"""Turn the raw Grok sprite sheets in art/raw/ into Sources/DaisyFrames.swift.

    python3 -m venv .venv && .venv/bin/pip install Pillow
    .venv/bin/python tools/make_frames.py

Why each step exists is documented in DAISY-PROMPTS.md; the short version:

  * The generator delivers a small logical canvas (100x100) upscaled to ~1024 and softened by JPEG
    compression. Resampling it would smear the pixel art, so the native grid is recovered by
    sampling the CENTRE of each logical block.
  * Backgrounds are never true #FF00FF (observed 199-245 R, 12-64 G, 149-218 B) but are always flat
    and always unambiguous against her palette, so the magenta key is deliberately generous.
  * Frames arrive in independent grid cells with inconsistent placement, so they are re-aligned onto
    one shared canvas: nose-align for locomotion, centroid-align for idle poses.
  * A few sheets need hand-coded repairs (a two-tailed frame, a mirrored-away facing direction, a
    sleep Z that teleports). Those live in ANIMATIONS below, not in the generic code path.
"""

from __future__ import annotations

import base64
import io
from typing import Optional
import sys
from collections import Counter, deque
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required:  python3 -m venv .venv && .venv/bin/pip install Pillow")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "art" / "raw"
OUT_SWIFT = ROOT / "Sources" / "DaisyFrames.swift"
PREVIEW = ROOT / "art" / "preview"

NATIVE = 100          # logical canvas the generator actually drew on
PALETTE_SIZE = 16     # NOT 8 - the art uses load-bearing anti-aliasing tones
PAD = 0               # no slack: every logical px of canvas height costs menu-bar height

# align: "nose"     - pin the muzzle (rightmost px) and ears (topmost px); for locomotion
#        "centroid" - balance the mass; for idle poses with no meaningful muzzle anchor
# mirror: flip every frame horizontally (fixes facing direction on side views)
# order:  frame indices to keep, in playback order. Negative index means "mirror of |i|-1",
#         used to manufacture a missing pose from a symmetrical front view.
# intro:  how many leading frames play once before the rest loops
# loop:   False for one-shot sequences
ANIMATIONS = {
    "sleep": dict(
        file="01-sleep.png", grid=(2, 2), align="centroid", fps=3.0,
        order=[0, 1, 2, 3], fix="sleep_z",
        note="Z is a separate blob; its x position teleports, so fix_sleep_z re-places it.",
    ),
    "drowsy": dict(
        file="02-blink.png", grid=(2, 2), align="centroid", fps=2.5,
        order=[0, 2],   # f2 is a duplicate of f1 (half-lid never rendered); f4 split into "alert"
        note="2-state blink. f4 lives in the 'alert' clip because it is 22% different.",
    ),
    "alert": dict(
        file="02-blink.png", grid=(2, 2), align="centroid", fps=1.4,
        order=[0, 3], loop=False,
        note="Ears perk + head lift. Occasional idle beat; strobes if looped every cycle.",
    ),
    "trot": dict(
        file="03-trot.png", grid=(2, 2), align="nose", fps=9.0,
        order=[0, 1, 2, 3],
    ),
    "dig": dict(
        file="04-dig.png", grid=(2, 2), align="nose", fps=10.0,
        order=[0, 1, 2, 3], intro=1,
        note="f1 has no dirt at all, so it flickers if looped. Plays once as a wind-up.",
    ),
    "sniff": dict(
        file="05-sniff.png", grid=(2, 2), align="nose", fps=7.0,
        order=[0, 1, 2, 3],
    ),
    "zoomies": dict(
        file="06-zoomies.png", grid=(2, 2), align="nose", fps=14.0,
        order=[0, 1, 2, 3],
        note="Pale speed puffs arrive as separate blobs; DaisyRender inks them instead of "
             "punching them out, else they vanish in System mode.",
    ),
    "ask": dict(
        file="07-ask.png", grid=(2, 2), align="centroid", fps=3.5,
        order=[0, 1, 2, 3],
    ),
    "wag": dict(
        file="08-wag.png", grid=(2, 2), align="centroid", fps=11.0,
        order=[0, 1, -1, 3],   # -1 => mirror of frame 0, replacing the two-tailed generated f3
        note="Generated f3 had TWO TAILS. Discarded; mirror(f1) supplies the tail-sweeps-right pose.",
    ),
    "yawn": dict(
        file="09-yawn.png", grid=(2, 2), align="centroid", fps=2.2,
        order=[0, 1, 2, 3], mirror=True, loop=False,
        note="Generated facing LEFT while every other side view faces right.",
    ),
}


# ---------------------------------------------------------------- grid + keying

def to_native(path: Path, n: int = NATIVE) -> Image.Image:
    """Recover the logical pixel grid by sampling the centre of each block."""
    src = Image.open(path).convert("RGB")
    w, h = src.size
    sp = src.load()
    out = Image.new("RGB", (n, n))
    op = out.load()
    for gy in range(n):
        for gx in range(n):
            op[gx, gy] = sp[int((gx + 0.5) * w / n), int((gy + 0.5) * h / n)]
    return out


def is_background(p) -> bool:
    """Generous magenta test - the generator never emits true #FF00FF."""
    r, g, b = p
    return r > 120 and b > 110 and g < 120 and (r + b) / 2 - g > 60


def key_background(img: Image.Image) -> Image.Image:
    n = img.width
    sp = img.load()
    out = Image.new("RGBA", img.size)
    op = out.load()
    for y in range(n):
        for x in range(n):
            op[x, y] = (0, 0, 0, 0) if is_background(sp[x, y]) else (*sp[x, y], 255)
    return out


def despeckle(img: Image.Image) -> Image.Image:
    """Replace surviving magenta-ish pixels with their neighbours' majority colour.

    A handful of pixels sit between the background and the outline and squeak past the key,
    showing up as stray pink dots inside her. Quantising alone would snap them to some
    arbitrary palette entry, so they are resolved from context first.
    """
    w, h = img.size
    sp = img.load()
    out = img.copy()
    op = out.load()
    fixed = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if not a:
                continue
            if (r + b) / 2 - g > 45 and b > 90 and r > 110:   # still looks like background bleed
                votes = Counter()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if (dx or dy) and 0 <= nx < w and 0 <= ny < h:
                            nr, ng, nb, na = sp[nx, ny]
                            if na and not ((nr + nb) / 2 - ng > 45 and nb > 90 and nr > 110):
                                votes[(nr, ng, nb)] += 1
                if votes:
                    op[x, y] = (*votes.most_common(1)[0][0], 255)
                    fixed += 1
    return out, fixed


# ---------------------------------------------------------------- frame splitting

def blobs_in(img: Image.Image, box) -> list[list[tuple[int, int]]]:
    x0, y0, x1, y1 = box
    a = img.getchannel("A").load()
    seen: set[tuple[int, int]] = set()
    found = []
    for sy in range(y0, y1):
        for sx in range(x0, x1):
            if not a[sx, sy] or (sx, sy) in seen:
                continue
            q = deque([(sx, sy)])
            seen.add((sx, sy))
            cells = []
            while q:
                x, y = q.popleft()
                cells.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    nx, ny = x + dx, y + dy
                    if x0 <= nx < x1 and y0 <= ny < y1 and a[nx, ny] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            if len(cells) >= 4:       # anything smaller is compression grit
                found.append(cells)
    found.sort(key=len, reverse=True)
    return found


class Frame:
    """One cell: the dog blob plus any particle blobs (dirt, speed puffs, the sleep Z)."""

    def __init__(self, dog, particles, src: Image.Image):
        self.dog = dog
        self.particles = particles
        self.src = src

    @property
    def dog_box(self):
        xs = [c[0] for c in self.dog]; ys = [c[1] for c in self.dog]
        return min(xs), min(ys), max(xs), max(ys)

    def pixels(self):
        for cells, is_particle in ((self.dog, False), *[(p, True) for p in self.particles]):
            for x, y in cells:
                yield x, y, is_particle


def split(img: Image.Image, grid) -> list[Frame]:
    cols, rows = grid
    n = img.width
    cw, ch = n // cols, n // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            bs = blobs_in(img, (c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            if not bs:
                continue
            frames.append(Frame(bs[0], bs[1:], img))
    return frames


# ---------------------------------------------------------------- repairs

def fix_sleep_z(frames: list[Frame]) -> list[Frame]:
    """Re-place the sleep Z on a clean rising diagonal.

    Grok drew the Z at inconsistent x positions (right, left, centre, right), so it teleports
    rather than drifting upward. The Z is a separate blob, so it can simply be moved. Frame
    sizes are small/big/big/small, which suits low -> mid -> high -> reset.
    """
    rise = [0, 3, 6, 0]        # logical px lifted above the base
    drift = [0, 1, 2, 0]       # px drifted toward her nose
    out = []
    for i, f in enumerate(frames):
        if not f.particles:
            out.append(f)
            continue
        dx0, dy0, dx1, dy1 = f.dog_box
        z = max(f.particles, key=len)
        zx0 = min(c[0] for c in z); zy1 = max(c[1] for c in z)
        # anchor: just above her head, which is the right-hand end of the curled body
        tx = dx1 - 6 + drift[i % 4]
        ty = dy0 - 1 - rise[i % 4]
        shift = (tx - zx0, ty - zy1)
        moved = [(x + shift[0], y + shift[1]) for x, y in z]
        others = [p for p in f.particles if p is not z]
        out.append(Frame(f.dog, [moved, *others], f.src))
    return out


FIXES = {"sleep_z": fix_sleep_z}


# ---------------------------------------------------------------- alignment

def place(frame: Frame, canvas, align: str, mirror: bool):
    """Render one frame onto the shared canvas. Returns (RGBA image, particle mask)."""
    cw, ch = canvas
    sp = frame.src.load()
    dx0, dy0, dx1, dy1 = frame.dog_box
    dw, dh = dx1 - dx0 + 1, dy1 - dy0 + 1

    if align == "nose":
        # pin the muzzle to the right edge and the ears to the top: her head holds still
        ox = cw - PAD - dw - dx0
        oy = PAD - dy0
    else:
        cx = sum(c[0] for c in frame.dog) / len(frame.dog)
        cy = sum(c[1] for c in frame.dog) / len(frame.dog)
        ox = int(round(cw / 2 - cx))
        oy = int(round(ch / 2 - cy))

    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    mask = Image.new("L", canvas, 0)
    ip, mp = img.load(), mask.load()
    for x, y, is_particle in frame.pixels():
        tx, ty = x + ox, y + oy
        if 0 <= tx < cw and 0 <= ty < ch:
            ip[tx, ty] = sp[x, y]
            if is_particle:
                mp[tx, ty] = 255
    if mirror:
        img = ImageOps.mirror(img)
        mask = ImageOps.mirror(mask)
    return img, mask


# ---------------------------------------------------------------- palette

MERGE_DIST = 18       # colours closer than this are visually identical at 36px

def build_palette(images: list[Image.Image]) -> list[tuple[int, int, int]]:
    """One shared palette across every animation, so she looks like the same dog throughout.

    Plain median-cut allocates slots by pixel population, and she is mostly black - a first pass
    spent 11 of 16 entries on near-identical darks (within 5 RGB of each other, indistinguishable)
    while rust got 2. So: over-quantise, then greedily keep the most populous colours while
    rejecting any that duplicate one already chosen. That reallocates the wasted slots onto the
    mid-tones that actually carry the markings.
    """
    pool = []
    for im in images:
        sp = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = sp[x, y]
                if a:
                    pool.append((r, g, b))
    strip = Image.new("RGB", (len(pool), 1))
    strip.putdata(pool)
    over = strip.quantize(colors=64, method=Image.MEDIANCUT).convert("RGB")
    ranked = Counter(over.getdata()).most_common()

    chosen: list[tuple[int, int, int]] = []
    for colour, _ in ranked:
        if len(chosen) >= PALETTE_SIZE:
            break
        r, g, b = colour
        if all((r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2 >= MERGE_DIST ** 2 for c in chosen):
            chosen.append(colour)
    return chosen


def snap(img: Image.Image, palette) -> Image.Image:
    sp = img.load()
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    op = out.load()
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = sp[x, y]
            if not a:
                continue
            key = (r, g, b)
            if key not in cache:
                cache[key] = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            op[x, y] = (*cache[key], 255)
    return out


# ---------------------------------------------------------------- emit

def b64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def swift_source(clips: dict, canvas, palette) -> str:
    cw, ch = canvas
    L = []
    L.append("// Auto-generated by tools/make_frames.py - do not edit by hand.")
    L.append("//")
    L.append(f"// {len(clips)} clips, {sum(len(c['frames']) for c in clips.values())} frames, "
             f"{cw}x{ch} logical px on a shared canvas, {len(palette)}-colour shared palette.")
    L.append("// Rendered 1 logical px = 1 device px on a 2x display, so nothing is ever resampled.")
    L.append("")
    L.append("import CoreGraphics   // CGFloat")
    L.append("")
    L.append(f"let daisyCanvas = (w: {cw}, h: {ch})")
    L.append("")
    L.append("/// Draw at exactly this many points tall so one logical pixel lands on one device")
    L.append(f"/// pixel on a 2x display ({ch} px / 2 = {ch/2:g} pt). Any other height resamples the")
    L.append("/// sprite and smears the pixel art - which is the whole reason the art is pixel art.")
    L.append("///")
    L.append("/// Upstream's other styles hard-code 18 pt (main.swift, crabIcon). Daisy's tallest pose")
    L.append(f"/// is {ch} logical px, so 18 pt would mean a {18*2/ch:.2f}x non-integer downscale. Trading a")
    L.append("/// slightly taller icon for a crisp one is the deliberate choice here.")
    L.append(f"let daisyPointHeight: CGFloat = {ch/2:g}")
    L.append("")
    L.append("/// One animation clip. `intro` frames play once, then the remainder loops")
    L.append("/// (or plays once more and stops, when `loops` is false).")
    L.append("struct DaisyClip {")
    L.append("    let frames: [String]   // base64 PNG, decoded once and cached")
    L.append("    let fps: Double")
    L.append("    let loops: Bool")
    L.append("    let intro: Int")
    L.append("    /// Indices of frames whose particle pixels (dirt, speed puffs, the sleep Z) must be")
    L.append("    /// drawn as ink in System colour mode instead of punched out as holes.")
    L.append("    let particleMasks: [String?]")
    L.append("}")
    L.append("")
    L.append("let daisyClips: [String: DaisyClip] = [")
    for name, c in clips.items():
        if c.get("note"):
            L.append(f"    // {c['note']}")
        L.append(f'    "{name}": DaisyClip(')
        L.append("        frames: [")
        for f in c["frames"]:
            L.append(f'            "{f}",')
        L.append("        ],")
        L.append(f'        fps: {c["fps"]}, loops: {str(c["loops"]).lower()}, intro: {c["intro"]},')
        L.append("        particleMasks: [")
        for m in c["masks"]:
            L.append(f'            "{m}",' if m else "            nil,")
        L.append("        ]),")
    L.append("]")
    L.append("")
    return "\n".join(L)


def main() -> int:
    if not RAW.is_dir():
        sys.exit(f"missing {RAW}")
    PREVIEW.mkdir(parents=True, exist_ok=True)

    # --- pass 1: split every sheet, discover the shared canvas size
    staged = {}
    for name, spec in ANIMATIONS.items():
        path = RAW / spec["file"]
        if not path.exists():
            sys.exit(f"missing {path}")
        nat = to_native(path)
        keyed = key_background(nat)
        keyed, fixed = despeckle(keyed)
        frames = split(keyed, spec["grid"])
        if fix := spec.get("fix"):
            frames = FIXES[fix](frames)
        staged[name] = (spec, frames)
        boxes = [f.dog_box for f in frames]
        print(f"{name:8s} {len(frames)} cells, dog "
              f"{max(b[2]-b[0]+1 for b in boxes)}x{max(b[3]-b[1]+1 for b in boxes)}, "
              f"{sum(len(f.particles) for f in frames)} particle blobs"
              + (f", despeckled {fixed}px" if fixed else ""))

    # canvas must hold the widest and tallest content of any frame we actually keep
    cw = ch = 0
    for name, (spec, frames) in staged.items():
        for idx in spec["order"]:
            f = frames[abs(idx) - 1 if idx < 0 else idx]
            xs = [x for x, _, _ in f.pixels()]; ys = [y for _, y, _ in f.pixels()]
            cw = max(cw, max(xs) - min(xs) + 1)
            ch = max(ch, max(ys) - min(ys) + 1)
    canvas = (cw + PAD * 2, ch + PAD * 2)
    print(f"\nshared canvas: {canvas[0]}x{canvas[1]} logical px "
          f"-> {canvas[0]/2:.1f}x{canvas[1]/2:.1f} pt at 1 logical px per device px on 2x")

    # --- pass 2: place, then build one palette from everything
    placed = {}
    for name, (spec, frames) in staged.items():
        seq = []
        for idx in spec["order"]:
            f = frames[abs(idx) - 1 if idx < 0 else idx]
            img, mask = place(f, canvas, spec["align"], spec.get("mirror", False))
            if idx < 0:                      # manufacture the missing pose by mirroring
                img, mask = ImageOps.mirror(img), ImageOps.mirror(mask)
            seq.append((img, mask))
        placed[name] = (spec, seq)

    palette = build_palette([im for _, seq in placed.values() for im, _ in seq])
    print(f"shared palette ({len(palette)}): {palette}")

    # --- pass 3: snap to palette, encode
    clips = {}
    for name, (spec, seq) in placed.items():
        frames_b64, masks_b64 = [], []
        for img, mask in seq:
            frames_b64.append(b64_png(snap(img, palette)))
            masks_b64.append(b64_png(mask) if mask.getbbox() else None)
        clips[name] = dict(frames=frames_b64, masks=masks_b64, fps=spec["fps"],
                           loops=spec.get("loop", True), intro=spec.get("intro", 0),
                           note=spec.get("note"))

    OUT_SWIFT.write_text(swift_source(clips, canvas, palette))
    total = sum(len(c["frames"]) for c in clips.values())
    kb = OUT_SWIFT.stat().st_size / 1024
    print(f"\nwrote {OUT_SWIFT.relative_to(ROOT)}  ({total} frames, {kb:.0f} KB)")

    # --- previews so a human can sanity-check without launching the app
    for name, (spec, seq) in placed.items():
        z = 6
        strip = Image.new("RGB", ((canvas[0] * z + 4) * len(seq) + 4, canvas[1] * z + 8), (150, 150, 155))
        for i, (img, _) in enumerate(seq):
            b = snap(img, palette).resize((canvas[0] * z, canvas[1] * z), Image.NEAREST)
            strip.paste(b, (4 + i * (canvas[0] * z + 4), 4), b)
        strip.save(PREVIEW / f"{name}.png")
        gif = []
        for img, _ in seq:
            c = Image.new("RGB", (canvas[0] * z, canvas[1] * z), (150, 150, 155))
            b = snap(img, palette).resize((canvas[0] * z, canvas[1] * z), Image.NEAREST)
            c.paste(b, (0, 0), b)
            gif.append(c.convert("P", palette=Image.ADAPTIVE))
        gif[0].save(PREVIEW / f"{name}.gif", save_all=True, append_images=gif[1:],
                    duration=int(1000 / spec["fps"]), loop=0, disposal=2)
    print(f"wrote {len(placed)*2} preview files to {PREVIEW.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
