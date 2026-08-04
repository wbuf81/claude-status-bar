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
    one shared canvas by a feature of the DOG: her muzzle and ear line for locomotion, her ground
    line and head centre for lying and sitting poses. Never her centre of mass - whatever moves
    drags the centroid with it, so centroid-aligning compensates for the motion and cancels it.
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

# Per-clip enlargement, to stop her SHORT poses looking undersized in the menu bar.
#
# The canvas is sized by her tallest pose (sitting, 42 px). A lying pose is only ~30 px, so at one
# logical pixel per device pixel it renders about 15 pt of dog inside a 21 pt slot while neighbouring
# menu bar icons show ~18 pt. Short clips are therefore scaled up toward the canvas height.
#
# This RESAMPLES, and there is no way around that: the menu bar affords 44 device px, so a 30 px
# sprite has no integer scale between 1x (15 pt) and 2x (30 pt, far over the bar). NEAREST is used
# rather than a smooth filter - it leaves some pixels 1 device px and some 2, which reads better on
# pixel art than uniform blur.
#
# Set to 1.0 to disable entirely and go back to strictly crisp, physically-consistent scaling.
MAX_UPSCALE = 1.15

# align: "nose"   - pin the muzzle (rightmost px) and ears (topmost px); for locomotion
#        "ground" - pin her ground line and head centre; for lying and sitting poses
#        "ground-front" - ground line + front end; for the stretch, whose raised rump
#                         breaks the "top rows are her head" assumption
# mirror: flip every frame horizontally (fixes facing direction on side views)
# order:  frame indices to keep, in playback order. Negative index means "mirror of |i|-1",
#         used to manufacture a missing pose from a symmetrical front view.
# intro:  how many leading frames play once before the rest loops
# loop:   False for one-shot sequences
ANIMATIONS = {
    "sleep": dict(
        file="01-sleep.png", grid=(2, 2), align="ground", fps=3.0,
        order=[0, 2, 3], fix="sleep_z",
        note="Frame 1 dropped: its tail flick reads as a paw sticking out of her back. Z is a "
             "separate blob whose x position teleports, so fix_sleep_z re-places it on a rise.",
    ),
    "drowsy": dict(
        file="02-blink.png", grid=(2, 2), align="ground", fps=2.5,
        order=[0, 2],   # f2 is a duplicate of f1 (half-lid never rendered); f4 split into "alert"
        note="2-state blink. f4 lives in the 'alert' clip because it is 22% different.",
    ),
    "alert": dict(
        file="02-blink.png", grid=(2, 2), align="ground", fps=1.4,
        order=[0, 3], loop=False,
        note="Ears perk + head lift. Occasional idle beat; strobes if looped every cycle.",
    ),
    "trot": dict(
        file="03-trot.png", grid=(2, 2), align="nose", fps=6.5,
        order=[0, 1, 2, 3],
    ),
    "dig": dict(
        file="04-dig.png", grid=(2, 2), align="nose", fps=4.5,
        order=[0, 1, 2, 3], intro=1,
        note="f1 has no dirt at all, so it flickers if looped. Plays once as a wind-up.",
    ),
    "sniff": dict(
        file="05-sniff.png", grid=(2, 2), align="nose", fps=4.5,
        order=[0, 1, 2, 3],
    ),
    "zoomies": dict(
        file="06-zoomies.png", grid=(2, 2), align="nose", fps=9.5,
        order=[0, 1, 2, 3],
        note="Regenerated after review: the first sheet had no compression phase - all four frames "
             "were extended sprint poses, so her front legs never folded under her and she looked "
             "like she was floating rather than running. This one has a real tuck (f3 is 36 px long "
             "against 43 at full extension). Dust is DARK by request (luminance ~65) so it inks "
             "natively in System mode instead of relying on the particle mask.",
    ),
    "ask": dict(
        file="07-ask.png", grid=(2, 2), align="ground", fps=3.5,
        order=[0, 1, 2, 3],
    ),
    "wag": dict(
        file="08-wag.png", grid=(2, 2), align="ground", fps=6.0,
        order=[0, 1, 2, 3],
        note="Regenerated with her body explicitly locked. The first sheet asked for a sweeping tail "
             "AND a body bouncing 3-4 px, which at 21 pt read as noise: the central body region was "
             "changing ~48% per frame. It is now 9.8%, essentially just the mouth. That earlier sheet "
             "also gave frame 3 two tails, which prompted faking the opposite side by mirroring f1 - "
             "REJECTED, because she measures 31.6% different from her own mirror, so the flip swung "
             "her whole body rather than her tail. Fine as a still, a twitch in motion. This sheet "
             "keeps the tail on one side and flicks it low/up/low/up-with-a-bark; with the body still, "
             "that reads cleanly, and the frame rate went back from 4 to 6 fps once the bounce was "
             "gone.",
    ),
    "yawn": dict(
        file="09-yawn.png", grid=(2, 2), align="ground-front", fps=2.2,
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
    """One cell: the dog blob plus any particle blobs (dirt, speed puffs, the sleep Z).

    Pixels carry their own colour rather than being looked up in the source image, so a frame can be
    mirrored or a particle moved without the colours going with the old coordinates.
    """

    def __init__(self, dog, particles):
        self.dog = dog                  # [(x, y, rgba)]
        self.particles = particles      # [[(x, y, rgba)], …]

    @property
    def dog_box(self):
        xs = [p[0] for p in self.dog]; ys = [p[1] for p in self.dog]
        return min(xs), min(ys), max(xs), max(ys)

    def pixels(self):
        for cells, is_particle in ((self.dog, False), *[(p, True) for p in self.particles]):
            for x, y, rgba in cells:
                yield x, y, rgba, is_particle

    def content_box(self):
        """Extents of EVERYTHING, particles included - what actually has to fit on the canvas."""
        xs = [p[0] for p in self.pixels()]; ys = [p[1] for p in self.pixels()]
        return min(xs), min(ys), max(xs), max(ys)

    def mirrored(self) -> "Frame":
        """Flip horizontally about the dog's own bounding box.

        Mirroring here rather than flipping the finished canvas matters: a canvas flip maps
        x -> CW-1-x, which shifts an even-width sprite half a pixel and made the wag visibly jitter
        as it swapped sides. Flipping in source space keeps alignment exact.
        """
        dx0, _, dx1, _ = self.dog_box
        flip = lambda cells: [(dx0 + dx1 - x, y, rgba) for x, y, rgba in cells]
        return Frame(flip(self.dog), [flip(p) for p in self.particles])


def split(img: Image.Image, grid) -> list[Frame]:
    cols, rows = grid
    n = img.width
    cw, ch = n // cols, n // rows
    sp = img.load()
    frames = []
    for r in range(rows):
        for c in range(cols):
            bs = blobs_in(img, (c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            if not bs:
                continue
            with_colour = [[(x, y, sp[x, y]) for x, y in blob] for blob in bs]
            frames.append(Frame(with_colour[0], with_colour[1:]))
    return frames


# ---------------------------------------------------------------- repairs

def fix_sleep_z(frames: list[Frame]) -> list[Frame]:
    """Re-place the sleep Z on a clean rising diagonal.

    Grok drew the Z at inconsistent x positions (right, left, centre, right), so it teleports rather
    than drifting upward. The Z is a separate blob, so it can simply be moved.

    Indexed by ORIGINAL frame number, because the ANIMATIONS order below drops frame 1 (its tail
    flick reads as a paw sticking out of her back). Used frames are 0, 2, 3 -> small/low, big/mid,
    small/high, which plays as a Z puffing up and drifting away.
    """
    rise = [0, 0, 3, 6]        # logical px lifted above her head
    drift = [0, 0, 1, 2]       # px drifted toward her nose as it rises
    out = []
    for i, f in enumerate(frames):
        if not f.particles:
            out.append(f)
            continue
        dx0, dy0, dx1, dy1 = f.dog_box
        z = max(f.particles, key=len)
        zx0 = min(p[0] for p in z); zy1 = max(p[1] for p in z)
        # anchor just above her head, which is the right-hand end of the curled body
        tx = dx1 - 6 + drift[i % 4]
        ty = dy0 - 1 - rise[i % 4]
        sx, sy = tx - zx0, ty - zy1
        moved = [(x + sx, y + sy, rgba) for x, y, rgba in z]
        others = [p for p in f.particles if p is not z]
        out.append(Frame(f.dog, [moved, *others]))
    return out


FIXES = {"sleep_z": fix_sleep_z}


# ---------------------------------------------------------------- alignment

def anchor_of(frame: Frame, align: str) -> tuple[int, int]:
    """The point on the dog that holds still from frame to frame.

    Frames arrive at inconsistent positions inside their grid cells, so every frame is positioned by
    a feature of the DOG rather than by its cell.

      nose   - muzzle (rightmost px) and ear line (topmost px). Her head stays put and the legs do
               the moving, which reads far better on a run cycle than planting her feet: frame
               heights vary by 5 px, so pinning the bottom makes her pogo.
      ground - her ground line (lowest px) plus the horizontal centre of her HEAD. For every pose
               where she is lying, sitting or stretching, i.e. in contact with the floor.

    Anchoring on the centre of MASS was a mistake and is deliberately gone. Whatever moves - ears
    lifting, a tail sweeping - drags the centroid with it, so aligning on the centroid compensates for
    the motion and cancels it out. It cut the ear-perk from 22% different in the source sheet down to
    6.5%, i.e. to nearly invisible. The head centre is used horizontally for the same reason: a tail
    sweeping side to side would otherwise pull the whole dog after it.
    """
    dx0, dy0, dx1, dy1 = frame.dog_box
    if align == "nose":
        return dx1, dy0
    if align == "ground-front":
        # her front end (rightmost px) plus the ground line. For the stretch-and-yawn, where the
        # "top rows are her head" assumption below is false - in a downward-dog her raised rump is
        # the top of the sprite, so a head-centre anchor swings violently between frames.
        return dx1, dy1

    # horizontal: centre of the top 40% of her rows - head and shoulders, which stay put while a
    # tail sweeps or paws lift
    cut = dy0 + max(1, int((dy1 - dy0 + 1) * 0.40))
    head = [p[0] for p in frame.dog if p[1] <= cut]
    hx = sum(head) / len(head) if head else (dx0 + dx1) / 2
    return int(round(hx)), dy1


def clip_extents(seq: list[Frame], align: str) -> tuple[int, int, int, int]:
    """Bounding box of a whole clip's content, in anchor-relative coordinates.

    Particles are included, which is the point: the earlier version measured only the dog, so a
    risen sleep Z or dirt thrown wide of her paws fell outside the canvas and was silently dropped.
    """
    x0 = y0 = 10 ** 9
    x1 = y1 = -10 ** 9
    for f in seq:
        ax, ay = anchor_of(f, align)
        for x, y, _, _ in f.pixels():
            x0 = min(x0, x - ax); x1 = max(x1, x - ax)
            y0 = min(y0, y - ay); y1 = max(y1, y - ay)
    return x0, y0, x1, y1


def clip_offset(extents, canvas) -> tuple[int, int]:
    """Where a clip's anchor sits on the shared canvas: one offset for the whole clip.

    Per-CLIP rather than per-FRAME deliberately. An earlier attempt clamped each frame individually
    to keep it on canvas, which silently overrode the alignment by a different amount on every frame
    - the wag's mirrored frame shifted 0 px while its neighbours shifted 7-8, and that was the
    visible jitter as the tail swapped sides.

    Horizontally the clip is centred; vertically its lowest pixel is put on the canvas floor, so
    every clip shares one ground line and her feet do not jump when the state changes.
    """
    x0, y0, x1, y1 = extents
    cw, ch = canvas
    ox = (cw - (x1 - x0 + 1)) // 2 - x0
    oy = (ch - 1 - PAD) - y1
    return ox, oy


def upscale_clips(placed: dict, canvas) -> tuple[dict, tuple[int, int]]:
    """Enlarge each clip toward the canvas height, capped by MAX_UPSCALE. See that constant.

    Scaling is per CLIP, never per frame - a per-frame factor would make her pulse in size. The
    clip's content is cropped, scaled with NEAREST, then re-seated bottom-aligned and horizontally
    centred, so every clip keeps its shared ground line and her feet do not jump between states.
    """
    cw, ch = canvas
    if MAX_UPSCALE <= 1.0:
        return placed, canvas

    # measure each clip's content and pick its factor
    factors, boxes = {}, {}
    for name, (spec, seq) in placed.items():
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        for img, _ in seq:
            bb = img.getchannel("A").getbbox()
            if not bb:
                continue
            x0, y0 = min(x0, bb[0]), min(y0, bb[1])
            x1, y1 = max(x1, bb[2]), max(y1, bb[3])
        boxes[name] = (x0, y0, x1, y1)
        content_h = y1 - y0
        factors[name] = min(MAX_UPSCALE, ch / content_h) if content_h else 1.0

    # Each clip keeps the SHARED HEIGHT - that is what preserves the common ground line - but gets
    # its own tight WIDTH. The status item is variable-length and DaisyRender derives width from the
    # image's own aspect, so a shared width would only pad every clip out to the widest one.
    out = {}
    max_w = 0
    for name, (spec, seq) in placed.items():
        x0, y0, x1, y1 = boxes[name]
        f = factors[name]
        sw = max(1, int(round((x1 - x0) * f)))
        sh = max(1, min(ch - PAD * 2, int(round((y1 - y0) * f))))
        clip_canvas = (sw, ch)
        max_w = max(max_w, sw)
        frames = []
        for img, mask in seq:
            crop_i = img.crop((x0, y0, x1, y1)).resize((sw, sh), Image.NEAREST)
            crop_m = mask.crop((x0, y0, x1, y1)).resize((sw, sh), Image.NEAREST)
            big_i = Image.new("RGBA", clip_canvas, (0, 0, 0, 0))
            big_m = Image.new("L", clip_canvas, 0)
            oy = ch - PAD - sh                     # bottom-aligned: shared ground line
            big_i.paste(crop_i, (0, oy), crop_i)
            big_m.paste(crop_m, (0, oy))
            frames.append((big_i, big_m))
        out[name] = (spec, frames)
        print(f"  {name:8s} content {x1-x0}x{y1-y0} -> {sw}x{sh} in a {sw}x{ch} frame  (x{f:.3f})")
    return out, (max_w, ch)


def place(frame: Frame, canvas, align: str, offset: tuple[int, int]):
    """Render one frame onto the shared canvas. Returns (RGBA image, particle mask, clipped count)."""
    cw, ch = canvas
    ax, ay = anchor_of(frame, align)
    ox, oy = offset
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    mask = Image.new("L", canvas, 0)
    ip, mp = img.load(), mask.load()
    clipped = 0
    for x, y, rgba, is_particle in frame.pixels():
        tx, ty = x - ax + ox, y - ay + oy
        if 0 <= tx < cw and 0 <= ty < ch:
            ip[tx, ty] = rgba
            if is_particle:
                mp[tx, ty] = 255
        else:
            clipped += 1
    return img, mask, clipped


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

    # Resolve each clip's playback order into concrete frames, mirroring in SOURCE space so
    # alignment is computed on the final shape (see Frame.mirrored).
    resolved: dict[str, tuple[dict, list[Frame]]] = {}
    for name, (spec, frames) in staged.items():
        seq = []
        for idx in spec["order"]:
            f = frames[abs(idx) - 1 if idx < 0 else idx]
            if idx < 0:                       # manufacture a missing pose from a symmetrical view
                f = f.mirrored()
            if spec.get("mirror"):            # whole clip drawn facing the wrong way
                f = f.mirrored()
            seq.append(f)
        resolved[name] = (spec, seq)

    # Canvas is sized by the largest clip measured in ANCHOR-RELATIVE space, particles included.
    # Width is effectively free (the status item is variable-length); height is what costs menu bar
    # space, so it is reported prominently.
    extents = {n: clip_extents(seq, s["align"]) for n, (s, seq) in resolved.items()}
    cw = max(x1 - x0 + 1 for x0, _, x1, _ in extents.values())
    ch = max(y1 - y0 + 1 for _, y0, _, y1 in extents.values())
    canvas = (cw + PAD * 2, ch + PAD * 2)
    print(f"\nshared canvas: {canvas[0]}x{canvas[1]} logical px "
          f"-> {canvas[0]/2:.1f}x{canvas[1]/2:.1f} pt at 1 logical px per device px on 2x")
    tallest = max(extents.items(), key=lambda kv: kv[1][3] - kv[1][1])
    print(f"height driven by '{tallest[0]}' ({tallest[1][3]-tallest[1][1]+1} px)")

    # --- pass 2: place, then build one palette from everything
    placed = {}
    total_clipped = 0
    for name, (spec, seq) in resolved.items():
        off = clip_offset(extents[name], canvas)
        out = []
        for f in seq:
            img, mask, clipped = place(f, canvas, spec["align"], off)
            total_clipped += clipped
            out.append((img, mask))
        placed[name] = (spec, out)
    if total_clipped:
        print(f"WARNING: {total_clipped} pixels clipped off the canvas")

    if MAX_UPSCALE > 1.0:
        print(f"\nper-clip enlargement (cap x{MAX_UPSCALE}):")
        placed, canvas = upscale_clips(placed, canvas)
        print(f"canvas after enlargement: {canvas[0]}x{canvas[1]} "
              f"-> {canvas[0]/2:.1f}x{canvas[1]/2:.1f} pt")

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
