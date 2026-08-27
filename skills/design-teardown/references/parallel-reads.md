# Delegating the crop read

How to fan step 6 out across subagents without losing the things that make the output worth having. Read this before spawning anything.

## What this is for

Not context savings. The full crop set for a screen is roughly 12k image tokens — real, but not what fills a window. What delegation buys is **containment**: a subagent handed nothing but images, and forbidden from reporting numbers, cannot invent a hex code or a radius. It has no way to. That turns "the script does arithmetic, the model does judgement" from an instruction into a property of the setup.

The cost is coordination. Every rule below exists because a naive fan-out breaks something specific.

## What stays in the main context, always

- `probe`, `geometry`, `colors` and `contrast` output. All of it.
- The region map, and therefore every component's name.
- Token clustering (step 7) and the written prompt (step 8).

Colour and geometry are global problems. Fourteen near-identical greys collapse into four semantic tokens only because one reader sees all fourteen at once; spacings of 11/12/13px become one `space-3` the same way. Split that across agents and each one reasonably reports its own value, and you get back exactly the raw-value sprawl the token system exists to prevent.

## Grouping

**One agent per component family, not per crop.** Group so that everything a reader needs to compare is in the same message:

| Group | Contents |
|---|---|
| card family | every card variant, including the "add" and empty ones |
| list rows | every row state — plain, selected, expanded, done |
| controls | buttons, steppers, badges, inputs, each variant |
| chrome | header, sidebar, nav, footer |
| one-offs | anything with no siblings, batched together |

Variant and state detection is comparative. An agent looking at one crop cannot tell you it is the hover state of another crop; it will describe a slightly different button and move on, and the state ladder — the most valuable thing in a screenshot — is silently lost.

Assign names centrally, from the region map, before fanning out. Two agents naming the same pattern `pinned-card` and `saved-item` produces a spec with a phantom extra component.

## The brief

Send each subagent: its crops, the component names and `kind` from the region map for those regions, and the target stack if it's known. Nothing else.

```
Look at the attached crops from one UI screenshot. They are magnified with
NEAREST, so the jagged edges are an artefact of the upscale, not the design.

For each named component, report:
  - purpose, one line
  - what it contains: text, icons, images, nested elements, in layout order
  - which of these crops are variants of the same component, and what
    distinguishes them
  - visible states, and what signals each one
  - the props it should expose to be reusable
  - the icon set and icon names, if you recognise them
  - anything that looks like a defect or an inconsistency in the design

Do NOT report colours, hex values, dimensions, padding, radii, font sizes or
shadow values. Those are measured separately and your estimate would be
substituted for a real measurement. If a distinction genuinely depends on one
— "these two differ only in fill" — say that in words, without the value.

Return structured notes, not prose. No preamble.
```

The prohibition is the load-bearing part. Without it a subagent will helpfully volunteer `#FFD470`, it will be plausible, and there is no signal in the returned text marking it as a guess rather than a measurement.

## Merging

Reconcile before writing anything:

- **Duplicate components under different names.** Two families describing the same skeleton means the grouping was wrong. Merge and note it.
- **Contradictory variant claims.** If one agent calls a row "selected" and another calls the same fill "completed", that's a real ambiguity in the source — put it in open questions rather than picking one.
- **Missing crops.** Check every region in the map came back. A subagent that dropped one fails silently.

Then join the semantic notes to the measurements by region `id`. The measurements are authoritative for every number; the subagent notes are authoritative for nothing except meaning.

## When not to do this

- Fewer than roughly a dozen crops — the coordination costs more than it returns.
- Hosts without subagents. The sequential read is the fallback and produces identical output.
- A single component. There is nothing to compare and nothing to parallelise.
