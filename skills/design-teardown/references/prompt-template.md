# Output prompt template

The deliverable is written to be opened by a fresh session of a coding agent that has the `crops/` folder available. Write it addressed to that agent, in the imperative — not as a report addressed to the user.

Keep it dense. Every line should be something the builder needs. Skip sections that have no content rather than filling them with "N/A".

## Split it across files

**A full screen produces three files, not one.** A single-file spec for a screen runs 300+ lines, and the builder pays for all of it before writing a line of code — including the component specs for parts it hasn't reached yet.

```
IMPLEMENTATION_PROMPT.md     entry point — read in full, first
spec/tokens.md               color, spacing, radius, type, elevation, contrast
spec/components.md           per-component specs
```

Scale the split to the job:

| Scope | Files |
|---|---|
| One component, or a small fragment | a single `IMPLEMENTATION_PROMPT.md` |
| One screen | the three above |
| A multi-screen flow | entry + `spec/tokens.md` + one `spec/<screen>.md` per screen |

This is the same progressive-disclosure structure the skill itself uses, and for the same reason: load what's needed to start, and let the rest be fetched on demand.

Two rules that make the split work:

- **The entry file must stand alone as a prompt.** Someone who pastes only that file must still get a correct build started: what to build, what was assumed, the layout, the open questions, the build order, and an explicit instruction to read the other files. Aim for roughly 120 lines.
- **Every token lives in `spec/tokens.md` and nowhere else.** The component specs reference `--accent` and `space-4`; they never repeat `#FFD470` or `16px`. Duplicating a value across two files guarantees the two drift.

Paths in `spec/` are relative to `spec/`, so crops are `../crops/<file>.png`. Check they resolve before handing the folder over.

---

## Entry file: `IMPLEMENTATION_PROMPT.md`

````markdown
# Implementation prompt: [screen or component name]

Build the interface described below and in `spec/`. Reference images are in
`crops/`; the full source screenshot is `[filename]`.

**Read `spec/tokens.md` before writing any code, and `spec/components.md` before
building each component.** This file carries what you need in order to start.

| File | Contains | Read it |
|---|---|---|
| `spec/tokens.md` | color, spacing, radius, type, elevation, contrast audit | first, in full |
| `spec/components.md` | per-component specs, each pointing at its crop | per component |
| `crops/manifest.json` | source box, scale and output size for every crop | when locating a crop in the source |
| `measurements.txt` | the raw sampler output everything here derives from | when checking a number |

Every value is tagged. `measured` came from pixel sampling — treat it as
accurate. `inferred` is derived and safe to adjust for consistency. `guessed`
has no evidence in the source.

## Assumptions

- Source capture: [W x H]px, DPR [n]x, and how the DPR was established
- Target stack: [stack]
- [any other assumption made without confirmation]

## Layout

[Structure outside-in. Container widths, the grid or flex axis at each level,
gaps, alignment, how sections stack. Name the crop that shows each part.]

## Responsive behavior

[What the single capture supports, then what must be decided. Be explicit that
breakpoint behavior is not observable from one frame.]

## Interaction and motion

[Anything the layout implies — dropdowns, modals, tabs. Mark all of it as
inferred from affordances, not observed.]

## Open questions

Numbered list of what the source cannot answer and that materially affects the
build. Each answerable in a sentence. Include any accessibility failure that
needs a decision before launch.

## Build order

tokens → primitives → composites → page assembly, and which component to build
first because the rest inherit its API.
````

## `spec/tokens.md`

````markdown
# Design tokens — [name]

Part of `../IMPLEMENTATION_PROMPT.md`. Read that first for assumptions and
layout. All values are CSS px at DPR [n].

## Color
| Token | Value | Role | Confidence |
|---|---|---|---|

## Spacing
Base unit [n]px. Scale: [list]. Table of measured gaps and what they snapped to.

## Radius
| Token | Value | Applies to | Confidence |

Call out anything that is not a rounded rectangle — `geometry` reporting four
disagreeing corners on a shape that looks circular means a blob mask.

## Typography
| Token | Size / Weight / Line height | Used for | Confidence |

Font stack: `[stack]` (guessed — letterform tells: [what you observed])

## Elevation
| Level | Shadow | Used by | Confidence |

## Contrast audit
| Pair | Ratio | AA |

Report failures; don't silently fix them.
````

## `spec/components.md`

````markdown
# Components — [name]

Part of `../IMPLEMENTATION_PROMPT.md`. Token names are defined in `tokens.md` —
use the token, never the raw value.

## [ComponentName] → `../crops/[file].png`

- **Purpose:** one line
- **Box:** dimensions, padding, gap
- **Fill / border / radius / shadow:** token references
- **Typography:** token references
- **Content:** what text and icons it holds; icon set and names if identifiable
- **Variants observed:** [list, each with its crop] — or `only the resting state is visible`
- **States not visible:** [list, with suggested treatment]
- **Props suggested:** the API this component should expose
````

---

## Writing notes

**Token references over raw values.** In the components file write `--bg-surface` and `space-4`, not `#FFFFFF` and `16px`. `spec/tokens.md` is the single source of truth.

**Point at crops constantly.** The crops are the highest-bandwidth part of the handoff. Every component heading carries its filename so the builder can look rather than parse prose.

**Don't describe what the image already shows.** "A card with a heading and two lines of body text" is redundant with the crop next to it. Spend the words on what the image *doesn't* say: the props, the states, the token mapping, the ambiguities.

**Open questions are the most valuable section**, which is why they live in the entry file rather than buried in a spec file. They're where the prompt admits its limits, which is what stops the next agent from confidently building the wrong thing. Five sharp questions beat twenty vague ones. Good examples: "Does the sidebar collapse or overlay on mobile?", "Is the badge count live or static?", "Should the six feature cards come from data or be hardcoded?"

**Match the stack.** Adjust the components file to what the target actually needs — a Tailwind target wants utility-class hints and a `tailwind.config` token block; a plain CSS target wants custom properties; a shadcn/ui target wants to know which existing primitives to use instead of building from scratch, and should say so explicitly ("use `Button` with `variant="outline"`, don't rebuild it").
