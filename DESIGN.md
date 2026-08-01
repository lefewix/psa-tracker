---
name: PSA Submission Tracker
description: A white-label grading ledger executed at Apple fidelity — white sheet, hairline rows, glass chrome.
colors:
  accent: "#3a6fd8"
  accent-ambient: "#5b8def"
  accent-text-light: "color-mix(in srgb,var(--ac) 92%,black)"
  accent-text-dark: "color-mix(in srgb,var(--ac) 45%,white)"
  accent-hot-light: "color-mix(in srgb,var(--ac) 82%,black)"
  accent-hot-dark: "color-mix(in srgb,var(--ac) 82%,white)"
  accent-fill: "color-mix(in srgb,var(--ac) 86%,black)"
  accent-fill-hot: "color-mix(in srgb,var(--ac) 78%,black)"
  sheet-white: "#ffffff"
  sheet-graphite: "#17181a"
  surface-raised-dark: "#1c1d20"
  ink: "#1d1d1f"
  ink-inverse: "#f2f2f4"
  muted: "#6e6e73"
  muted-dark: "#98989f"
  tertiary: "#86868b"
  tertiary-dark: "#8a8a92"
  fill-quiet: "#f2f2f4"
  fill-quiet-dark: "rgba(255,255,255,.08)"
  hairline: "rgba(0,0,0,.1)"
  hairline-dark: "rgba(255,255,255,.12)"
  hairline-hover: "rgba(0,0,0,.28)"
  hairline-hover-dark: "rgba(255,255,255,.3)"
  track: "#ececef"
  track-dark: "rgba(255,255,255,.14)"
  row-hover: "rgba(0,0,0,.028)"
  row-hover-dark: "rgba(255,255,255,.045)"
  glass: "rgba(255,255,255,.72)"
  glass-dark: "rgba(30,31,35,.62)"
  glass-solid: "#ffffff"
  glass-solid-dark: "#212226"
  glass-rim: "rgba(255,255,255,.85)"
  glass-rim-dark: "rgba(255,255,255,.16)"
  grade-red: "#b12b2b"
  grade-red-dark: "#ff7a6e"
  alert: "#b03a2e"
  alert-dark: "#ff8a7a"
typography:
  large-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  figure:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "16.5px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  field:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
    fontFeature: "tabular-nums"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  micro:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  cert:
    fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  none: "0"
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "14px"
  capsule: "999px"
  orb: "50%"
spacing:
  hair: "2px"
  xs: "4px"
  sm: "7px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  xxl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent-fill}"
    textColor: "#ffffff"
    typography: "{typography.field}"
    rounded: "{rounded.md}"
    padding: "12px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.accent-fill-hot}"
    textColor: "#ffffff"
  button-compact:
    backgroundColor: "{colors.accent-fill}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "11px 18px"
    width: "auto"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent-text-light}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0"
  button-text-hover:
    backgroundColor: "transparent"
    textColor: "{colors.accent-hot-light}"
  input-field:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.md}"
    padding: "11px 13px"
    width: "100%"
  input-search:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.md}"
    padding: "10px 12px 10px 34px"
    width: "100%"
  chip-segment:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.body}"
    rounded: "{rounded.capsule}"
    padding: "7px 14px"
  chip-segment-active:
    backgroundColor: "{colors.glass-solid}"
    textColor: "{colors.accent-text-light}"
    rounded: "{rounded.capsule}"
    padding: "7px 14px"
  ledger-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "15px 12px"
  toolbar:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "12px 14px"
  scan-tile:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0"
  orb-control:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.muted}"
    rounded: "{rounded.orb}"
    size: "40px"
---

# Design System: PSA Submission Tracker

## Overview

**Creative North Star: "Canon, Played Straight"**

This is the category standard executed at Apple fidelity: a precision instrument for
watching cards move through a grading queue, refusing themed decoration entirely. The
sheet is white and edge-to-edge, rows are separated by hairlines rather than boxed into
cards, type is sentence-case system stack, and exactly one accent — supplied per store by
environment — carries every link, active state, and the single filled button. The world is
recognizable with all content removed, purely by its restraint plus its Liquid Glass
chrome. The direction is an owner-chosen standing exit (2026-07-31): the assigned grounded
direction was stood aside by the owner's call in favor of playing the category canon
straight.

Depth exists in one place only: the chrome. The sticky toolbar, the segmented filter
capsule, and the two fixed corner orbs are translucent, blurred, saturated, rimmed with a
specular top edge, and cast one soft shadow. Everything below them — rows, scans, values,
stage bars — sits flat on the sheet with no fill, no tint, and no shadow. That split is the
whole material story: glass floats, content does not.

Character is delivered by motion and precision instead of ornament. Rows settle in on a
short staggered rise; the progress capsule springs forward when a submission advances;
buttons and chips depress 3% under a press. Nothing else moves. The build ships both a
light and a dark palette on every page so the client toggle flips instantly, and the accent
is validated server-side so a store's brand color can never become a CSS injection or an
illegible label.

**Key Characteristics:**
- White edge-to-edge sheet; content rows are hairline-separated, never boxed
- One env-supplied accent (steel blue by default) as text plus one filled button
- Liquid Glass on chrome only — toolbar, filter capsule, corner orbs
- System font stack exclusively; sentence case throughout, never tracked uppercase
- Tabular numerals globally; cert numbers in monospace
- Both palettes always emitted; every accent shade derived by `color-mix`

## Colors

A near-neutral system — white or graphite ground, gray text ramp, no tinted surfaces — with
a single chromatic accent that a store owns, plus a reserved red that appears only on a
landed grade or an alert.

### Primary
- **Steel Blue** (`--ac`, env `PSA_ACCENT`): the store's brand accent. Never painted raw
  onto text or fills; every usable shade is derived from it.
- **Accent as Text** (`--ac-pale`): the accent deepened toward black on the white sheet and
  lightened toward white on the graphite one. This is what links, active filter labels, the
  current stage name, and inline actions actually use.
- **Accent Hover** (`--ac-hot`): the text accent's hover — deeper on light, brighter on dark,
  always further from the ground.
- **Accent Fill** (`--ac-fill` / `--ac-fill-hot`): the one filled surface. Unlike the text
  shades it does **not** flip with theme — it is darkened in both themes so white label text
  stays legible even when a store supplies a very light brand color.

### Secondary
- **Ambient Blue** (`--ac2`, env `PSA_ACCENT_2`): the store's second brand color, held for
  ambient/secondary brand expression. It never competes with the primary inside a row.

### Tertiary
- **Grade Red** (`--grade`): the color of a grade landing. Used on the grade line of a scan
  tile and nowhere else. It is the emotional payoff of the product; its scarcity is why it
  lands.
- **Alert Red** (`--err` / `--holdtx`): form errors, destructive actions, and the "On hold"
  pill. Same family as Grade Red, distinct token, distinct job.

### Neutral
- **Paper White / Graphite** (`--bg`): the sheet. Light is the flagship; dark is a neutral
  gray ground — never blue-gray, never pure black.
- **Ink** (`--txt`): near-black on white, near-white on graphite. All primary text.
- **Muted** (`--m1`): secondary text — metadata, captions, ETA pills, empty states, the
  inactive filter label.
- **Tertiary Gray** (`--tert`): the search glyph and other non-text furniture.
- **Quiet Fill** (`--inp` / `--surface3` / `--ph`): input grounds and image placeholders. The
  only filled rectangles in content, and they carry no border.
- **Hairline** (`--hair`): every rule in the system — row separators, image borders, glass
  edges — with `--hairh` as its hover state and `--hair2` as the softer variant inside
  settings panels.
- **Track** (`--track`): the unfilled portion of the stage capsule.
- **Row Hover** (`--hovrow`): the only tint content ever receives, and only on pointer devices.

### Named Rules
**The Two-Color Store Rule.** A store picks exactly two colors (`PSA_ACCENT`,
`PSA_ACCENT_2`). Every other accent shade is derived in CSS via `color-mix(in srgb, …)`.
Never hardcode a third brand color, and never bypass the derivation to hand-pick a shade.

**The Validated Accent Rule.** Env colors are matched against `#[0-9a-fA-F]{6}` server-side
and fall back to the default on any mismatch. A color arriving from configuration is data,
never CSS.

**The Darkened Fill Rule.** White text appears only on `--ac-fill`, which is always darkened
regardless of theme, and hover deepens it further. Brightening on hover drops the label
under 4.5:1, so the filled button's hover always goes darker.

**The Both-Palettes Rule.** Every page emits `:root`, `:root[data-theme="dark"]`, and
`:root[data-theme="light"]` blocks. Never ship a page that can only render one theme.

**The Reserved Red Rule.** Red belongs to a landed grade, an alert, or a hold. It is never a
decorative accent, a heading color, or a hover state.

## Typography

**Display Font:** system UI stack (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`, `Helvetica`, `Arial`)
**Body Font:** the same stack — there is no second family
**Label/Mono Font:** `ui-monospace` / `SF Mono` / `Menlo` / `Consolas`, for cert numbers only

**Character:** One family, six sizes, two weights. The type does no expressive work at all;
hierarchy comes from size, weight (400 vs 600), and gray level. Negative tracking appears
only at the two largest sizes, where the system face needs it.

### Hierarchy
- **Large Title** (600, 21px, 1.25, −0.015em): the page name in the glass toolbar
  ("Submissions", "Settings"). One per page.
- **Figure** (600, 16.5px, 1.3, −0.01em): the numbers that matter — lot number, ledger value,
  card value, settings panel titles. The row's anchor at each end.
- **Field** (400, 15px): inputs and search; the filled button's label is the same size at 600.
- **Body** (400, 13px, 1.45): the default. Metadata lines, stage line, pills, links, filter
  chips, owner tags, empty states.
- **Caption** (400, 12px, 1.5): subtitles under a title, sync notes, service line, helper text.
- **Micro** (400, 11.5px, 1.4): the sub-figure line under a value, preview-row secondaries,
  section labels inside the search preview.
- **Cert** (monospace, 11.5px): certification numbers on scan tiles. A prelim card falls back
  to the inherited face at 12px because there is no number to align.

### Named Rules
**The Sentence Case Rule.** Every string is sentence case. No `text-transform: uppercase`, no
letter-spaced label caps, no kickers or eyebrows anywhere in the system.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set globally on `body`. Values,
dates, and lot numbers align in a column without per-element intervention.

**The Monospace-For-Identifiers Rule.** Monospace is reserved for machine identifiers — cert
numbers and CLI strings. Never for prose, values, or emphasis.

**The System-Face Rule.** No webfonts. The system stack is the face; anything a webfont would
buy is bought instead with spacing and weight.

## Layout

A single centered column, `max-width: 820px`, on a page padded `14px 20px 96px`
(`12px 14px 88px` under 640px). The bottom padding reserves the corner-orb landing zone.

Content rows are **wider than the column**: the ledger row uses `padding: 15px 12px` with
`margin: 0 -12px` so its hover tint and hairline bleed past the text measure. That bleed is
what makes the sheet read as edge-to-edge rather than as a stack of blocks. The list carries
a closing hairline on its bottom edge.

The toolbar is sticky at `top: 10px` (`z-index: 20`); the filter capsule floats below it.
Scan grids are `repeat(auto-fill, minmax(152px, 1fr))` with an 18px gutter, tightening to
`minmax(136px, 1fr)` and a 14px gutter under 640px. Scan tiles hold a fixed `1.72 / 2.4`
aspect ratio — a card's proportions — so the grid never reflows as images load.

Spacing rhythm runs on a coarse 2 / 4 / 7 / 10 / 14 / 18 / 24 ladder: 2px between a title
and its subtitle, 7–10px inside chips, 12–14px between row elements, 18–24px between sections.

**Breakpoint:** one, at 640px.

### Named Rules
**The Current-Stage-Only Rule.** Under 640px only the *current* stage is ever named. The
stage line is one sentence ("Grading · stage 4 of 8") above the capsule bar; the system never
renders an eight-label stepper on a phone.

**The No-Wrap Segment Rule.** The filter capsule never breaks to a second row. Under 640px it
becomes a horizontally scrolling strip with the scrollbar hidden and
`overscroll-behavior-x: contain`.

**The Three-Line Row Rule.** A dashboard ledger row is three lines tall: identity + value,
stage line + bar, footer actions. Detail-only facts (stage entry dates) never enter the
dashboard row.

**The 16px Input Rule.** All text inputs go to 16px under 640px so iOS never zooms on focus.

## Elevation & Depth

Hybrid, split strictly by role. **Chrome is glass; content is flat.** The toolbar, filter
capsule, settings segmented bar, and the two fixed corner orbs share one material:
translucent ground, `blur(16px) saturate(170%)`, a hairline border, an inset specular top
rim, and one soft cast shadow. Content — rows, scan tiles, values, bars — has no background,
no border box, and no shadow at all. Depth in content is expressed only by the hairline and
by gray level.

Modals, the search preview, and the lightbox are the exceptions that prove the rule: they are
*detached* surfaces floating above the sheet, so they take a solid surface fill plus a deep
shadow rather than glass.

### Shadow Vocabulary
- **Glass** (`box-shadow: inset 0 1px 1px var(--rim), 0 10px 26px var(--shc)`): the only
  chrome elevation. Inset rim and soft cast, always together.
- **Segment Lift** (`box-shadow: 0 1px 2px var(--shc3)`): the active pill inside a capsule.
  The smallest shadow in the system.
- **Popover** (`box-shadow: 0 14px 40px var(--shc2)`): the search preview.
- **Modal** (`box-shadow: 0 24px 60px var(--shc2)`): the settings popup.
- **Lightbox** (`box-shadow: 0 24px 70px rgba(0,0,0,.45)`): the enlarged scan; the only
  fixed-value shadow, because it always sits on a dimmed backdrop.

### Named Rules
**The Glass-Is-Chrome Rule.** `backdrop-filter` appears on the toolbar, the filter/segment
capsules, and the corner orbs. Never on a content row, a scan tile, or anything holding data.

**The Bare-Content Rule.** Content never gets a card, a tint, a border box, or a shadow. If a
row needs separation, it gets a hairline.

**The Graceful Degradation Rule.** Every glass surface ships two fallbacks together:
`@supports not (backdrop-filter)` and `@media (prefers-reduced-transparency: reduce)` both
swap to `--glasssolid`, and the reduced-transparency branch also drops the lightbox to an
opaque 72% black scrim.

## Shapes

Corner language runs from square to circle by role, not by size. Ledger rows and settings
blocks are **radius 0** — they are rules on a sheet, not objects. Images take 6px (scan tiles,
covers, logo chip); a lightbox image takes 12px because it is presented rather than listed.
Inputs, buttons, and preview rows take 8px. Popovers and the compact toolbar take 12px; the
full toolbar and modal take 14px. Anything segmented or pill-shaped takes 999px. Corner orbs
are 40px circles.

Borders are always exactly 1px and always `--hair`. There is no second border weight and no
colored border except the owner tag's focus underline and its transient save states.

Every progress bar is a 4px capsule (2px radius) — track plus fill, nothing else.

### Named Rules
**The Hairline Rule.** One border weight (1px) and one border color (`--hair`) across the
entire system. A border that needs emphasis shifts to `--hairh` on hover, never to a thicker
stroke.

**The Square-Ledger Rule.** Rows, list containers, and settings blocks have zero radius.
Rounding a row turns it into a card, and this world has no cards.

## Components

### Buttons
- **Shape:** softly rounded (8px); compact variants keep the same radius at `auto` width.
- **Primary:** the accent fill with a `#fff` label, 600/15px, full width, 12px padding.
  Exactly one per form.
- **Hover / Focus:** background deepens to `--ac-fill-hot` over 180ms; focus takes the global
  2px accent outline at 2px offset.
- **Press:** `scale(.97)` over 140ms `ease-out`. Every pressable element does this; orbs use
  `.94`.
- **Text buttons:** accent-as-text on transparent, no padding, no border — "Archive", "View
  cards", "Undo", disclosure links. Hover shifts to `--ac-hot`.
- **Destructive:** transparent ground, alert-red label. It never becomes a filled red button.

### Chips
- **Style:** a floating glass capsule (999px) holds borderless segments; the track is a faint
  tinted layer inside the glass.
- **State:** inactive is muted 500-weight on transparent; active takes the `--segon` fill,
  accent-as-text, 600 weight, and the Segment Lift shadow. The archive filter is the one
  exception — when active its label is ink, not accent, so "Archived" never reads as a live
  link.
- **Press:** `scale(.97)`.

### Cards / Containers
There are no content cards. The row is a **ledger row**: transparent, zero radius, one top
hairline, `15px 12px` padding with `-12px` horizontal margin, no shadow. Its only state is a
hover tint on pointer devices. Archived rows drop to `opacity: .5` with `grayscale(.6)` and
lift to `.62` on hover.

### Inputs / Fields
- **Style:** quiet gray fill, **no border**, 8px radius, 15px/400, `11px 13px`.
- **Focus:** a 2px accent outline at zero offset — the fill does not change.
- **Search:** the same field inset 34px on the left for an inline stroked SVG glyph in tertiary
  gray; it lives inside the glass toolbar.
- **Error:** a 12px alert-red message below the form with a reserved `min-height` so the layout
  never jumps when it appears.

### Navigation
Navigation is the sticky glass toolbar: brand/logo and the 21px large title on the left, sync
status and controls on the right, search below. Back links are plain accent-as-text with a `←`
character and are history-aware. Under 640px the toolbar wraps, the logo drops to 26px, and
the sync block collapses to a single inline 11px line. Cross-page view transitions are on by
default (`@view-transition { navigation: auto }`) but explicitly disabled on settings pages,
where the layout differs enough that a crossfade reads as lag.

### Stage Bar (signature)
The product's signature component: one text line — current stage in accent-as-text 600, then
"· stage N of 8" in muted — above a 4px capsule whose fill animates its width over 350ms on
`cubic-bezier(.23, 1, .32, 1)`. Archived rows render the fill in muted gray instead of accent.
This is the only spring in the system and the moment the product exists for.

### Owner Tag (signature)
An inline text field that is invisible until touched: transparent ground, transparent bottom
border, inherited type. Hover reveals a hairline underline; focus turns the underline accent;
a successful save flashes green and a failure alert-red. Behavior is load-bearing: **Enter
saves and never navigates**, a click on a filled tag opens that person's page, and a click on
a tag on that person's own page is a no-op.

### Scan Tile (signature)
Image at a fixed 1.72/2.4 card ratio with a 6px radius and a hairline — no shadow, no
container. Below it: grade in Grade Red 600/13px, cert number in monospace micro, card name
clamped to three lines (two under 640px), value in Figure, then the owner tag pinned to the
bottom via `margin-top: auto`. While an image loads it carries a 1.1s linear shimmer sweep
that stops the instant the loaded class lands.

### Named Rules
**The One Filled Element Rule.** A screen has at most one filled accent surface — the submit
button. Everything else that uses the accent uses it as text.

**The Pointer-Only Hover Rule.** Every hover state lives inside `@media (hover: hover)`. Touch
devices never inherit a stuck hover.

**The Two-Emoji Rule.** 👋 (the new-visitor hint) and 🎉 (the all-tagged empty state) are the
only emoji in the product. No emoji icons, no emoji in headings, no third emoji.

**The Inline-SVG Icon Rule.** Every icon is an inline stroked SVG at 12–17px with
`stroke: currentColor`, so it inherits its context's color. No icon fonts, no glyph characters
standing in for icons, no raster icons.

## Do's and Don'ts

### Do:
- **Do** derive every accent shade with `color-mix(in srgb, var(--ac) …)` so a store's two env
  colors propagate everywhere.
- **Do** validate any env-supplied color against `#[0-9a-fA-F]{6}` before it reaches CSS.
- **Do** put white text only on `--ac-fill`, and deepen (never brighten) it on hover.
- **Do** emit both the light and dark palettes on every page so the client toggle is instant.
- **Do** separate content with a 1px `--hair` rule and nothing else.
- **Do** keep Liquid Glass on the toolbar, the segmented capsules, and the corner orbs only.
- **Do** ship the `@supports not (backdrop-filter)` and `prefers-reduced-transparency` solid
  fallbacks with every new glass surface.
- **Do** wrap decorative motion in `@media (prefers-reduced-motion: no-preference)` and kill it
  in the `reduce` branch, view transitions included.
- **Do** set monospace on cert numbers and keep tabular numerals everywhere else.
- **Do** name only the current stage under 640px.
- **Do** write in sentence case, in the system face.
- **Do** press-scale interactive elements (`.97`, orbs `.94`) — it is the system's tactility.

### Don't:
- **Don't** put a box, tint, fill, border, or shadow on a content row or scan tile.
- **Don't** apply `backdrop-filter` to anything holding data.
- **Don't** load a webfont; the system stack is the face.
- **Don't** use tracked uppercase, kickers, or eyebrow labels anywhere.
- **Don't** introduce a third brand color or a hand-picked accent shade outside `color-mix`.
- **Don't** use red for anything but a landed grade, an alert, or a hold.
- **Don't** add a second border weight or a colored border beyond the owner tag's focus underline.
- **Don't** round a ledger row; rounding turns it into a card and this world has none.
- **Don't** add a third emoji, an icon font, or a glyph character used as an icon.
- **Don't** add decorative motion — no glow, no spotlight, no parallax. The row settle and the
  stage bar are the entire motion budget.
- **Don't** let the filter capsule wrap to a second row on any viewport.
- **Don't** reach for near-black-plus-violet "AI default" surfaces or any themed retro world;
  the dark ground is neutral gray, never blue-gray and never pure black.
