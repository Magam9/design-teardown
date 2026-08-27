# CLAUDE.md

Context for working on this repo. The code and README describe *what* things do; this file
records *why*, so decisions don't get relitigated.

## What this is

A Claude skill that turns a UI screenshot into per-component crops plus a measured
implementation prompt. The deliverable is a **prompt**, not code — a downstream agent builds
from it. Version 0.1.0, not yet published.

Layout: single plugin at repo root (`.claude-plugin/`), skill in `skills/design-teardown/`.
No `plugins/<name>/` nesting because there's only one plugin; `marketplace.json` points at
`"./"`.

## Decisions already made — don't reopen without a reason

**Name is `design-teardown`.** "Slicer" was rejected: the term is dominated by 3D printing
(Cura, PrusaSlicer), which poisons discoverability. "Teardown" maps to iFixit — disassemble
and document each part.

**`NEAREST` for upscaling, not bilinear.** Smoothing destroys exactly what the crop exists
to reveal: the corner staircase that makes radius countable, and 1px borders. Do not
"improve" this to a smoother filter.

**Upscale factor is capped on the long edge** (`MAX_OUTPUT_EDGE = 1600`). A 1440x72 navbar is
small by short edge, so naive logic gives it 3x and produces a 4320px crop that burns vision
context for zero gain.

**Colors are quantized before counting.** Raw `getcolors()` on a real interface returns
thousands of near-duplicates from anti-aliasing and the actual fill drowns. Values within
~8/255 are merged.

**Confidence tags (`measured`/`inferred`/`guessed`) are mandatory in output.** This is the
core product promise, not decoration. A spec that silently invents a hover color sends the
next agent building fiction. Font family is always `guessed`.

**Tokens are clustered before the prompt is written.** 14 near-identical grays → 4 semantic
tokens; paddings of 11/12/13px → one `space-3`. Raw values produce code where every
component has its own shade of gray.

**Script does arithmetic, model does judgement.** Anything countable belongs in
`slice_image.py`. Vision models misread hex (anti-aliasing shifts perceived color) but are
good at knowing a thing is a button, not a card border. Don't move color measurement into
the prompt, and don't move semantic segmentation into the script.

**Leading slashes in `.gitignore`** (`/crops/`, not `crops/`). Without them git would ignore
`examples/**/crops/` too — silently dropping the most valuable content in the repo.

**`version` is pinned in `plugin.json`.** Without it, every commit counts as a new release
for installed users.

**MIT.** Output gets embedded in users' codebases; copyleft would deter commercial use for
no benefit.

## Open work, roughly in priority order

1. **`examples/` is empty.** The README's whole argument rests on it. Needs at least one real
   teardown committed as-is: source screenshot, `regions.json`, `crops/`,
   `IMPLEMENTATION_PROMPT.md`. Candidate source: GitHub's new-repository form (dark theme,
   open dropdown, and two visible states — selected item plus focused search field).

2. **Coordinate drift on large screenshots.** Region boxes are estimated by eye on a
   downscaled view but cropped against the original, so they can be off on big captures. Fix
   is a `resize` subcommand that pre-scales the image so emitted coordinates map 1:1, per
   the `resized_size()` reference implementation in Anthropic's vision docs. ~20 lines. If
   that implementation is ported, check the cookbook license and attribute.

3. **Synthetic round-trip eval.** Render HTML from a known token set → screenshot → run the
   teardown → diff recovered values against ground truth. Exact, cheap, no annotation
   needed, and the only eval that can verify the `measured` tag. Also the regression suite.
   Metrics: color ΔE, radius error ±1px after dividing by upscale and DPR, spacing snap
   accuracy, DPR detection across @1x/@2x/@3x renders, font-size error.

4. **Design2Code end-to-end** for the headline number. Pipeline: screenshot → teardown →
   prompt → code → render → their metrics, with raw-screenshot-to-code as baseline. Note
   their corpus is C4 webpages, not modern app UIs, so the delta may not transfer to
   dashboard-style targets. Run 3–5 times per case; single-run comparisons are noise.

## Conventions

- `SKILL.md` stays under ~200 lines. Detail belongs in `references/`, loaded on demand
  (`style-extraction.md` before the style pass, `prompt-template.md` before writing output).
- The skill's `description` frontmatter is what triggers it — edit it carefully, and keep
  both what it does and when to use it.
- `slice_image.py` has no dependencies beyond Pillow. Keep it that way; it must run in a
  bare container.
- Prose in SKILL.md and references is instructional, addressed to the model. The generated
  `IMPLEMENTATION_PROMPT.md` is addressed to the *next* agent, imperative mood.

## Positioning

Published as a personal tool: MIT, no support promised, no roadmap commitments in the
README. Avoids the trap where a stale repo implies abandonment. The differentiator is
measured-not-guessed plus the crops as artifacts — not breadth of features.
