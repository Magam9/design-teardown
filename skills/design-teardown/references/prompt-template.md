# Output prompt template

The deliverable is `IMPLEMENTATION_PROMPT.md`, written to be pasted into a fresh session of a coding agent that has the `crops/` folder available. Write it addressed to that agent, in the imperative — not as a report addressed to the user.

Keep it dense. Every line should be something the builder needs. Skip sections that have no content rather than filling them with "N/A".

---

## Required structure

````markdown
# Implementation prompt: [screen or component name]

Build the interface described below. Reference images are in `crops/`; the full
source screenshot is `[filename]`. Values tagged `measured` came from pixel
sampling and should be treated as accurate. Values tagged `inferred` are derived
and safe to adjust for consistency. Values tagged `guessed` have no evidence in
the source — use judgement.

## Assumptions

- Source capture: [W x H]px, DPR [n]x — all values below are in CSS px
- Target stack: [stack]
- [any other assumption made without confirmation]

## Design tokens

### Color
| Token | Value | Role | Confidence |
|---|---|---|---|
| `--bg-page` | `#RRGGBB` | page background | measured |

### Spacing
Base unit [n]px. Scale: [list]

### Radius
| Token | Value |

### Typography
| Token | Size / Weight / Line height | Used for | Confidence |

Font stack: `[stack]` (guessed — letterform tells: [what you observed])

### Elevation
| Level | Shadow | Used by |

## Layout

[Structure outside-in. Container widths, the grid or flex axis at each level,
gaps, alignment, and how sections stack. Name the crop that shows each part.]

## Components

For each component, in the order they appear:

### [ComponentName]  →  `crops/[file]`

- **Purpose:** one line
- **Box:** dimensions, padding, gap
- **Fill / border / radius / shadow:** token references, not raw values
- **Typography:** token references
- **Content:** what text and icons it holds; icon set and names if identifiable
- **Variants observed:** [list, each with its crop] — or `only the resting state is visible`
- **States not visible:** [list, with suggested treatment]
- **Props suggested:** the API this component should expose

## Responsive behavior

[What the single capture supports, then what must be decided. Be explicit that
breakpoint behavior is not observable from one frame.]

## Interaction and motion

[Anything the layout implies — dropdowns, modals, tabs. Mark all of it as
inferred from affordances, not observed.]

## Open questions

Numbered list of things the source cannot answer and that materially affect the
build. Each should be answerable with a sentence.

## Build order

Suggested sequence: tokens → primitives → composites → page assembly.
````

---

## Writing notes

**Token references over raw values.** In the components section write `--bg-surface` and `space-4`, not `#FFFFFF` and `16px`. The token table is the single source of truth; duplicating raw values there and in each component guarantees they drift.

**Point at crops constantly.** The crops are the highest-bandwidth part of the handoff. Every component heading carries its filename so the builder can look rather than parse prose.

**Don't describe what the image already shows.** "A card with a heading and two lines of body text" is redundant with the crop next to it. Spend the words on what the image *doesn't* say: the props, the states, the token mapping, the ambiguities.

**Open questions are the most valuable section.** They're where the prompt admits its limits, which is what stops the next agent from confidently building the wrong thing. Five sharp questions beat twenty vague ones. Good examples: "Does the sidebar collapse or overlay on mobile?", "Is the badge count live or static?", "Should the six feature cards come from data or be hardcoded?"

**Match the stack.** Adjust the components section to what the target actually needs — a Tailwind target wants utility-class hints and a `tailwind.config` token block; a plain CSS target wants custom properties; a shadcn/ui target wants to know which existing primitives to use instead of building from scratch, and should say so explicitly ("use `Button` with `variant="outline"`, don't rebuild it").

**Length.** A single component: half a page. One screen: two to four pages. A multi-screen flow: split into per-screen files with a shared token file, and say so at the top.
