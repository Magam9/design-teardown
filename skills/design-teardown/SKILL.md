---
name: design-teardown
description: Turns a UI design screenshot into a build-ready implementation prompt by slicing the image into per-component crops, measuring real colors and geometry from pixels, and writing a spec that pairs each crop with its style tokens. Use this whenever the user supplies a screenshot, mockup, design reference, Figma export, or photo of a UI and wants it broken down into components, reverse-engineered into design tokens, described with styles, converted into a prompt for another AI/agent, or rebuilt in code — even if they only say something vague like "recreate this", "what's in this design", "make a prompt from this screenshot", or "cut this into pieces". Also use for design audits where per-element style extraction matters.
---

# Design Teardown

Turn one flat screenshot into: a folder of per-component crops + a written prompt that another agent (or a human) can build from.

The output is **a prompt**, not code. The user takes that prompt plus the crops somewhere else — Claude Code, v0, a designer, a ticket. Don't start implementing the UI unless asked separately.

## Why slice at all

Reading styles off a full screenshot is unreliable. A 32px-tall button inside a 1440px-wide capture is a handful of pixels once the image is scaled to fit a vision context — border radius, 1px borders, shadow falloff, and letter-spacing all disappear. Cropping that button and upscaling it 3x makes those details legible again.

So the whole method is: **structure from the whole, style from the parts, colors from arithmetic.** Never eyeball a hex code. Sample it.

## Workflow

### 1. Probe the image

```bash
python3 scripts/slice_image.py probe <image>
```

Reports dimensions, aspect, and a guess at the source device class (mobile / tablet / desktop) plus likely DPR. You need real pixel dimensions before you can talk about spacing in a meaningful unit — a 2x capture reports 32px paddings that are really 16px, and getting this wrong doubles every number in the final spec.

If DPR looks like 2x or 3x, note it and divide all measurements by it in the final spec. State the assumption explicitly so the user can correct you.

**The device class is inferred from dimensions alone**, which only means anything for a real viewport capture. Exported artboards and presentation mockups land on round numbers no device produces, and `probe` says so when it sees one. In that case the DPR guess is not evidence — settle it from a measured cap height in step 5 instead (body text below ~10px means the export is @2x) and don't divide anything until you have.

### 2. First pass: map the structure

Look at the full screenshot and write a region map. Work outside-in: page → sections → components → leaf elements. Stop at the level where a thing is reusable. A card is a component; the 4px gap between two lines of text inside it is not.

Give every region a pixel box and a semantic name. Save to `regions.json`:

```json
{
  "image": "screenshot.png",
  "dpr": 2,
  "regions": [
    {"id": "nav",         "name": "top-navbar",       "box": [0, 0, 1440, 72],    "kind": "section"},
    {"id": "nav-cta",     "name": "primary-button",    "box": [1256, 20, 1400, 52], "kind": "component", "upscale": 4},
    {"id": "hero",        "name": "hero-section",      "box": [0, 72, 1440, 640],   "kind": "section"},
    {"id": "card-1",      "name": "feature-card",      "box": [120, 700, 520, 980], "kind": "component", "upscale": 2}
  ]
}
```

`box` is `[x0, y0, x1, y1]` in source pixels. Normalized 0–1 floats also work if you'd rather estimate proportionally. `upscale` defaults to a value the script picks from region size — override it for anything fiddly.

Two rules that keep the map useful:

- **Crop repeated elements once, plus their variants.** Six identical feature cards need one crop, not six. But if one card is in a hover/selected state, crop that too and name it as a variant — state differences are the most valuable thing a screenshot can tell you and the easiest to lose.
- **Isolate every leaf element whose styling carries information**: buttons (each variant), inputs (each state visible), badges, avatars, icons, form labels, table headers. These are the crops that make the final prompt precise.

### 3. Cut the crops

```bash
python3 scripts/slice_image.py crop regions.json --outdir crops/
```

Writes `crops/<id>__<name>.png` with padding and upscaling applied, plus `crops/manifest.json` recording the exact source box, output size, and scale factor for each. Add `--context 12` to include a ring of surrounding pixels — helpful for judging how a component sits against its background, which matters for shadows and for telling a border apart from a background seam.

### 4. Measure the geometry

```bash
python3 scripts/slice_image.py geometry regions.json
```

For each region: the fill's exact bounding box, its size, and all four corner radii, computed from the area each rounded corner cuts away. Use this instead of counting the staircase by eye. Counting works only when the shape contrasts with what's behind it, and in a light theme it usually doesn't — a `#FAFCFE` card on a `#FFFFFF` page is invisible at any magnification, and that describes most components on most light-mode screenshots.

Read the verdict line, not just the four numbers:

- **`uniform radius ~Npx`** — take it. That's a `measured` value.
- **`circle` / `fully rounded ends`** — write `50%` or `rounded-full`, not the number.
- **`one edge reads larger — a soft shadow is being counted as fill`** — a shadow sits between the fill and the page in value, so that edge absorbs it. Use the pair the tool points at; the other is contaminated.
- **`fill occupies only N%`** — the box holds text, a row of controls, or two components. The radii are meaningless. Re-box a single shape and run it again.
- **`corners disagree`** with no shadow diagnosis — look at the crop before writing anything. Organic and blob shapes are real and more common than you'd expect; a blob reported as `border-radius: 50%` is a wrong build that reviews as "close enough" until someone puts it side by side.

Boxes are grown by 6px automatically, because a shape can't be separated from a background that isn't in frame. Override per region with `"context"`, or globally with `--context`.

### 5. Measure the colors

```bash
python3 scripts/slice_image.py colors regions.json --top 6
```

For each region: dominant hex values with coverage percentages, plus corner and center probes. Corner probes are how you separate a component's own background from the page behind it, and how you detect a gradient (corners differ) from a flat fill (corners match).

Then check contrast on anything with text:

```bash
python3 scripts/slice_image.py contrast "#1F2937" "#FFFFFF"
```

Read `references/style-extraction.md` before interpreting any of this. It covers reading radius and shadow from an upscaled crop, inferring the spacing scale, guessing font stacks from letterforms, and — importantly — how to normalize measured values onto a sane token scale instead of emitting `padding: 13px`.

### 6. Second pass: read each crop

This pass answers only what pixels can't be counted: what the thing *is*, what it contains, which crops are variants of one component, what states are visible, and what props it should expose. Colour, radius and dimensions are already measured — do not re-derive them by eye here.

Reconcile against the measurement output rather than trusting your eye. When your visual read and the sampled colour disagree, the sampler is right — anti-aliasing and compression shift perceived colour, especially on thin text and 1px borders.

**If you can spawn subagents, delegate this pass — and only this pass.** Send each subagent a group of related crops and have it return a structured semantic description. Read `references/parallel-reads.md` for the brief before doing it. Two rules that make it safe:

- **Group by component family, never one agent per crop.** All the card variants go to one agent, all the task rows to another. Variant and state detection is comparative — an agent that sees one crop in isolation cannot tell you it's the hover state of something else.
- **Never send measurements to a subagent, and forbid it from reporting any.** Colours and geometry stay in the main context, where the whole set is visible at once. This is not only about trust: clustering fourteen near-identical greys into four tokens in step 7 requires seeing all fourteen together, and a fan-out that scatters them makes it impossible.

Delegation buys accuracy, not context. The crop set for a full screen is only ~12k image tokens; what it actually prevents is a model inventing a hex code it was never in a position to read.

Skip the fan-out for anything under roughly a dozen crops, and on hosts without subagents — the sequential read below is the fallback and produces the same output, more slowly.

Sequentially: view the crops one at a time, in region-map order, writing each component's semantic notes as you go.

### 7. Build the token system

Cluster the measured values before writing the prompt. Fourteen near-identical grays become 4 semantic tokens; measured paddings of 11/12/13px become one `space-3`. A prompt built on tokens produces consistent code; a prompt built on 40 raw hex values produces a mess. `references/style-extraction.md` has the clustering thresholds.

### 8. Write the prompt

Follow `references/prompt-template.md` exactly.

**Split the output across files.** A whole screen written as one document runs 300+ lines, and the builder pays for every one of them before writing any code:

```
IMPLEMENTATION_PROMPT.md     entry point — assumptions, layout, open questions, build order
spec/tokens.md               color, spacing, radius, type, elevation, contrast
spec/components.md           per-component specs
```

One component or a small fragment stays a single file. A multi-screen flow gets one `spec/<screen>.md` per screen alongside a shared `spec/tokens.md`.

Two rules make the split work: the entry file must stand alone as a prompt — pasting only that file still has to start a correct build, so it names the other files and says when to read them — and every token is defined in `spec/tokens.md` and nowhere else, referenced by name everywhere else. Paths inside `spec/` are relative to it, so crops are `../crops/<file>.png`; check they resolve before handing the folder over.

Save next to `crops/`, then present the whole folder to the user.

Ask about the target stack before writing if it isn't already clear from the conversation — the template's code-shape section depends on it. If the user doesn't care or isn't around to ask, default to React + TypeScript + Tailwind and say so in the prompt's assumptions block.

## Confidence, and saying what you can't see

A screenshot is a single frame. It cannot tell you hover states, focus rings, transitions, breakpoint behavior, scroll behavior, empty/loading/error states, real content length, or z-index relationships in a collapsed stack. Font identification from rendered text is a guess, not a match.

Mark every inference with a confidence level — `measured` / `inferred` / `guessed` — and collect the genuinely unknowable things in the prompt's open-questions section. A prompt that quietly invents a hover color sends the next agent off building fiction, and the user won't know which parts to check. One that says "hover state not visible in source; suggest darkening the fill one step" is honest and still actionable.

## Handling awkward inputs

**Very long pages** (a 6000px scroll capture): crop by section first, then treat each section as its own slicing job. One prompt per section, or one master prompt with section files — ask which.

**Photos of screens / low-res / compressed**: say so up front. Sampled colors will be off by several values from moiré and JPEG artifacts, so round aggressively toward plausible palette values and mark colors `guessed`. Don't produce a false-precision spec from a bad source.

**Dark mode**: check whether it's genuinely dark-themed or an inverted light theme — inverted themes have telltale pure-black backgrounds and unadjusted saturation. Note which, since it changes how the token system should be built.

**Multiple screens in one image**: slice into per-screen regions in step 2 and confirm with the user whether they want one prompt covering all screens plus shared components, or separate prompts.

## Scripts

`scripts/slice_image.py` — one entry point, five subcommands:

| Command | Purpose |
|---|---|
| `probe <image>` | Dimensions, aspect, device class, DPR guess |
| `crop <regions.json>` | Per-region crops with padding + upscaling, writes manifest |
| `geometry <regions.json>` | Fill bounding box and four corner radii per region |
| `colors <regions.json>` | Dominant palette per region with coverage, corner/center probes |
| `contrast <fg> <bg>` | WCAG contrast ratio and pass/fail levels |

Requires Pillow. If it's missing: `pip install pillow --break-system-packages`. Run `python3 scripts/slice_image.py --help` for full flags.

## References

- `references/style-extraction.md` — measuring radius, shadows, spacing, type; normalizing to tokens; confidence rules. Read before step 5.
- `references/parallel-reads.md` — how to fan the crop read out across subagents without losing variant detection or token clustering. Read before delegating step 6; skip it if you're reading the crops yourself.
- `references/prompt-template.md` — the required output format, and how to split it across files. Read before step 8.
