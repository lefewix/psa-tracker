---
name: PSA Submission Tracker
description: A grading tracker rendered as the hobby's own print artifact — the monthly price guide.
colors:
  spot-ink: "#8b5cf6"
  spot-ink-2: "#6366f1"
  spot-fill: "color-mix(in srgb,var(--ac) 86%,black)"
  spot-fill-hot: "color-mix(in srgb,var(--ac) 76%,black)"
  day-paper: "#f5f2ea"
  day-paper-top: "#faf8f1"
  day-surface: "#fdfcf7"
  day-ink: "#221e18"
  day-ink-strong: "#100d09"
  day-rule-strong: "#b5ae9c"
  night-paper: "#131110"
  night-surface: "#1c1917"
  night-ink: "#eae4d9"
  night-ink-strong: "#fbf7ee"
  hold-red-day: "#9c3222"
  hold-red-night: "#ffbfae"
typography:
  display:
    fontFamily: "'Barlow Condensed', 'Arial Narrow', 'Helvetica Neue', -apple-system, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "0.005em"
  headline:
    fontFamily: "'Barlow Condensed', 'Arial Narrow', sans-serif"
    fontSize: "24px"
    fontWeight: 700
    letterSpacing: "0.01em"
  figure:
    fontFamily: "'Barlow Condensed', 'Arial Narrow', sans-serif"
    fontSize: "15px"
    fontWeight: 700
    letterSpacing: "0.02em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: "'Barlow Condensed', 'Arial Narrow', sans-serif"
    fontSize: "11px"
    fontWeight: 600
    letterSpacing: "0.09em"
  mono:
    fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 600
rounded:
  none: "0"
  xs: "2px"
  sm: "3px"
  md: "4px"
  lg: "6px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.spot-fill}"
    textColor: "#fff"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "12px"
  button-primary-hover:
    backgroundColor: "{colors.spot-fill-hot}"
  filter-tab:
    backgroundColor: "transparent"
    textColor: "{colors.day-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "6px 13px"
  filter-tab-active:
    backgroundColor: "{colors.spot-fill}"
    textColor: "#fff"
  pill-stamp:
    backgroundColor: "transparent"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "5px 11px"
  modal-card:
    backgroundColor: "{colors.day-surface}"
    rounded: "{rounded.lg}"
    padding: "26px 28px"
  input:
    backgroundColor: "{colors.day-paper-top}"
    textColor: "{colors.day-ink}"
    rounded: "{rounded.md}"
    padding: "12px"
---

# Design System: PSA Submission Tracker

## Overview

**Creative North Star: "The Monthly Price Guide"**

The tracker is the hobby's own print artifact: a two-color price-guide newsprint ledger. The ground is warm paper (halftone-dotted, with an SVG fractal-noise "tooth" at 5% opacity so it never reads as flat vector fill); the voice is near-black ink; the store's brand accent is SPOT INK — it carries rules, stamps, fills, and prices, and nothing else does. Content sits as ruled rows on the page's own paper, not as floating cards. The light theme is the flagship "day edition"; dark is the "night edition" — the same paper inverted to warm ink-black with cream ink, never blue-gray. This world explicitly refuses the dark glassy SaaS dashboard.

Print devices are structural, not decorative: the classic thick-thin double rule under mastheads (3px bar + 1px hairline 5px below), 2px dotted leader lines connecting labels to figures, stamped pills rotated a fraction of a degree off true, punched-square progress checkboxes, dashed pencil rules for editable owner tags, and a fixed 6px spot-ink cover stripe along the top of every page.

**Provenance.** Grounded concept roll, ordered by resonance: (1) PSA slab/cert-label grammar, (2) nine-pocket binder page, (3) hobby price-guide newsprint ledger, (4) booster-foil reveal, (5) submission paperwork with stage stamps, (6) card-shop display case, (7) TCG card frame. The seed script (seed key `86ebdb28`) assigned index 3. The owner delegated all design decisions ("no preference, deploy what you think looks/feels best"), so no human direction-approval round was held — this was an unattended build under the assigned direction. Finish review ran 2026-07-31; disposition: ship.

**Key Characteristics:**
- Two-color print: warm paper + near-black ink + one store accent as spot ink
- Ruled ledger rows on the page paper; real surfaces reserved for modals
- Barlow Condensed (600/700, self-hosted) for mastheads, labels, and figures; system sans for body; monospace for cert numbers
- Thick-thin double rules, dotted leaders, stamped pills, halftone tint, newsprint noise
- White-label: the entire accent family derives from two env-supplied hexes via `color-mix`

## Colors

One warm neutral family per edition plus a single store accent from which every accent shade is derived; there is no third hue.

### Primary
- **Spot Ink** (`#8b5cf6` default; always the env value `PSA_ACCENT`): the one voice of color. Progress fills, focus outlines, active-tab fills, stamp borders, guide prices, the cover stripe. Validated as `#rrggbb` server-side so env can't inject CSS.
- **Spot Ink 2** (`#6366f1` default; `PSA_ACCENT_2`): ambient secondary, available to stores; every other shade is derived, so stores only ever pick two colors.
- **Derived accent shades** (all `color-mix(in srgb, var(--ac) N%, black|white)`): `--ac-hot`, `--ac-soft`, `--ac-pale`, `--ac-ice` mix toward **black on light** (85/80/68/45%) and toward **white on dark** (82/72/45/15%) — lighter on dark, deeper on light. `--ac-pale` is the workhorse text-accent (prices, view links, sub-labels).
- **Spot Fill** (`color-mix(in srgb, var(--ac) 86%, black)`; hover 76%): the only accent shade that does **not** flip with theme. It exists to carry white text — `#fff` on raw `#8b5cf6` is 4.23:1, under the 4.5 floor, and a store-supplied accent can be worse, so fills are always darkened rather than trusted, and hover deepens instead of brightening.

### Neutral
- **Day Paper** (`#f5f2ea`, top-of-page gradient to `#faf8f1`): the page ground, hue-warm. Surfaces step subtly brighter: surface `#fdfcf7`, surface2 `#f7f4ec`, surface3 `#f1eee3`.
- **Day Ink** (`#221e18`, strong `#100d09`): body and masthead text; also the masthead's double rule.
- **Muted ink ramp** (`m1–m11`, `#544f46` → `#767065` day / `#b0a794` → `#8a8274` night): eleven graded ink dilutions for meta text, labels, and de-emphasis.
- **Rules and hairlines**: solid borders `b1–b5` (`#ddd7c8` → `#b5ae9c` day) and alpha hairlines (`rgba(34,30,24,.16)` day / `rgba(234,228,217,.15)` night) for entry separators.
- **Night Paper / Night Ink** (`#131110` / `#eae4d9`, strong `#fbf7ee`): the night edition — warm ink-black and cream, same structure.
- **Hold/Error Red** (`#9c3222`/`#b03a2e` day, `#ffbfae`/`#ff9b8b` night): the sole functional exception to two-color print, reserved for holds and errors.

### Named Rules
**The Spot-Ink Rule.** The accent is one hue with derived shades, never a palette. Every accent variant is a `color-mix` of `--ac`; introducing a second decorative hue breaks the two-color print.
**The Fill-Never-Flips Rule.** Anything carrying white text uses `--ac-fill` (accent darkened 14%+), in both themes. Never put `#fff` on the raw accent; never brighten a fill on hover.
**The Warm-Paper Rule.** Neutrals are hue-warm in both editions — the material is paper, not glass. No blue-gray anywhere.
**The Honest-Paper Rule.** No accent-tinted surfaces in the day edition; the accent stays pure spot ink on untinted paper. (Night may tint its halftone dots with accent at 20%.)

## Typography

**Display Font:** Barlow Condensed 600/700 (self-hosted woff2 at `/font-600.woff2` and `/font-700.woff2`, preloaded; fallback `'Arial Narrow', 'Helvetica Neue', -apple-system, sans-serif`)
**Body Font:** System sans (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial`)
**Label/Mono Font:** `ui-monospace, 'SF Mono', Menlo, Consolas` — cert numbers only

**Character:** A newsprint pairing — condensed caps do the shouting (mastheads, labels, figures), a quiet system sans does the reading. All numerals are tabular (`font-variant-numeric: tabular-nums` on body). Uppercase + tracking is the condensed face's native register here.

### Hierarchy
- **Display / Masthead** (700, 34px desktop / 29px mobile, line-height 0.95, uppercase): page nameplates; the gate cover scales to `clamp(46px, 9.5vw, 68px)`.
- **Headline / Lot Number** (700 condensed, 24px, letter-spacing .01em): submission numbers, styled as listing headers.
- **Figure / Guide Price** (700 condensed, 15–16px, `--ac-pale`): the number the reader came for; its unit suffix drops to 10–10.5px, 600, muted.
- **Body / Meta** (400 system sans, 13–13.5px): descriptions, meta lines, hints.
- **Label** (600 condensed, 9.5–13px, letter-spacing .06–.14em, uppercase): stage labels, section tabs, stamps, sub-headings, buttons.
- **Cert numbers** (monospace, 13px, 600): certification numbers are data and stay monospace — never the condensed face.

### Named Rules
**The Two-Faces Rule.** Condensed caps for structure and figures; system sans for prose; mono for cert data. No other faces, and no system display faces.
**The Current-Stage Rule.** On mobile (≤640px), stage labels collapse to `font-size: 0`; only the CURRENT stage keeps its name and date.

## Layout

Single centered column, `max-width: 820px`, page padding `40px 20px 80px` (`32px 14px` on mobile). The page is one continuous sheet: ledger entries are separated by 1px hairline rules (`--chipline`), the list closes with a bottom rule, and entries carry generous internal padding (`24px 6px 22px`) instead of card margins. The toolbar (search + controls) is sticky at top with the page-paper background, a strong hairline underline, and a faint cast shadow. The card-scan grid is `repeat(auto-fill, minmax(160px, 1fr))` with 16px gaps (140px/12px mobile). Corner controls (settings gear, day/night flip) are fixed 42px squares at bottom-right. Rhythm steps observed: 6/10/16/22–26px. Entries settle in with a staggered 8px rise animation (0.04s steps, disabled under `prefers-reduced-motion`).

## Elevation & Depth

The system is flat by conviction: depth is conveyed by ink weight (rules, borders) and paper tone, not shadow. Ledger rows have `box-shadow: none` and transparent backgrounds; hover is a paper-tone wash, not a lift. Shadows exist only where something genuinely sits above the page.

### Shadow Vocabulary
- **Overlay lift** (`0 14px 40px var(--shc2)` / `0 14px 44px`): search preview dropdown and modals — real objects above the sheet.
- **Sticker cast** (`0 2px 6px var(--shc2)`): the grade badge, a paper label stuck on a scan.
- **Corner-button float** (`0 4px 14px var(--shc)`): the two fixed corner controls.
- **Toolbar underline** (`0 8px 20px -16px var(--shc3)`): a hint of lift under the sticky toolbar.

### Named Rules
**The On-The-Page Rule.** If it is part of the ledger, it lies flat on the paper. Only things physically above the page (modals, previews, lightbox, corner controls, stuck-on stickers) cast shadows.

## Shapes

Print geometry: square by default, softened only enough to not look digitalized. Ledger rows are radius 0 with ruled tops. Small stamped/tabbed elements use 2–3px; inputs and buttons 4px; modals and corner buttons 6px. Progress checkpoints are punched **squares** (9px, 2px radius), not dots. Stamps and grade stickers rotate slightly off-true (−1.4° to +0.6°) — hand-applied, not machine-set. Dashed borders mean "pencilled": margin-note hints, empty photo slots, editable owner rules, undo chips. Dotted borders mean "leader line": the price-line leader and the progress track (2px dotted).

## Components

### Buttons
- **Shape:** softly squared (4px radius), full-width in forms.
- **Primary:** spot-fill background (`--ac-fill`) with white condensed-caps label (600, 14.5px, .09em tracking), 12px padding.
- **Hover / Focus:** hover deepens to `--ac-fill-hot` (never brightens); active scales to .97; focus is the global 2px accent outline, offset 2px.
- **Destructive:** transparent field, error-red mixed border and hold-red text; hover washes 12% error-red.
- **Ghost text-buttons** (archive, hint-dismiss): borderless condensed caps in muted ink, warming toward full ink on hover.

### Chips
- **Section tabs (`.f`):** condensed caps 12.5px/600, transparent field, 1px strong border (`--b5`), 3px radius. Active tab is a solid spot-ink tab: `--ac-fill` fill + white text. The archive tab, when active, fills with muted ink instead of accent.
- **Stamp pills:** inked, not glowing — transparent field, 1.5px border of accent mixed 60% toward the page, `--ac-pale` text, rotated −0.8°. Done: muted ink, +0.6°. Hold: hold-red family.

### Cards / Containers
- **Ledger entry:** not a card — transparent background, 1px rule on top, radius 0, no shadow; hover is a 55% paper-tone wash.
- **Listing cell (`.gc`):** the one gridded surface — `--surface` fill, 1px `--chipline` border, 3px radius, 11px padding; hover strengthens the border only.
- **Modal (`.smodal .card`):** the exception that keeps a real paper surface — `--surface`, 1px border, 6px radius, `26px 28px` padding, overlay-lift shadow, over a `rgba(12,10,7,.72)` scrim.

### Inputs / Fields
- **Standard:** `--inp` field, 1px `--b5` border, 4px radius, 12px padding; focus swaps the border to pure accent and suppresses the outline (the border carries focus; no double ring).
- **Owner tag (inline ledger write-in):** borderless, a 1px dashed pencil rule underneath; focus turns it a 1.5px solid accent rule and boxes the field with `--inp`. Save flashes the rule green (`#3a7c4f`); error flashes `#b25555`. Behavior is law: Enter saves and never navigates; clicking a saved tag opens that person's page; on their own page the click no-ops.
- **Search:** boxed left-aligned variant with an inset icon, living in the sticky toolbar.

### Navigation
Section tabs (above) are the navigation. The masthead row wears the thick-thin double rule (3px solid ink + 1px hairline 6px below); the issue line ("Last refreshed…", condensed caps, muted) sits flush right. View links are condensed caps underlined with a half-strength accent rule, inking up fully on hover.

### Progress Checklist (signature)
The stage tracker is a checklist rule, not a progress bar: a 2px dotted leader for the track, a 2px solid spot-ink fill over the completed span, and punched squares at each stage — hollow when undone, solid spot ink when done, and the current one enlarged (13px), ringed in page ink, with a soft accent pulse (2.6s; disabled under reduced motion). Labels are 9.5px condensed caps.

### Dotted Leader Line (signature)
Label … leader … figure: condensed-caps label left, `2px dotted` rule stretching between, condensed 700 figure in `--ac-pale` right. The guide's namesake device; use it wherever a name meets a number.

## Do's and Don'ts

### Do:
- **Do** derive every accent shade with `color-mix` from `--ac` — white-label theming (`PSA_ACCENT`, `PSA_ACCENT_2`, `PSA_THEME`, optional store logo with chip/silhouette dark-mode modes) is a survival constraint; two other live stores consume it.
- **Do** emit both palettes always (`:root[data-theme="dark"]` and `"light"` blocks) so the client toggle flips instantly; the store's `PSA_THEME` is only the default.
- **Do** keep white-on-accent text on `--ac-fill` and deepen on hover (The Fill-Never-Flips Rule).
- **Do** set cert numbers in monospace — they are data.
- **Do** honor the owner-tag rulings (Enter saves, never navigates; click opens the person page; self-page click no-ops) and the randomized self-refresh (a random :12–:17 past each hour, so open tabs never stampede the server together).
- **Do** ship reduced-motion and reduced-transparency fallbacks for every animation and every frosted surface, as the build does.

### Don't:
- **Don't** float content on cards — ledger rows live flat on the page; only modals get a real paper surface, border, and shadow.
- **Don't** introduce blue-gray neutrals, glassy dark-dashboard surfaces, or a second decorative hue; the world is warm two-color print.
- **Don't** brighten accent fills on hover or put white text on the raw store accent — contrast is not guaranteed at 4.5:1.
- **Don't** replace the 👋 (newcomer hint) and 🎉 (all-tagged) copy emoji — they are owner-pinned copy, and they are the only two; they are not a license for glyph icons elsewhere (interface icons are inline stroke SVGs).
- **Don't** render stage labels on mobile except for the current stage.
- **Don't** use round dots for progress checkpoints — punched squares are the print grammar.
