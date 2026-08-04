# Daisy Status Bar — image generation prompts (pixel art)

Prompts for Grok Imagine / Google Gemini. **Target style: 16-bit pixel art, Stardew Valley / SNES
era**, ~32-43 px per frame so it lands in the menu bar at native resolution with no downsampling.

Working method: Claude pastes a fully-assembled prompt into chat one animation at a time, you
generate, Claude measures the result. This file holds the per-animation scene text plus the three
standard blocks that get appended to all of them.

---

## THE RECIPE (validated — do not deviate)

**Always: 4 frames, arranged as a 2x2 grid.** Six frames in one strip forces a ~6:1 image and the
model shrinks her. 4 frames with big deltas read better at 36px than 6 mushy ones.

**Always: describe every frame explicitly and separately.** The first trot attempt described the
cycle as a *concept* ("legs move through a full diagonal trot") and produced 6 frames with only 3
distinct poses — two of them measured **2.0% different**. Naming each frame's pose fixed it
completely (30–56% differences).

**Then pick one of two motion framings:**

| | HIGH-MOTION (run, zoomies, dig, wag, yawn) | SUBTLE IDLE (sleep, blink, belly-up) |
|---|---|---|
| say | "dramatically and obviously different, exaggerate heavily, do not repeat a pose" | "nearly identical, change ONLY the pixels described, leave every other pixel identical" |
| target diff | adjacent pairs >12%, none <8% | adjacent pairs ~2–8% |
| failure | duplicate poses | a thrashing, restless dog |

**Always: attach the approved character sheet, and stay in the same chat thread.** A fresh thread
gives you a different dog.

**Always: name the scale.** "the same pixel scale as the reference — do not shrink her."

**Always: pin the ears.** Include this verbatim in every prompt. Saying "ears perked up" produced
erect pointed cat/shepherd ears and cost a regeneration:

> Her ears are floppy, soft, rounded drop ears that hang down against the sides of her head, exactly
> like the reference. Her ears must NEVER be pointed, erect, triangular or sticking up — she is a
> Bernese Mountain Dog, not a cat or a shepherd. Keep the same floppy rounded ears in all four frames.

**Give abstract motion a concrete drawable proxy.** "Tilt her head" was ignored twice — head rotation
is too abstract. "The white blaze stripe must run at a strong DIAGONAL instead of straight up and
down" worked first try, because a line's angle is drawable *and* measurable. Look for the equivalent
trick for any rotation or expression: name a specific marking, edge or line and say what angle or
position it takes.

**Never put a white marking in front of another white marking.** The raised paw was held over the
white chest bib and became invisible. Moving it out to the side, silhouetted against the background,
fixed it. General rule for small sprites: motion must happen against contrast.

**Sub-3-pixel changes do not render.** The model has no middle gear — it either duplicates a frame
almost exactly (measured 0.5–0.8%) or makes a big obvious change. A 2px "chest rises as she breathes"
produced literally nothing. If motion needs to be small, either add a discrete object that moves (the
sleep Z) or hand it to code.

## What to reject

- **Blurry / anti-aliased / soft pixel edges**, or a misaligned pixel grid.
- **Duplicate or near-duplicate poses** in a high-motion set.
- **A transparency checkerboard painted into the image.** Happened twice on the character sheets and
  looks completely convincing. This is why every prompt now demands flat magenta instead.
- **Frames that touch or overlap** — makes splitting fragile.
- **A shrunken dog** — the commonest failure when frame count goes up.
- Ground shadows, drop shadows, cell borders, grid lines, text, frame numbers, watermarks.

---

## THE THREE STANDARD BLOCKS

Append all three, verbatim, to every scene below.

**LAYOUT BLOCK**
> Layout: arrange the 4 frames as a grid, 2 columns across and 2 rows down. Reading order is left to
> right along the top row (frames 1, 2), then left to right along the bottom row (frames 3, 4). Every
> frame uses an identical cell size, and she sits at the exact same pixel scale and the same position
> within every cell. Leave a clear, generous empty gap of background between all frames — the dogs
> must never touch or overlap each other. The camera does not move, rotate, zoom, or change angle
> between frames.

**RENDERING BLOCK**
> Rendering: true pixel art on a strict integer pixel grid. Every pixel is a crisp, hard-edged square
> block of exactly the same size, perfectly aligned to the grid. Absolutely no anti-aliasing, no
> blur, no soft edges, no gradients, no glows, no smooth shading, no dithering, no stipple texture.
> Flat blocks of solid colour only.

**BACKGROUND BLOCK**
> Background: a completely flat, solid, uniform pure magenta `#FF00FF` (RGB 255, 0, 255) filling every
> part of the image she does not occupy. Do NOT draw a transparency checkerboard pattern. Do NOT use
> gray, white, or any gradient. The magenta must be one single flat colour with no shading, noise, or
> variation. No ground shadow, no drop shadow, no cell borders, no grid lines, no text, no frame
> numbers, no watermark.

**IDENTITY BLOCK** (opens every prompt)
> Match the attached character reference exactly — the same cute 16-bit pixel art Bernese Mountain Dog
> in Stardew Valley / SNES sprite style, the same markings (black body, bold white muzzle blaze, bold
> white chest bib, white paws, white tail tip, rust/tan eyebrow patches and cheeks, rust/tan legs), the
> same colour palette, and the same pixel scale as the reference. Do not shrink her.

---

## Status

Image cache lives at `~/.claude/image-cache/bc4df9dc-7745-4dd9-bd89-6a3cff39b173/`.

**ART COMPLETE as of 2026-08-04: 8 animations approved, 1 cut.**

| # | Animation | App state | Status | Source | Native | Diffs |
|---|---|---|---|---|---|---|
| 0 | Character sheet | — | **APPROVED** | `2.png` | ~32x38/dog | 100x100 grid |
| 3 | Trotting | thinking / working | **APPROVED** | `4.png` | 43x32 | 30–56% |
| 6 | Zoomies | Running command | **APPROVED** | `11.png` | 46x39 | 27–36%, 25.5% vs trot |
| 4 | Digging | Editing / Writing | **APPROVED** | `12.png` | 48x40 | 28–46% |
| 5 | Sniffing | Reading / Searching | **APPROVED** | `13.png` | 46x38 | 19–27%, 32.7% vs trot |
| 7 | Head tilt, paw up | awaiting permission | **APPROVED** | `10.png` | 42x44 | 12–40% |
| 8 | Tail wag | turn complete | **APPROVED** | `14.png` | 48x46 | 49–54% (repaired) |
| 1 | Sleeping + ZZZ | idle > 2 min | **APPROVED** | `6.png` | 43x38 | 5–13% |
| 2 | Blink, sphinx | idle < 2 min | **APPROVED** | `8.png` | 47x35 | blink 5%, f4 22% |
| 9 | Stretch and yawn | idle fidget | **APPROVED** | `15.png` | 46x45 | 21–59% |
| 10 | Belly-up roll | rare easter egg | **CUT** | `16.png` | 48x29 | pose illegible at 36px |

**Why belly-up was cut:** the animation measured correctly (6% for the identical settled frames, 18–23%
for the wiggles) but the *pose* doesn't read as a dog at 36px. Upside down, her stubby legs read as
bumps and her tipped-back head merges into her body; the template is a black mass with specks. Idle
variance is already covered twice (stretch-and-yawn + the blink set's f4 ear-perk), and it was the
1-in-40 easter egg. If an easter egg is wanted later, a **play-bow** or **tail-chase spin** would keep a
legible upright silhouette.

### MIRRORING — free poses and free fixes

She is symmetrical enough that horizontal mirroring is invisible, and it solved two different problems:

- **Front views: manufactures a missing pose.** The wag's f3 came back with TWO TAILS. Discarded it and
  substituted `mirror(f1)` to get the tail-sweeps-right frame. Adjacent diffs went to 49–54% and the arc
  is now perfectly symmetrical — better than what was asked for.
- **Side views: corrects facing direction.** The stretch-and-yawn came back facing LEFT while every other
  side view faces right. Mirrored all 4 frames. Verified against the trot — they now match.

Do NOT mirror a side view expecting a new pose (it just turns her around), and do NOT rely on mirroring
to fix a front view's direction (there isn't one).

### Per-animation post-processing notes

- **Sleeping (`6.png`)** — the Z is a separate blob from the dog; align on the dog and carry the Z.
  Grok's Z jumps horizontally (right→left→centre→right); **reposition it in code** onto a clean
  diagonal rise. In System mode the curled pose is nearly a solid blob (bib hidden underneath) — the
  Z is what makes it read as sleeping. Luminance histogram has a wide empty gap from 49 to 178, so
  no cut value can add internal detail; `cut=150` sits safely mid-plateau.
- **Blink (`8.png`)** — f2 is a duplicate of f1 (half-lid didn't render), so the blink is 2-state:
  play `f1 → f3 → f1`. **f4 (both ears perked, head lifted) is 22% different — do NOT play it every
  cycle** or she strobes. Use it as an occasional idle "alert" beat; it's a free second idle fidget
  alongside the stretch-and-yawn.
- **Head tilt (`10.png`)** — one stray magenta speck in f1 near her shoulder; speck filter handles it.
- **Zoomies (`11.png`)** — the pale blue speed puffs arrive as separate small blobs (`extras [16,16,8]`
  and `[16,8,8]`). Being light, the template punches them out as holes, and an isolated hole in nothing
  is INVISIBLE — they vanish in System mode. **Render puff blobs as INK in template mode**, opposite to
  the dog's treatment. Also f3 is not the FULL TUCK that was asked for — all four frames are extended
  sprint poses, so there's no compression phase. Accepted: at 36px and high fps it reads as frantic
  sprinting, which is what zoomies are.
- **Digging (`12.png`)** — dark brown dirt was requested specifically so it survives as ink, and it does.
  But dirt count goes 0 → 4 → 3 → lots instead of building and settling, so f1's total absence of dirt
  flickers. **Play f1 once as a wind-up when digging starts, then loop f2–f4.** Nicer than the original
  spec — adds an anticipation beat. Stray pink speck in f3.
- **Sniffing (`13.png`)** — template is blobby: head down hides the muzzle blaze and compresses the bib,
  so System mode is a mostly-black mass. The flagged-up tail rescues it. Optional polish (not needed):
  a couple of dark sniff puffs at her nose would sharpen both motion and silhouette.
- **Tail wag (`14.png`)** — **f3 has two tails; DISCARD it.** Use `f1, f2, mirror(f1), f4`.
- **Stretch and yawn (`15.png`)** — **faces LEFT as generated; mirror all 4 frames.** One-shot, not a
  loop. f1 and f4 are both resting (21.5% apart) which is correct — it must hand back cleanly to the
  sleeping/drowsy idles.

### Particle rule (learned twice)

Light-coloured particles VANISH in System mode: the template punches bright pixels out as holes, and a
hole with no surrounding ink is invisible. This killed the zoomies puffs and would have killed a white
sleep Z. Two remedies, both in use:
1. **Ask for dark particles** (the brown dirt) — they become ink naturally.
2. **Special-case them in code** — particles arrive as separate small blobs, so identify them and render
   as ink rather than punching them out.
- **Height normalisation (OPEN ISSUE)** — sitting poses are 38–41px tall vs 32 for the trot. All
  animations must share one scale or non-integer downscaling will blur the pixel art. Plan: pick one
  canonical sprite height covering the tallest pose and map it to a slightly taller point size so the
  mapping stays integer at 2x. The sitting pose is the height driver.
- **Backgrounds are never true `#FF00FF`** — observed `(201,64,170)`, `(241,43,218)`, `(203,46,163)`,
  `(241,12,217)`. Always flat and always unambiguous against her palette, so the widened key
  (`r>120 and b>110 and g<120 and (r+b)/2-g>60`) handles all of them. Don't tighten it.

---

## Prompt 3 — Trotting (APPROVED, kept for reference)

High-motion framing. This is the wording that worked.

> A 4-frame running cycle, side view facing right. **The four poses must be dramatically and
> obviously different from one another — this is a tiny sprite, so exaggerate the leg and body
> positions heavily. Subtle differences are invisible. Do not repeat the same pose twice.** Draw each
> frame exactly as described:
>
> **Frame 1 — FULL STRETCH.** Her body is stretched out long and low, fully airborne with no paws
> touching the ground. Both front legs reach far forward ahead of her chest, nearly straight. Both back
> legs stretch far backward behind her rump, nearly straight. The distance between her front paws and
> back paws is at its absolute widest. Her tail streams straight out behind her.
>
> **Frame 2 — LANDING SQUASH.** Her front paws are planted on the ground directly beneath her chest,
> front legs bent and compressed. Her back legs swing forward underneath her belly, bunched close
> behind her front legs. Her body is visibly compressed shorter and sits at its lowest point of the
> whole cycle. Her tail curves upward.
>
> **Frame 3 — GATHERED HOP.** All four legs are bunched tightly together underneath the centre of her
> body, knees bent, paws close to each other. Her back is arched upward like a cat stretching. Her body
> is at its shortest and highest point of the cycle. Her tail flicks up high above her back.
>
> **Frame 4 — PUSH OFF.** Her back legs are planted on the ground behind her and extending backward as
> she pushes off. Her front legs lift up and fold in toward her chest, paws well clear of the ground.
> Her body begins stretching long again and tilts slightly nose-up. Her tail streams out behind her.
>
> Frame 4 must lead cleanly back into frame 1 so the loop is seamless.

---

## Prompt 1 — Sleeping (idle, deep) — SUBTLE

> A 4-frame sleeping idle loop, side view facing right. She is curled up asleep in a tight compact
> ball, nose tucked in toward her tail, eyes closed as simple soft curved dark lines, ears relaxed and
> flopped down over her cheeks, tail wrapped around her body.
>
> **This is a very subtle idle animation, not an action. The four frames must be nearly identical to
> each other. Her position, size, curl, orientation, and outline must stay exactly the same in all four
> frames — she does not move, shift, rotate, or resize. Change ONLY the specific few pixels described
> for each frame, and leave every other pixel identical.**
>
> **Frame 1 — RESTING.** She lies completely still, fully at rest.
>
> **Frame 2 — INHALE.** Exactly the same as frame 1, except the curve of her back and side rises by
> about two pixels, as though her chest is expanding with a slow breath. Nothing else changes.
>
> **Frame 3 — RESTING.** Pixel-for-pixel identical to frame 1.
>
> **Frame 4 — TWITCH.** Exactly the same as frame 1, except one ear flicks up by about two pixels and
> the white tip of her tail lifts by one pixel. Nothing else changes.

---

## Prompt 2 — Blink, lying down (idle, drowsy) — SUBTLE

> A 4-frame blinking idle loop, side view facing right. She lies in a relaxed sphinx pose — belly on
> the ground, front paws stretched out ahead of her, head up and awake but sleepy, ears up but soft,
> tail resting along the ground behind her.
>
> **This is a very subtle idle animation, not an action. The four frames must be nearly identical. Her
> body, legs, tail, head position, size and outline must stay exactly the same in all four frames —
> only her eyes and one ear change. Change ONLY the pixels described, and leave every other pixel
> identical.**
>
> **Frame 1 — EYES OPEN.** Both eyes fully open and bright, ears up.
>
> **Frame 2 — HALF CLOSED.** Identical to frame 1 except her eyes are half closed — the lower half of
> each eye still visible.
>
> **Frame 3 — EYES SHUT.** Identical to frame 1 except her eyes are fully closed, drawn as simple thin
> dark horizontal lines.
>
> **Frame 4 — REOPENING.** Identical to frame 1 except her eyes are half open again and one ear tips
> slightly sideways.

---

## Prompt 7 — Head tilt, paw up (awaiting permission) — MODERATE

> A 4-frame "may I?" loop, three-quarter view with her sitting and facing slightly toward the viewer.
> She sits politely on her haunches, ears perked fully up, eyes wide and hopeful.
>
> **Her sitting body, haunches, and tail stay in exactly the same position and at the same size in all
> four frames. Only her head angle, one front paw, and her eyes change — but make those changes clear
> and obvious, not subtle.**
>
> **Frame 1 — SQUARE.** Sitting upright, head perfectly level, both front paws flat on the ground in
> front of her, ears straight up.
>
> **Frame 2 — TILT BEGINS.** Same body. Her head tilts clearly to one side, and the front paw nearest
> the viewer lifts a few pixels off the ground.
>
> **Frame 3 — FULL ASK.** Same body. Her head is tilted right over at a strong, obvious angle, and
> that front paw is raised high up near her chest, held in the air. Her eyes are at their widest and
> most pleading.
>
> **Frame 4 — BLINK.** Identical to frame 3 — same strong head tilt, same raised paw — except her eyes
> are closed in a single blink.

---

## Prompt 4 — Digging (editing / writing files) — HIGH MOTION

> A 4-frame digging loop, side view facing right. Her rear end is up high and her front half is low to
> the ground, front paws scrabbling at the dirt. Her tail sticks straight up. Her expression is
> focused and delighted. Dirt is drawn as chunky solid square pixel blocks, not soft specks.
>
> **The four poses must be dramatically and obviously different from one another — exaggerate the paw
> and body positions heavily. Do not repeat the same pose twice.**
>
> **Frame 1 — PAWS HIGH.** Rear end high, chest low, both front paws lifted right up near her chin,
> ready to strike. No dirt in the air yet.
>
> **Frame 2 — STRIKE DOWN.** Both front paws slammed down into the ground directly beneath her chest,
> her head ducked low between them. Three or four chunky dirt blocks are just starting to fly backward
> past her belly.
>
> **Frame 3 — SCRAPE BACK.** Her front paws are dragged back underneath her belly, body shoved
> slightly backward by the effort. The most dirt of the whole cycle is in the air — six or seven chunky
> blocks scattered behind her in an arc.
>
> **Frame 4 — LIFT.** Her front paws are lifting back up toward her chin again, rear still high, with
> only two dirt blocks left tumbling down behind her.
>
> Frame 4 must lead cleanly back into frame 1 so the loop is seamless.

---

## Prompt 5 — Sniffing / tracking (reading / searching) — MODERATE

> A 4-frame scent-tracking loop, side view facing right. Her nose is pressed right down to the ground
> the entire time, sniffing along a trail. Her tail is held straight up like a flag. Her ears hang
> forward past her cheeks.
>
> **Her nose stays touching the ground in all four frames, but the four poses must be clearly and
> obviously different — exaggerate the head sweep and the leg positions. Do not repeat a pose.**
>
> **Frame 1 — NOSE FORWARD.** Head stretched far forward, nose to the ground well ahead of her front
> paws, front legs braced and straight, hind legs trailing back.
>
> **Frame 2 — HEAD DRAWN BACK.** Nose still on the ground but tucked back close underneath her chest,
> her neck compressed, front legs gathered under her, hind legs stepping forward. Her tail leans to one
> side.
>
> **Frame 3 — MID STEP.** Nose on the ground at a middle position, one front paw clearly lifted in the
> air mid-step, body stretched a little longer, tail straight up.
>
> **Frame 4 — SWEEP.** Nose on the ground, head clearly turned and sweeping to the far side of the
> trail, hind legs pushing forward, tail leaning to the other side.
>
> Frame 4 must lead cleanly back into frame 1 so the loop is seamless.

---

## Prompt 6 — Zoomies (running a command) — MAXIMUM MOTION

> A 4-frame flat-out sprint cycle, side view facing right — maximum-speed puppy zoomies. Throughout,
> her ears are pinned flat back against her head, her tongue hangs out to one side, and her eyes are
> wide with joyful mania. Speed puffs are drawn as chunky solid square pixel blocks.
>
> **This is the fastest, most extreme animation in the set. The four poses must be dramatically and
> obviously different — exaggerate the stretch, the tuck and the leg extension far beyond realistic.
> Do not repeat a pose.**
>
> **Frame 1 — MAXIMUM EXTENSION.** Fully airborne, body stretched to its absolute longest and
> flattest. All four legs reach out straight — front legs far ahead, hind legs far behind. Tail
> streaming straight out. This is the longest, lowest frame of the cycle.
>
> **Frame 2 — FRONT LANDING.** Front paws slam down hard, front legs bent and absorbing the impact,
> body compressed low and short. Hind legs still trailing far out behind her. Two or three speed puff
> blocks burst at her front paws.
>
> **Frame 3 — FULL TUCK.** Fully airborne again with all four legs bunched tight underneath her belly,
> back arched high like a cat. Body at its shortest and tallest of the cycle. Tail streaming.
>
> **Frame 4 — HIND PUSH.** Hind legs planted behind her and extending hard backward as she launches,
> front legs folded up to her chest, body tilted clearly nose-up. Three or four speed puff blocks burst
> behind her hind paws.
>
> Frame 4 must lead cleanly back into frame 1 so the loop is seamless.

---

## Prompt 8 — Tail wag, happy bounce (turn complete) — HIGH MOTION

> A 4-frame celebration loop, three-quarter view facing slightly toward the viewer. She is thrilled:
> sitting up proud with her chest out, mouth open in a big happy smile with her tongue showing, eyes
> bright and squinty with joy, ears perked up.
>
> **The tail positions must be dramatically and obviously different from one another — swing it through
> a wide, exaggerated arc. Do not repeat a pose.**
>
> **Frame 1 — TAIL LEFT, BODY DOWN.** Her plumed tail is swept all the way over to one side, low
> behind her. Her body is settled down at its lowest.
>
> **Frame 2 — TAIL UP, BODY UP.** Her tail is swung up to point straight up above her back, and her
> whole body has bounced up two or three pixels off her haunches.
>
> **Frame 3 — TAIL RIGHT, BODY DOWN.** Her tail is swept all the way over to the opposite side, low
> behind her. Her body is settled back down at its lowest.
>
> **Frame 4 — TAIL UP, MOUTH WIDE.** Her tail is straight up again and her body bounced up, but this
> time her mouth is open even wider in an excited bark and her tongue is further out.
>
> Frame 4 must lead cleanly back into frame 1 so the loop is seamless.

---

## Prompt 9 — Stretch and yawn (idle fidget) — HIGH MOTION, ONE-SHOT

> A 4-frame stretch-and-yawn sequence, side view facing right. **This is a one-shot sequence that
> plays once, NOT a repeating loop — frame 4 does not need to lead back into frame 1.**
>
> **The four poses must be dramatically and obviously different from one another — exaggerate heavily.
> Do not repeat a pose.**
>
> **Frame 1 — LYING RELAXED.** Lying down comfortably, belly on the ground, head up, eyes half closed
> and sleepy, paws tucked in close.
>
> **Frame 2 — BIG STRETCH.** A huge exaggerated downward-dog stretch: both front legs shoved far
> forward with her chest pressed flat to the ground, toes splayed wide, and her rear end hoisted up
> high in the air with her tail straight up. Body stretched to its longest.
>
> **Frame 3 — ENORMOUS YAWN.** Holding the same big stretch, but her mouth is now open in a huge yawn
> that takes up most of her head, eyes squeezed tightly shut, tongue curled up.
>
> **Frame 4 — SETTLED.** Flopped back down lying relaxed and contented, eyes half closed, tail curled
> around beside her, body compact again.

---

## Prompt 10 — Belly-up roll (rare easter egg) — SUBTLE

> A 4-frame belly-up wiggle loop, side view. She lies flat on her back with her bold white chest and
> belly fully exposed, all four paws folded up in the air above her, head tipped back, tongue lolling
> out to one side, eyes squeezed shut in blissful contentment.
>
> **She stays on her back in the same spot at the same size in all four frames — she does not roll
> over, get up, or change position. Only her paws, head and tongue shift slightly. Change ONLY the
> pixels described.**
>
> **Frame 1 — SETTLED.** Lying still on her back, paws up, head tipped back, tongue out to one side.
>
> **Frame 2 — WIGGLE ONE WAY.** Identical to frame 1 except all four raised paws lean a couple of
> pixels to one side and her head rocks slightly that way.
>
> **Frame 3 — SETTLED.** Pixel-for-pixel identical to frame 1.
>
> **Frame 4 — WIGGLE THE OTHER WAY.** Identical to frame 1 except her paws lean a couple of pixels to
> the opposite side, her head rocks that way, and her tongue flops to the other side of her mouth.

---

## Pipeline (verified against the approved trot)

- **Grid recovery** — both delivered images were a 100x100 logical canvas upscaled to ~1024. Detect
  the block size from the edge-gap histogram, then sample **block centres**; never resample.
- **Magenta key** — `r>130 and b>130 and g<110`. A tighter threshold left a stray speck.
- **Frame split** — 8-connected blobs, minimum ~120 logical px, ordered by (row, column).
- **Alignment** — **nose-align** (rightmost + topmost pixel) for locomotion; **centroid-align** for
  idle poses. Bottom-align rejected: frame heights vary and she pogos.
- **Quantize to ~16 colours, not 8** — the art uses load-bearing anti-aliasing tones.
- **System-mode template** — ink where opaque, pixels brighter than **luminance 150** punched through
  as holes, so blaze, bib, paws and tail tip read as negative space.
- Emit base64 arrays into `Sources/DaisyFrames.swift`.

Scratchpad scripts: `analyze.py`, `grid.py`, `gridof.py`, `native.py`, `test2.py`, `sil.py`,
`frames.py` (pairwise difference matrix), `anim.py`, `align.py`.
