# design-teardown

Turn a UI screenshot into per-component crops and a measured implementation prompt.
Colors and geometry are sampled from pixels, not guessed.

A [Claude skill](https://code.claude.com/docs/en/skills). The output is a prompt plus a
folder of reference images — hand both to a coding agent, or to a person.

> Status: early. Works, but the numbers in [Benchmarks](#benchmarks) are not filled in yet.
> Personal tool published in case it's useful. Issues welcome; responses not guaranteed.

## Why slice the screenshot at all

A 32px-tall button inside a 1440px-wide capture is a handful of pixels once the image is
scaled to fit a vision model's fixed input budget. Border radius, 1px borders, shadow
falloff, and letter-spacing are simply not there to read. No amount of prompting recovers
detail that was destroyed at resize time.

So this skill crops each component out of the **full-resolution original** and magnifies it
before asking the model to describe it. Same corner, before and after:

| In the full screenshot | Cropped and magnified 4x |
|---|---|
| a blue smudge | ![button crop](examples/README-button-crop.png) |

The staircase on the corner is countable, so the radius is *measured* rather than guessed.

This is not a novel idea — it's the same technique as Anthropic's
[crop/zoom tool](https://github.com/anthropics/anthropic-cookbook), which reports more than
doubled accuracy on a public chart-reading benchmark. Related evidence from
[ScreenSpot-Pro](https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding): narrowing the
search area lifted GUI grounding from 18.9% to 48.1% with no additional training.

## What you get

```
crops/
  nav__top-navbar.png
  nav-cta__primary-button.png        # 4x
  card-1__feature-card.png           # 2x
  manifest.json                      # source box, scale, output size per crop
IMPLEMENTATION_PROMPT.md
```

The prompt is addressed to the *next* agent, not to you. It contains a token system
(clustered, not raw values), a component-by-component spec pointing at each crop, and an
open-questions section listing what a single frame cannot answer.

Every value is tagged:

| Tag | Meaning |
|---|---|
| `measured` | came out of the pixel sampler, or was counted on a magnified crop |
| `inferred` | derived from measured values plus an assumption (spacing scale, type scale) |
| `guessed` | no evidence in the image — font family, hover colors, transitions |

The tags exist so the recipient knows which numbers to trust. A spec that quietly invents a
hover color sends the next agent off building fiction.

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
- Knowing the source DPR helps. `probe` guesses it, but a wrong guess doubles or halves
  every number in the final spec, so correct it if you know better.

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

Three passes, with a deliberate split of labour.

**1 — Structure, from the whole image.** The model reads the full screenshot and writes a
region map: page → sections → components → leaf elements, stopping where a thing becomes
reusable. Repeated elements are cropped once plus their variants.

**2 — Style, from the parts.** Each region is cropped from the original and upscaled with
`NEAREST`, not bilinear — smoothing would destroy exactly the corner staircase and 1px
borders the crop exists to reveal. The model then reads the crops one at a time.

**3 — Color, from arithmetic.** The region is quantized first, because `getcolors()` on a
real interface returns thousands of near-duplicate values from anti-aliasing and the actual
fill drowns in them. Corner probes disambiguate flat fill (corners match) from a gradient
(corners differ in pairs) from rounded corners catching the page behind (all four differ).

The division of labour: anything countable goes to the script, judgement stays with the
model. Vision models misread hex codes because anti-aliasing shifts perceived color; they
are good at knowing that a thing is a button and not a card border. The script is the
reverse.

Measurements are clustered into tokens **before** the prompt is written. Fourteen
near-identical grays become four semantic tokens; paddings of 11/12/13px become one
`space-3`. A prompt built on 40 raw hex values produces code where every component has its
own shade of gray.

## Known limitations

- **Coordinate drift on large screenshots.** Region boxes are estimated by eye on a
  downscaled view but cropped against the original, so boxes can be off on big captures.
  Fix is a `resize` subcommand that pre-scales the image so emitted coordinates map 1:1 —
  not written yet.
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

MIT
