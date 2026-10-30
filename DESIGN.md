# Design

The brief asked for funky. This is an Operate surface, so the funk comes from four things only: type, palette, density and one signature move. Navigation, tabs, tables, selects and sliders stay standard.

## World: Indian highway, truck art

Painted lorries and roadside milestones. Confident type, one loud colour, and the yellow-capped National Highway milestone that every Indian traveller reads without thinking.

## Colour

Light mode only. Three colours: ink, marigold, rani. Tokens live in `client/src/styles/tokens.css`; use tokens only, never raw hex.

- `--ink` for text and outlines, `--marigold` for action, selection and the milestone cap, `--rani` for gaps and critical state.
- `--chalk` page ground, `--white` surfaces, `--line` hairlines.
- Gap scale: one hue, pale to deep rani, `--gap-1` to `--gap-5`. No-data is `--gap-none` with a hatch on the map.
- Older token names (peacock, parrot, sindoor, indigo-dye) stay as aliases of these values.

## Type

- Display and headings: **Anek Latin** variable (Ek Type, an Indian foundry), weights 600 to 800. Use the width axis: wide for page titles, condensed for dense labels.
- Body and UI: **Hind** 400, 500, 600 (Indian Type Foundry).
- Numbers: Hind with `font-variant-numeric: tabular-nums`. No monospace costume.
- Scale: 12, 13, 14, 16, 20, 28, 40, 56 px. Nothing under 12 px.
- Indian number grouping everywhere: 1,08,00,000 and "1.08 crore". Use `formatIN` from `client/src/lib/format.ts`.

## Shape and depth

Radius 4 for controls, 8 for panels, 999 for small chips. Flat: panels and overlays use a `--line` border. A light shadow only where a map overlay must lift off the map.

## Signature move: the milestone

The NH milestone is the one place the world becomes literal: a white stone with a rounded marigold cap. `<Milestone>` is the selected district's readout on the map, and the ranked "next stops" in the planner. The cap holds the code, for example `MH 12`. The body holds the distance-style reading, for example `1,240 EVs per charger`. Crisp CSS or SVG geometry, with no texture. It appears nowhere else. No truck-art florals, no "Horn OK Please" costume on working screens, except one line of wit in an empty state.

## Motion

Motion only explains state: a loading shimmer, progress, a short hover transition. No keyframe flourishes, pulses or slide-ins.

## Refuse

No inline styles except values computed at runtime. No gradients of any kind, eyebrow labels, dark shells, glass panels, side-stripe cards, nested cards, identical KPI card grids, the hero-metric template, emoji or glyphs as icons. Icons come from `lucide-react`.

Avoid em dashes in UI copy. Theme selection, focus rings and scrollbars from the palette.
