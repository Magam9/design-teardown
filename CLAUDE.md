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

**The output prompt is split across files, not delivered as one document.**
`IMPLEMENTATION_PROMPT.md` is the entry point; `spec/tokens.md` and `spec/components.md`
carry the bulk. A screen written as one file runs 300+ lines and the builder pays for the
whole thing before writing any code, including specs for components it hasn't reached. Two
constraints keep it working: the entry file must start a correct build if pasted alone, and
every token is defined in `spec/tokens.md` and referenced by name everywhere else — a value
duplicated across two files will drift. Single components stay single-file; multi-screen
flows get one `spec/<screen>.md` each.

**Tokens are clustered before the prompt is written.** 14 near-identical grays → 4 semantic
tokens; paddings of 11/12/13px → one `space-3`. Raw values produce code where every
component has its own shade of gray.

**Radius is measured by the `geometry` subcommand, not counted by eye.** The original plan
was to count the NEAREST staircase on an upscaled crop. That fails on the common case: a
`#FAFCFE` card on a `#FFFFFF` page is 5/255 apart and invisible at any magnification, so
eyeballing returns a confident wrong number rather than an imprecise one. Radii come from
the area each corner cuts away — an integral, so one stray shadow row moves it by pixels
instead of hundreds. Do not replace it with a row-inset method; that under-reports by
`sqrt(R)` and a single bad row destroys the reading.

**`geometry` refuses rather than guesses, in three cases**, and those refusals are a feature:
a shadow contaminating one edge (says which pair to trust), a box holding text or several
controls (density under 65% voids the reading), and corners that genuinely disagree
(organic blob shapes are real — the example has three). Don't "improve" these into always
returning a number.

**Colour clustering has two different tolerances on purpose.** `CORNER_TOLERANCE` (6) is for
dithering noise between corner probes. `SURFACE_TOLERANCE` (3) is for telling two surfaces
apart, and must stay below it — real designs put surfaces 5/255 apart, and a single
tolerance either merges them or reports gradients on every flat fill. Both bugs shipped
once already.

**The crop read may be delegated to subagents; measurement never is.** Step 6 fans out, and
only step 6. Subagents get crops and component names, and are explicitly forbidden from
reporting colours, dimensions, radii or font sizes — that prohibition is the whole point,
because it makes inventing a hex code structurally impossible rather than merely discouraged.
Two things break if this is loosened: token clustering needs all fourteen greys visible to
one reader at once, and variant detection is comparative, so agents must be grouped by
component family rather than one per crop.

Do not justify this as a context optimisation. The full crop set for a screen measures ~12k
image tokens — roughly twice the measurement text, and not what fills a window. It was
measured, not assumed. The benefit is containment; if someone later "optimises" the fan-out
for context and scatters the colour data, they will have traded the actual benefit away for
a saving that was never there.

**Script does arithmetic, model does judgement.** Anything countable belongs in
`slice_image.py`. Vision models misread hex (anti-aliasing shifts perceived color) but are
good at knowing a thing is a button, not a card border. Don't move color measurement into
the prompt, and don't move semantic segmentation into the script.

**Leading slashes in `.gitignore`** (`/crops/`, not `crops/`). Without them git would ignore
`examples/**/crops/` too — silently dropping the most valuable content in the repo. This has
now been broken twice, once as `crops/` and once as `/*/**/crops/`, which looks
root-anchored but still matches `examples/<name>/crops/`. Check with
`git check-ignore -v examples/*/crops/*.png` after touching that file.

**`version` is pinned in `plugin.json`.** Without it, every commit counts as a new release
for installed users.

**MIT.** Output gets embedded in users' codebases; copyleft would deter commercial use for
no benefit. It covers the skill, scripts and teardown output — **not** the example
screenshot, which is "FREE Freelancer Schedule Web" by Lorez
(dribbble.com/shots/10858979), credited in `examples/taskly-dashboard/README.md`. Any future
example needs the same treatment: named author, link, and an explicit carve-out from the
licence. Don't commit a screenshot whose author can't be named.

## Open work, roughly in priority order

1. **A second example, from a large native capture.** `examples/taskly-dashboard/` exists
   and is a full run, but its source is a 2000px exported artboard, where downscaling to a
   vision model's 1568px budget costs only 22%. The crop-and-magnify argument barely shows
   on it — the wins there all came from arithmetic. A 2560px or 3840px capture would
   demonstrate the other half of the claim. Candidate: GitHub's new-repository form (dark
   theme, open dropdown, and two visible states — selected item plus focused search field),
   which also covers dark mode, currently untested end to end.

2. **Coordinate drift on large screenshots.** Region boxes are estimated by eye on a
   downscaled view but cropped against the original, so they can be off on big captures.
   `geometry` now reports the fill's true bounding box, which makes the drift visible and
   hand-correctable — that's how the example's boxes were tightened — but the real fix is
   still a `resize` subcommand that pre-scales the image so emitted coordinates map 1:1, per
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
