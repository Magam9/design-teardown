# design-teardown

Turn a UI screenshot into per-component crops and a measured implementation prompt.
Colors and geometry are sampled from pixels, not guessed.

A [Claude skill](https://code.claude.com/docs/en/skills). The output is a prompt plus a
folder of reference images — hand both to a coding agent, or to a person.

> Status: early. There's one worked example in [`examples/`](examples/); the numbers in
> [Benchmarks](#benchmarks) are not filled in yet. Personal tool published in case it's
> useful. Issues welcome; responses not guaranteed.

## The problem it solves

Ask a model to read styles off a screenshot and it will answer confidently about things it
cannot see. The failure isn't vagueness — it's false precision. You get a hex code that's
three values off because anti-aliasing shifted it, a hover state that was never in the
image, and `border-radius: 50%` on a shape that isn't a circle.

None of those are visible as mistakes in the output. They surface later, as a rebuild that
looks *almost* right.

So this skill splits the work. Anything countable goes to a Python script that measures it.
Judgement — what's a button, what's a card, which crops matter — stays with the model. And
every value in the final prompt is tagged with where it came from:

| Tag | Meaning |
|---|---|
| `measured` | came out of the pixel sampler |
| `inferred` | derived from measured values plus an assumption (spacing scale, type scale) |
| `guessed` | no evidence in the image — font family, hover colors, transitions |

The tags are the product. A spec that quietly invents a hover color sends the next agent off
building fiction, and the recipient has no way to know which parts to check.

## What that catches

From the [worked example](examples/taskly-dashboard/) — a real dashboard design
([FREE Freelancer Schedule Web](https://dribbble.com/shots/10858979-FREE-Freelancer-Schedule-Web)
by [Lorez](https://dribbble.com/Lorez)), torn down and committed exactly as the skill
produced it:

![blob versus circle](examples/blob-vs-circle.png)

Left is what `border-radius: 50%` produces. Right is the button that's actually in the
screenshot, at 6x. Its measured corner radii are 42 / 26 / 26 / 30 on a 64 x 67 box, where a
circle reads 32 / 32 / 32 / 32 — an asymmetric blob mask, reused for the brand mark and the
avatar. Three wrong shapes, from one reasonable-looking assumption.

Also from that run, none of it visible by eye:

- **The surface roles invert between columns.** The sidebar is tinted and its cards are
  white; the main column is white and its cards are tinted. The two surfaces are 5/255
  apart — obvious side by side in the render, impossible to name from memory.
- **The player's progress bar has no track.** Every pixel past the playhead measures the
  card color exactly. A rebuild that adds the usual grey track is inventing it.
- **Everything accent-colored fails WCAG AA** — 1.41:1 on the button glyph. Measured and
  reported, not silently corrected, because a build that quietly darkens the palette won't
  match the mockup it gets reviewed against.

Of that run's 32 regions, 12 get a confident radius, 4 are answered with a stated caveat,
and **10 are refused outright** — the box turned out to hold text, or two components, or a
shape whose corners genuinely disagree. Ten refusals against twelve answers is the ratio
that makes the `measured` tag mean something.

## What you get

```
crops/
  task-active__task-row-highlighted.png    # 2x
  fab__fab-add-blob.png                    # 6x
  badge__category-badge.png                # 8x
  manifest.json                            # source box, scale, output size per crop
IMPLEMENTATION_PROMPT.md                   # entry point — read in full, first
spec/
  tokens.md                                # color, spacing, radius, type, elevation, contrast
  components.md                            # per-component specs, each pointing at its crop
measurements.txt                           # raw sampler output everything else derives from
```

The prompt is addressed to the *next* agent, not to you: a token system (clustered, not raw
values), a component-by-component spec pointing at each crop, suggested props and variants,
and an open-questions section listing what a single frame cannot answer.

It's split rather than delivered as one document because a whole screen runs past 300 lines,
and a builder shouldn't pay for the spec of a component it hasn't reached yet. The entry file
stands alone — paste only that and a correct build still starts — and it names what to read
and when. Same progressive disclosure the skill itself uses.

## Prerequisites

**Runtime**

- **Python 3.8+** on the machine that runs the skill — `python3` must be on `PATH`.
- **[Pillow](https://pillow.readthedocs.io/)**, the only third-party dependency
  (everything else is stdlib):

  ```bash
  pip install pillow
  # Homebrew / Debian / other externally-managed Python:
  pip install pillow --break-system-packages
  ```

**Host**

A Claude surface that can both see images and run shell commands — the two passes are
split between vision and the script, so neither alone is enough.

- **Claude Code** — the plugin install path below needs a version with plugin marketplace
  support (`/plugin`). Older versions can still use the manual skill copy.
- **Claude.ai / desktop** — requires the code-execution tool enabled for the conversation,
  since the scripts run in that sandbox rather than on your machine.

**Input image**

- Native-resolution capture. Anything already downscaled has thrown away the corner
  staircase and 1px borders that the crops exist to read.
- PNG, or another lossless format. JPEG artifacts shift sampled colors; the skill flags
  those results `guessed` rather than `measured`.
- A real screenshot, not a photo of a screen — moiré and uneven lighting make color
  sampling meaningless.
- Knowing the source DPR helps. `probe` guesses it from dimensions, but that only means
  anything for a real viewport capture — exported artboards land on round numbers no device
  produces, and there the guess is worthless. `probe` says so when it sees one.

## Install

**Claude Code**

```
/plugin marketplace add Magam9/design-teardown
/plugin install design-teardown@design-teardown
```

**Claude.ai / desktop** — grab the `.skill` bundle from
[Releases](https://github.com/Magam9/design-teardown/releases) and upload it in Settings → Capabilities.

**Manually** — copy `skills/design-teardown/` into `~/.claude/skills/` (personal) or
`.claude/skills/` (project).

## Use

Give Claude a screenshot and ask for a teardown. It triggers on its own for phrasings like
"break this design into components", "make a prompt from this screenshot", or "what are the
tokens here".

The scripts are usable standalone:

```bash
python3 slice_image.py probe shot.png              # size, device class, DPR guess
python3 slice_image.py crop regions.json           # per-region crops + manifest
python3 slice_image.py geometry regions.json       # bounding box + 4 corner radii per region
python3 slice_image.py colors regions.json         # palette with coverage %, corner probes
python3 slice_image.py contrast "#1F2937" "#FFF"   # WCAG ratio
```

`regions.json` accepts pixel or normalized (0–1) boxes:

```json
{
  "image": "shot.png",
  "dpr": 2,
  "regions": [
    {"id": "cta", "name": "primary-button", "box": [1256, 20, 1400, 52], "upscale": 4}
  ]
}
```

Upscale factor is chosen from region size when omitted, capped so a wide navbar doesn't
become a 4000px crop that burns context for nothing.

## How it works

Four passes, with a deliberate split of labour.

**1 — Structure, from the whole image.** The model reads the full screenshot and writes a
region map: page → sections → components → leaf elements, stopping where a thing becomes
reusable. Repeated elements are cropped once plus their variants.

**2 — Crops, from the original.** Each region is cut from the full-resolution source and
upscaled with `NEAREST`, not bilinear — smoothing destroys exactly the corner staircase and
1px borders the crop exists to reveal.

How much this buys you depends on the source. A 32px button inside a 3840px capture is
nearly gone once the image is scaled to a vision model's fixed input budget; on a 2000px
artboard the same button survives largely intact. The crops always help the model *look at
one thing at a time*; whether they also recover destroyed detail depends on how far the
source had to shrink.

**3 — Geometry, from arithmetic.** Corner radii are computed from the area each rounded
corner cuts away, not counted by eye. Eyeballing works only when the shape contrasts with
its background, and in a light theme it usually doesn't — a `#FAFCFE` card on `#FFFFFF` is
invisible at any magnification. This pass also knows when to refuse: it distinguishes a
shadow bleeding into an edge from a genuinely uneven shape, and voids any reading from a box
that turns out to hold text or two components rather than one.

**4 — Color, from arithmetic.** The region is quantized first, because `getcolors()` on a
real interface returns thousands of near-duplicate values from anti-aliasing and the actual
fill drowns in them. Corner probes disambiguate flat fill from a gradient from rounded
corners catching the page behind.

The division of labour: anything countable goes to the script, judgement stays with the
model. Vision models misread hex codes because anti-aliasing shifts perceived color; they
are good at knowing that a thing is a button and not a card border. The script is the
reverse.

On hosts that support subagents, the crop-reading pass is delegated — each subagent gets a
family of related crops and is *forbidden from reporting any number*. That makes inventing a
hex code structurally impossible rather than merely discouraged. The measurements never
leave the main context, because clustering fourteen near-identical grays into four tokens
needs all fourteen visible to one reader at once.

Measurements are clustered into tokens **before** the prompt is written. Fourteen
near-identical grays become four semantic tokens; paddings of 11/12/13px become one
`space-3`. A prompt built on 40 raw hex values produces code where every component has its
own shade of gray.

The crop/zoom half of this is not a novel idea — it's the same technique as Anthropic's
[crop/zoom tool](https://github.com/anthropics/anthropic-cookbook), which reports more than
doubled accuracy on a public chart-reading benchmark. Related evidence from
[ScreenSpot-Pro](https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding): narrowing the
search area lifted GUI grounding from 18.9% to 48.1% with no additional training.

## Known limitations

- **Coordinate drift on large screenshots.** Region boxes are estimated by eye on a
  downscaled view but cropped against the original, so boxes can be off on big captures.
  `geometry` reports the fill's true bounding box, which makes the drift visible and
  correctable, but the fix — a `resize` subcommand that pre-scales the image so emitted
  coordinates map 1:1 — isn't written yet.
- **Soft shadows contaminate the edge they fall on.** A shadow sits between a card's fill
  and the page in value, so that edge absorbs it. Diagnosed and reported rather than
  silently averaged, but it means one pair of corners per shadowed card is unusable.
- Single frame, so hover/focus/transition/breakpoint behavior is unavailable by
  construction. Reported as open questions rather than invented.
- Font family identification is a guess. The skill states which letterform tells it used.
- Photos of screens and heavily compressed images produce unreliable color. Flagged as
  `guessed` rather than silently reported as measured.

## Benchmarks

Not yet run. Planned, in order of cost:

1. **Synthetic round-trip** — render HTML from a known token set, screenshot, run the
   teardown, diff recovered values against ground truth. Exact, cheap, and the only eval
   that can actually verify the `measured` tag. Also the regression suite.
2. **[Design2Code](https://salt-nlp.github.io/Design2Code/)** end-to-end — 484 real
   webpages with metrics comparing a render of the generated code against the reference
   screenshot. Pipeline: screenshot → teardown → prompt → code → render → metrics, with
   raw-screenshot-to-code as the baseline. That delta is the number worth publishing.
3. **ScreenSpot-v2** for the region-mapping stage in isolation.

## License

MIT — covering the skill, the scripts, and the teardown output.

The example screenshot is not covered by it. It is
[FREE Freelancer Schedule Web](https://dribbble.com/shots/10858979-FREE-Freelancer-Schedule-Web)
by [Lorez](https://dribbble.com/Lorez), included as sample input with credit; see
[`examples/taskly-dashboard/README.md`](examples/taskly-dashboard/README.md).
