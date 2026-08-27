# Style extraction reference

How to get trustworthy values out of a crop, and how to turn raw measurements into a token system.

## Contents

1. Confidence levels
2. Geometry: radius, borders, spacing
3. Shadows and elevation
4. Typography
5. Fills and gradients
6. Normalizing measurements into tokens
7. States and variants
8. Common misreads

---

## 1. Confidence levels

Tag every value in the final spec:

- **measured** — came out of the sampler. Colors from `colors`, radii and bounding boxes from `geometry`, pixel dimensions from `manifest.json`, contrast ratios from `contrast`. A value counted by eye on an upscaled crop is only `measured` when the shape genuinely contrasts with its background; otherwise it's `inferred`.
- **inferred** — derived from measured values plus a reasonable assumption. "Paddings measured 15/16/17px, so the scale is 4px and this is `space-4`." Font sizes read off an upscaled crop. Shadow blur estimates.
- **guessed** — no evidence in the image. Font family, hover colors, transition timing, breakpoint behavior.

This matters because the person receiving the prompt needs to know which numbers to trust and which to check. An untagged spec forces them to re-verify everything, which defeats the point.

## 2. Geometry: radius, borders, spacing

**Border radius.** Run `geometry` and take its verdict. Do not count the staircase by eye — it only works when the shape contrasts with what's behind it, and light-theme UIs routinely put a `#FAFCFE` card on a `#FFFFFF` page, a 5/255 difference that is invisible at any magnification. Eyeballing it there doesn't produce an imprecise answer, it produces a confident wrong one.

Two traps the subcommand exists to catch:

- **Shadows inflate a corner.** A soft shadow sits between the fill and the page in value, so whichever edge carries it absorbs it and those corners measure far too large. `geometry` reports which pair is contaminated and which to use. Never average the four.
- **Not everything rounded is a rounded rectangle.** Organic blob masks — asymmetric per-corner radii, or an SVG clip path — are common in illustration-led designs, and they read as circles at a glance. Four corners that disagree by more than a few pixels on a shape whose crop looks circular is the signature. A blob shipped as `border-radius: 50%` passes review right up until someone overlays it.

Fully rounded ends (a pill) look like a perfect semicircle whose radius equals half the height; write those as `9999px` / `rounded-full` rather than a measured number, since that's the intent. `geometry` labels them.

If `geometry` says the fill occupies a small fraction of its bounding box, the box holds text or several controls rather than one shape, and no radius from it means anything. Re-box and re-run.

**Borders.** A 1px border at DPR 2 is 2 source pixels and will survive upscaling as a clean band. Distinguish a border from a shadow: borders are uniform on all sides and hard-edged; shadows fall off in value and are usually asymmetric (heavier below). Distinguish a border from a background seam by checking whether the line continues past the component's corner — a seam does, a border doesn't.

**Spacing.** Measure gaps between element edges, not between visual centers. Collect every gap you can, then look at the distribution — real designs cluster hard around a base unit (usually 4px or 8px). Once you know the base unit, snap everything to it. Report both: "measured 14px, snapped to 16px (`space-4`)."

Inner padding is easier to measure on a crop with `--context 0`, since the crop edge is the component edge.

## 3. Shadows and elevation

A screenshot gives you: presence, direction, approximate spread, and approximate darkness. It does not give you exact `rgba()` values, because a shadow is composited against whatever is behind it.

Method: crop with `--context 20` so the shadow region is included, then sample. Compare the page background color just outside the shadow to the darkest point of the shadow. The difference tells you opacity roughly — subtle cards land around 4–8% black, prominent modals 15–25%.

Estimate offset from asymmetry (shadow visible below but not above → positive y-offset) and blur from how many pixels the falloff takes. Then round to a plausible elevation step rather than emitting something like `0 3.7px 11.2px rgba(0,0,0,0.083)`. Real design systems have 3–5 elevation levels; fit the measured shadows onto that ladder and say which level each component uses.

## 4. Typography

**Size.** Measure cap height on an upscaled crop (baseline to top of a capital letter), divide by upscale and DPR, then divide by roughly 0.7 to get font size. Cross-check against x-height ÷ ~0.52. Then snap to a type scale — designs rarely use 15px.

**Weight.** Compare stroke thickness relative to letter height across the crops. You're looking at relative differences within one screenshot, not absolute weights: the thinnest body text is probably 400, headings noticeably thicker are 600–700, anything hairline is 300. Don't claim 500 vs 600 with confidence — that distinction is barely visible in a raster.

**Family.** This is always a **guess**. Useful tells: double-story vs single-story lowercase `a` and `g`; terminal shapes on `t` and `l`; whether `I` has serifs; how geometric the `o` is; presence of visible serifs at all. Common outcomes for UI screenshots are Inter, SF Pro, Roboto, and system stacks — which are similar enough that naming a stack rather than a single font is more honest. Say what tells you observed so the user can correct you cheaply.

**Line height** is measurable where there are two or more lines: baseline-to-baseline distance ÷ font size. Report as a ratio.

**Letter spacing** only shows up as clearly tracked when it's substantial — small caps labels and buttons often are. If letters look normally spaced, say `normal` rather than inventing `-0.01em`.

## 5. Fills and gradients

The `colors` subcommand's corner probes are the primary signal:

- All four corners equal, matching center → flat fill.
- Top pair differs from bottom pair → vertical linear gradient. Report both stops.
- Left pair differs from right pair → horizontal gradient.
- Diagonal pairs differ → diagonal gradient, report the angle as an estimate.
- All four differ but center is a clean color → the component has rounded corners and the probes are catching the page behind it. Re-sample with a tighter box.

Coverage percentages tell you which color is the fill and which is content: a card whose top palette entry is 85% one hex has that as its background.

For glass/blur effects, look for the background showing through with reduced contrast plus a light border — note it as a backdrop-blur effect rather than trying to specify an exact color.

## 6. Normalizing measurements into tokens

Do this before writing the prompt. Raw measurements produce inconsistent code.

**Colors.** Cluster hex values within a small perceptual distance (roughly 8–12 per RGB channel) into one token. Then assign semantic names by role, not by appearance: `--bg-page`, `--bg-surface`, `--bg-surface-raised`, `--text-primary`, `--text-secondary`, `--text-muted`, `--border-subtle`, `--border-strong`, `--accent`, `--accent-hover`, plus semantic states if visible. A typical UI screenshot yields 3–5 neutrals, 1–2 accents, and 0–3 semantic colors. If you're producing 20 color tokens, you haven't clustered enough.

**Spacing.** Find the base unit by looking at the greatest common divisor of your measured gaps, tolerating ±2px of noise. Emit a scale (`2, 4, 8, 12, 16, 24, 32, 48, 64`) and map each measured value onto it.

**Radius.** Usually 2–4 distinct values plus `full`. Name them `sm / md / lg / full`.

**Type.** Emit a scale with size, weight, and line-height per step, named by role (`display`, `h1`, `h2`, `body`, `body-sm`, `caption`, `label`).

Note any measurement that refuses to snap. A value that's genuinely off-scale is often intentional — an optical adjustment, or an icon's fixed size — and flagging it is more useful than silently rounding it.

## 7. States and variants

Screenshots often contain more state information than people notice. Actively hunt for:

- A button that looks different from its siblings → a hover, active, or disabled state.
- A nav item with an underline or different color → the active route.
- A form field with a colored border → focus or validation state.
- A greyed control → disabled.
- Two sizes of the same component → a size variant.

Each of these is worth its own crop and its own line in the spec, because inferring a state ladder from one resting state is the most error-prone part of design-to-code. Where a state isn't visible, say so and offer a convention (for example: hover darkens the fill by one step, focus adds a 2px ring in the accent color at 40% opacity) clearly marked as a suggestion rather than an observation.

## 8. Common misreads

| Trap | What's actually happening |
|---|---|
| Text color looks lighter than it is | Anti-aliasing blends thin strokes toward the background. Sample the densest interior pixels of a thick glyph, or trust the sampler over your eye. |
| A shadow read as a border | Check for value falloff and asymmetry. |
| Spacing off by 2x | The capture is @2x and DPR wasn't divided out. Check `probe` output first — and if it flags the file as an exported artboard, its DPR guess is not evidence, so settle it from a cap height instead. |
| A blob shipped as a circle | Asymmetric organic masks are common in illustration-led designs. `geometry` reporting four corners that disagree on a shape that looks circular is the tell. |
| Radius too large on one edge | A drop shadow, the shape's own or the one cast by the element above it, is being counted as fill. Use the clean pair. |
| Two surfaces treated as one | A card 5/255 off the page behind it is a real, deliberate distinction that no eye can name. Cluster colors, but not so aggressively that neighbouring surfaces merge. |
| Inconsistent paddings everywhere | Anti-aliased edges make boundaries ambiguous by a pixel or two. Cluster before reporting. |
| Every card gets its own component | They're one component with different props. Look for the shared skeleton. |
| Gradient reported as flat | Corners sampled inside a rounded region, catching the page color. Tighten the box. |
| Icons described as images | Most UI icons are from a set (Lucide, Heroicons, Material, SF Symbols). Name a likely set and the specific icon names — far more useful than "a small house shape". |
