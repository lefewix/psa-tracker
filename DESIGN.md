---
name: PSA Submission Tracker
description: A white-label grading tracker executed at Apple fidelity — grouped ground, raised content cards, lensed glass chrome.
colors:
  # every share below is clamped per accent by _share() in app.py and emitted in
  # THEME_VARS; these are the values for the default #3a6fd8.
  accent: "#3a6fd8"
  accent-ambient: "#5b8def"
  accent-text-light: "color-mix(in srgb,var(--ac) 92%,black)"
  accent-text-dark: "color-mix(in srgb,var(--ac) 45%,white)"
  accent-hot-light: "color-mix(in srgb,var(--ac) 82%,black)"
  accent-hot-dark: "color-mix(in srgb,var(--ac) 73%,white)"
  accent-fill: "color-mix(in srgb,var(--ac) 86%,black)"
  accent-fill-hot: "color-mix(in srgb,var(--ac) 78%,black)"
  accent-bar-light: "color-mix(in srgb,var(--ac) 100%,black)"
  accent-bar-dark: "color-mix(in srgb,var(--ac) 85%,white)"
  accent-ring-light: "color-mix(in srgb,var(--ac) 100%,black)"
  accent-ring-dark: "color-mix(in srgb,var(--ac) 96%,white)"
  ground-light: "#f2f2f7"
  ground-dark: "#101113"
  card-light: "#ffffff"
  card-dark: "#1c1d20"
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
  hairline-soft: "rgba(0,0,0,.07)"
  hairline-soft-dark: "rgba(255,255,255,.08)"
  hairline-hover: "rgba(0,0,0,.28)"
  hairline-hover-dark: "rgba(255,255,255,.3)"
  track: "#ececef"
  track-dark: "rgba(255,255,255,.14)"
  row-hover: "rgba(0,0,0,.05)"
  row-hover-dark: "rgba(255,255,255,.07)"
  glass: "rgba(255,255,255,.72)"
  glass-dark: "rgba(30,31,35,.62)"
  glass-solid: "#ffffff"
  glass-solid-dark: "#212226"
  glass-rim-top: "rgba(255,255,255,.85)"
  glass-rim-top-dark: "rgba(255,255,255,.16)"
  glass-rim-bottom: "rgba(15,20,30,.06)"
  glass-rim-bottom-dark: "rgba(0,0,0,.35)"
  scrim: "rgba(0,0,0,.4)"
  segment-track: "rgba(0,0,0,.045)"
  segment-track-dark: "rgba(255,255,255,.05)"
  segment-on: "#ffffff"
  segment-on-dark: "rgba(255,255,255,.1)"
  grade-red: "#b12b2b"
  grade-red-dark: "#ff7a6e"
  alert: "#b03a2e"
  alert-dark: "#ff8a7a"
  saved-green: "#2f9e68"
  saved-green-dark: "#43c383"
typography:
  large-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.021em"
  figure:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.012em"
  large-title-compact:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.017em"
  gate-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  field:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  field-mobile:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontFeature: "tabular-nums"
  control:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "16px"
    letterSpacing: "normal"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  micro:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  tag:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "normal"
  cert:
    fontFamily: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  none: "0"
  bar: "2px"
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "14px"
  xxl: "16px"
  gate: "20px"
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
    rounded: "{rounded.capsule}"
    padding: "12px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.accent-fill-hot}"
    textColor: "#ffffff"
  button-primary-compact:
    backgroundColor: "{colors.accent-fill}"
    textColor: "#ffffff"
    typography: "{typography.control}"
    rounded: "{rounded.capsule}"
    padding: "11px 18px"
    width: "auto"
  button-bare:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.none}"
    padding: "0"
    width: "auto"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent-text-light}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "12px 8px"
  button-text-hover:
    backgroundColor: "transparent"
    textColor: "{colors.accent-hot-light}"
    padding: "12px 8px"
  stage-action-pill:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.accent-hot-light}"
    typography: "{typography.control}"
    fontWeight: 600
    rounded: "{rounded.capsule}"
    padding: "7px 14px"
  button-glyph-hover:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.capsule}"
    padding: "12px 14px"
  button-destructive:
    backgroundColor: "transparent"
    textColor: "{colors.alert}"
    typography: "{typography.control}"
    rounded: "{rounded.capsule}"
    padding: "11px 0"
    width: "auto"
  input-field:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.capsule}"
    padding: "11px 16px"
    width: "100%"
  input-search:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    typography: "{typography.field}"
    rounded: "{rounded.capsule}"
    padding: "10px 16px 10px 36px"
    width: "100%"
  chip-segment:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.control}"
    rounded: "{rounded.capsule}"
    padding: "7px 14px"
  chip-segment-active:
    backgroundColor: "{colors.segment-on}"
    textColor: "{colors.accent-text-light}"
    rounded: "{rounded.capsule}"
    padding: "7px 14px"
  chip-archived-solo:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.capsule}"
    padding: "9px 14px 11px"
  chip-archived-solo-active:
    backgroundColor: "{colors.accent-fill}"
    textColor: "#ffffff"
    rounded: "{rounded.capsule}"
    padding: "9px 14px 11px"
  chip-tag:
    backgroundColor: "color-mix(in srgb,var(--ac-pale) 12%,transparent)"
    textColor: "{colors.accent-text-light}"
    typography: "{typography.tag}"
    rounded: "{rounded.capsule}"
    padding: "3px 9px"
  submission-card:
    backgroundColor: "{colors.card-light}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.xxl}"
    padding: "18px 16px"
    border: "1px solid {colors.hairline-soft}"
    shadow: "0 2px 10px rgba(20,25,35,.08)"
    gap: "14px"
  submission-card-hover:
    backgroundColor: "color-mix(in srgb,{colors.ink} 4%,#ffffff)"
    textColor: "{colors.ink}"
  toolbar:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xxl}"
    padding: "12px 14px"
  toolbar-compact:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "7px 8px"
  preview-panel:
    backgroundColor: "{colors.glass-solid}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "6px"
  preview-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
  modal-sheet:
    backgroundColor: "{colors.glass-solid}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "24px 24px 26px"
    width: "min(460px,94vw)"
  status-pill:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0"
  status-pill-shipped:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
  status-pill-pending:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
  status-pill-hold:
    backgroundColor: "transparent"
    textColor: "{colors.alert}"
  strip-tile:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0"
    width: "84px"
    height: "117px"
  strip-morechip:
    backgroundColor: "{colors.fill-quiet}"
    textColor: "{colors.muted}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    width: "84px"
    height: "117px"
  skip-link:
    backgroundColor: "{colors.glass-solid}"
    textColor: "{colors.accent-text-light}"
    typography: "{typography.control}"
    rounded: "{rounded.capsule}"
    padding: "10px 16px"
  scan-tile:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0"
  orb-control:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.muted}"
    rounded: "{rounded.orb}"
    size: "44px"
---

# Design System: PSA Submission Tracker

## Overview

**Creative North Star: "Canon, Played Straight"**

This is the category standard executed at Apple fidelity: a precision instrument for
watching cards move through a grading queue, refusing themed decoration entirely. Content
sits on raised cards over a quiet grouped ground — white cards on Apple's grouped grey
(#f2f2f7) in light, #1c1d20 cards on near-black #101113 in dark. (App Store grammar, owner
call 2026-08-08: the original hairline ledger read too fused on the phone — "not enough
distinction between panels" — and was retired.) Type is sentence-case system stack, and
exactly one accent — supplied per store by environment — carries every link, active state,
and the single filled button. The world is recognizable with all content removed, purely by
its restraint plus its Liquid Glass chrome and card rhythm. The direction is an owner-chosen
standing exit (2026-07-31): the assigned grounded direction was stood aside by the owner's
call in favor of playing the category canon straight.

Depth exists in one place only: the chrome. The sticky toolbar, the segmented filter
capsule, and the two fixed corner orbs are translucent, blurred, saturated, and **lensed** —
rimmed with a specular catch along the top edge and a falloff along the bottom, so they read
as curved glass rather than as frosted rectangles. Under them, and only visible through them,
sits an ambient ground: two very wide accent-derived radials pooled in the top corners that
give the lens something to refract. Depth otherwise lives in exactly one more
place: the content card — 16px radius, hairline-soft edge, one quiet cast shadow, separated
by gaps rather than rules. Inside a card everything stays flat: scans, values, stage bars
carry no fill, no tint, no shadow of their own. The material story is glass floats and
refracts; cards sit raised on the ground; content inside them does not move.

Character is delivered by motion and precision instead of ornament. Rows settle in on a
short staggered rise; a stage bar is knocked to zero and released to its served width **only
when that submission actually advanced since this browser last saw it**, so the one motion the
product exists for means "your cards moved" rather than "a page loaded"; the toolbar earns its
shadow only once content slides underneath it; overlays materialize by fading their scrim, ramping
their blur, and landing from 97%. Nothing else moves. The build ships both a light and a
dark palette on every page so the client toggle flips instantly, and the accent is validated
*and measured* server-side — relative luminance is computed at boot and every derived mix
clamped until it clears its WCAG target — so a store's brand color can never become a CSS
injection or an illegible label.

Delivery stays zero-build: the stylesheet and the two page-independent scripts are served
once from hashed, immutable `/app.css` and `/app.js` URLs, and only the env-derived theme
variables remain inline. Nothing is compiled, bundled, or fetched from a CDN — no webfonts,
no icon packages, no framework runtime.

**Key Characteristics:**
- Grouped ground carrying raised 16px-radius content cards, gap-separated (App Store grammar)
- One env-supplied accent (steel blue by default) as text plus one opt-in filled capsule
- Liquid Glass on chrome only — dual-rimmed, over an accent-derived ambient ground
- Three type rungs only: 26/700 masthead, 17/650 data, 14/400 body
- Single-line controls are capsules (999px); content-side surfaces stay square-ish
- Both palettes always emitted; every accent shade derived by `color-mix` and contrast-clamped
- A visible accessibility layer: skip link, live region, real dialog semantics, keyboard paths

## Colors

A near-neutral system — white or graphite ground, gray text ramp, no tinted surfaces — with
a single chromatic accent that a store owns, a whisper of that accent as room air behind the
glass, and a reserved red that appears only on a landed grade or an alert.

### Primary
- **Steel Blue** (`--ac`, env `PSA_ACCENT`): the store's brand accent. It is a *source*, not
  a paint: the only place raw `var(--ac)` reaches a pixel is the ambient ground's radial. Every
  shade the user actually sees — text, fill, bar, ring — is derived from it and clamped.
- **Accent as Text** (`--ac-pale`): the accent deepened toward black on the white sheet and
  lightened toward white on the graphite one. This is what links, active filter labels, the
  current stage name, search-preview tags, and inline actions actually use.
- **Accent Hover** (`--ac-hot`): the text accent's hover — deeper on light, brighter on dark,
  always further from the ground.
- **Accent Fill** (`--ac-fill` / `--ac-fill-hot`): the one filled surface. Unlike the text
  shades it does **not** flip with theme — it is darkened in both themes so white label text
  stays legible even when a store supplies a very light brand color.
- **Bar Accent** (`--bar`): the stage bar's fill, clamped to 3:1 against its own track. It
  exists because raw accent measured 2.48:1 against the dark track — a progress bar is
  non-text content and still has to be seen.
- **Ring Accent** (`--ring`): every focus indicator — the global `:focus-visible` outline,
  input focus, and the owner tag's underline and keyboard ring — clamped to 3:1 against
  **`--inp`**, not the sheet. Inputs take the ring at `outline-offset: 0`, so it rides the quiet
  input fill; `--inp` is the harder ground in both palettes, so clamping there is correct
  everywhere the ring is actually painted.

### Secondary
- **Ambient Blue** (`--ac2`, env `PSA_ACCENT_2`): the store's second brand color. It never
  appears as ink or as a fill; its whole job is the ambient ground, where it is mixed to
  6% (light) / 11% (dark) into the wider top-right radial.

### Tertiary
- **Grade Red** (`--grade`): the color of a grade landing. **One place only: the grade line of
  a scan tile.** A red "N grades landed" status pill and a red detail-page badge shipped
  briefly on 2026-08-01 and were removed the next day by owner ruling — see the Reserved Red
  Rule. It is the emotional payoff of the product; its scarcity is why it lands.
- **Alert Red** (`--err` / `--holdtx`): form errors, destructive text actions, and the "On
  hold" pill. Same family as Grade Red, distinct token, distinct job.
- **Saved Green** (`--ok`): one use only — the owner tag's underline flashing on a successful
  save. It is confirmation, never decoration, and never a status color anywhere else.

### Neutral
- **Paper White / Graphite** (`--bg`): the sheet, set on `<html>` so overscroll rubber-banding
  always reveals flat ground. Light is the flagship; dark is a neutral gray — never blue-gray,
  never pure black.
  The browser and installed-app chrome take the same ground: two `theme-color` metas keyed
  on `prefers-color-scheme`, matching the scheme the head script actually renders.
- **Ink** (`--txt`): near-black on white, near-white on graphite. All primary text.
- **Muted** (`--m1`): secondary text — metadata, captions, ETA pills, empty states, the
  inactive filter label, the archived stage-bar fill.
- **Tertiary Gray** (`--tert`): the search glyph and other non-text furniture.
- **Quiet Fill** (`--inp` / `--surface3` / `--ph`): input grounds, image placeholders, and the
  hover pill behind text actions. The only filled rectangles in content, and they carry no border.
- **Hairline** (`--hair`): every rule in the system — row separators, image borders, glass
  edges, filmstrip tiles — with `--hairh` as its hover state and `--hair2` as the softer
  variant used in exactly one place, the rule above a settings danger zone.
- **Track** (`--track`): the unfilled portion of the stage capsule.
- **Row Hover** (`--hovrow`): the only tint content ever receives, and only on pointer devices.
- **Glass Rims** (`--rim` / `--rimb`): the top specular catch and the bottom falloff. Both are
  sub-threshold on purpose — felt as curvature, never seen as an outline.
- **Scrim** (`--scrim`): the dim behind the lightbox and the modal sheets. One token, one
  value, both overlays — an overlay never invents its own dim.

### Named Rules
**The Two-Color Store Rule.** A store picks exactly two colors (`PSA_ACCENT`,
`PSA_ACCENT_2`). Every other accent shade is derived in CSS via `color-mix(in srgb, …)`.
Never hardcode a third brand color, and never bypass the derivation to hand-pick a shade.

**The Validated Accent Rule.** Env colors are matched against `#[0-9a-fA-F]{6}` server-side
and fall back to the default on any mismatch. A color arriving from configuration is data,
never CSS.

**The Measured Accent Rule.** Syntactic validation is not enough: kelly green and Pokémon
yellow are both valid hex and both illegible at the shares tuned for steel blue. Every
derived shade starts at its tuned share and walks 1% at a time toward its pole — black on
light, white on dark — until the measured contrast passes: `--ac-pale` ≥4.5:1 on the sheet,
`#fff` ≥4.5:1 on `--ac-fill`, `--ac-hot` ≥4.5:1 on the hover-pill ground, `--bar` ≥3:1 on the
track, `--ring` ≥3:1 on `--inp`. The pole itself always passes, so the walk cannot fail. A new
accent-derived token ships with its target and **the ground it is actually painted on** named,
or it does not ship — `--ring` was clamped against the sheet for one day while inputs painted
it on `--inp`, which is exactly the class of mistake this rule exists to catch.

**The Darkened Fill Rule.** White text appears only on `--ac-fill`, which is always darkened
regardless of theme and clamped until `#fff` clears 4.5:1 on it; hover deepens it further.
Brightening on hover drops the label under 4.5:1, so the filled capsule's hover always goes
darker.

**The Both-Palettes Rule.** Every page emits `:root`, `:root[data-theme="dark"]`, and
`:root[data-theme="light"]` blocks. Never ship a page that can only render one theme.

**The Reserved Red Rule.** Red belongs to a landed grade (on the scan tile), an alert, or a
hold. It never *announces* — **owner ruling, 2026-08-02**: a critique argued the grades-landed
event deserved red in the status column, that shipped as a "N grades landed" pill plus a red
detail badge, and the owner rejected both on sight. Grades-ready is a lowercase detail note and
nothing else; the news is the grade printed under the scan, not a banner about it.
Red is never a heading color, a hover state, an emphasis device, or an event announcement.

**The Ambient-Ground Rule.** The room tint is composed **only** from `--ac` and `--ac2` via
`color-mix`, so a white-label swap re-tints it for free. Never hardcode an ambient hue, never
raise it past 6%/4% (light) or 11%/8% (dark), and never let it reach mid-viewport — if you can
name where it stops, it is too strong.

## Typography

**Display Font:** system UI stack (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`, `Helvetica`, `Arial`)
**Body Font:** the same stack — there is no second family
**Label/Mono Font:** `ui-monospace` / `SF Mono` / `Menlo` / `Consolas`, for cert numbers only

**Character:** One family, three rungs, tracking scaled to size. The type does no expressive
work at all; hierarchy is weight + size + leading as a *set*, never size alone. The masthead
takes 700 because at 26px extra weight — not extra size — is what separates it from the data
rung; data values take 650, a real optical weight on SF that degrades gracefully to 600/700
on Segoe and Roboto.

### Hierarchy
- **Large Title** (700, 26px, 1.15, −0.021em): the page name in the glass toolbar
  ("Submissions", "Settings"). One per page. Drops to 22px/−0.017em under 640px so the
  masthead stays on one row; the 300px password gate sets its own 24px/−0.02em and does
  **not** change at the breakpoint.
- **Figure** (650, 17px, 1.3, −0.012em): the data rung — lot number, ledger value, card value,
  settings panel titles, the current stage name, and the page-header figures (the detail ETA,
  the person page's estimated cost). The operator sweeps these columns; they all sit on one
  weight. The toolbar states sync in chrome instead of a figure: `.sync`, one 6px dot
  (`--ok` live, `--m1` quiet, `--holdtx` stale) and one word at 12.5/500, the full phrase
  in a `.vh` span.
- **Field** (400, 15px): inputs, search, and the bare button reset (which sets 15/600).
- **Body** (400, 14px, 1.5): the default reading layer. Metadata lines, stage line, status
  pills, links, owner tags, card names, empty states. The stage name sits here too, at body
  size with the data rung's 650 weight (`.stage b`), the one place the two rungs cross.
  (Lifted from 13/1.45 on 2026-08-08 — owner found the sheet claustrophobic and the text small.)
- **Control** (500, 13px, 16px line box): control labels only — filter pills, compact
  buttons, the skip link. Stays at 13 because the capsule height arithmetic (38px at both
  breakpoints) is stated in the CSS and depends on the 16px line box.
- **Caption** (400, 12px, 1.5): subtitles under a title, sync notes, service line, helper text.
  The masthead subtitle alone runs 12.5px — half a pixel is all it needs to stop reading as a
  caption under a 26px title.
- **Micro** (400, 12px, 1.4): the sub-figure line under a value, preview-row secondaries,
  section labels inside the search preview. Merged up from 11.5 (2026-08-08); the caption
  tier is now a single 12px rung.
- **Tag** (500, 11px, 1.0): the search-preview category chip. `line-height: 1` keeps its 3px
  of vertical padding from growing the row.
- **Cert** (monospace, 12px): certification numbers on scan tiles. A prelim card falls back
  to the inherited face at 12px because there is no number to align.

### Named Rules
**The Three-Rung Rule.** There are exactly three hierarchy rungs: 26/700 masthead, 17/650
data, 14/400 body. Everything else (13 controls, 12 captions, 11 tags) hangs off the body
rung. A new size does not create a new rung.

**The Optical Tracking Rule.** Tracking is a function of size, never a style: 26px = −0.021em,
24px = −0.020em, 22px = −0.017em, 17px = −0.012em, 14px and below = 0. Nothing in this system
ever tracks positive. When a caption sits inside a tracked value (`.ledval span`), it resets
letter-spacing to normal, because tracking inherits and size does not.

**The Sentence Case Rule.** Every string is sentence case. No `text-transform: uppercase`, no
letter-spaced label caps, no kickers or eyebrows anywhere in the system.

**The One Punctuation Rule.** Shipped copy carries no em dash: a period, a colon or a comma
instead. The curly `’` is the only apostrophe, entity forms never ship.

**The One Word Per Thing Rule.** The PSA fetch is a *sync* in every string (never scan, which
is the card image, and never refresh, which is the browser reloading); the credential that opens
/settings is the *settings password* on the gate, in the panel and in every error.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set globally on `body`. Values,
dates, and lot numbers align in a column without per-element intervention.

**The Monospace-For-Identifiers Rule.** Monospace is reserved for machine identifiers — cert
numbers and CLI strings. Never for prose, values, or emphasis.

**The System-Face Rule.** No webfonts, and none in the repo — the face is the system stack,
and anything a webfont would buy is bought instead with spacing and weight.

## Layout

A single centered column, `max-width: 820px`, on a page padded `18px 20px 96px`
(`16px 14px 88px` under 640px). The bottom padding reserves the corner-orb landing zone.
Both orbs sit in one `<nav aria-label="Site controls">`, and on a touch screen they go inert
(`pointer-events:none`, `opacity .55`) for 150ms after each scroll event, so a tap that lands
mid scroll falls through to the card underneath.

Content sits in **raised cards flush with the column**: each submission is a card at
`padding: 18px 16px`, `margin: 0 0 14px` (`16px 14px` / `12px` gap under 640px), 16px
radius, `--hair2` edge and a `0 2px 10px` cast shadow. The gap between cards is the
separator — no hairlines between or around the list, no closing rule. An empty state takes
the same card (`48px 20px` padding, `14px` top margin), never bare text on the ground.
Inside a card, the mobile filmstrip still bleeds to the card's own padding edge
(`-14px`) so the last tile runs off the card edge as the "there is more" cue. Above 640px,
where there is no bleed, an overflowing strip carries the same cue as a 28px `mask-image`
fade on whichever edge still has tiles past it (`.sl` / `.sr`, set by the same FX_JS the
filter capsule uses); a strip that fits is never faded.

The toolbar is sticky at `top: 10px` (`z-index: 20`), preceded by a 1px sentinel that drives
its scroll-edge elevation; the filter capsule floats below it. Scan grids are
`repeat(auto-fill, minmax(152px, 1fr))` with an 18px gutter, tightening to
`minmax(136px, 1fr)` and a 14px gutter under 640px. Scan tiles hold a fixed `1.72 / 2.4`
aspect ratio — a card's proportions — so the grid never reflows as images load.
The grade line is always present on a tile, empty at its 21px line box on an ungraded card,
so graded and ungraded neighbours in one row share a baseline.

Spacing rhythm runs on a coarse 2 / 4 / 7 / 10 / 14 / 18 / 24 ladder: 2px between a title
and its subtitle, 7–10px inside chips, 12–14px between row elements, 18–24px between sections.

**Breakpoint:** one, at 640px. Under it the page-header `.synced` block goes full width and
left aligned, so its `.estnote` drops the `margin-left: auto` that right-aligns the 34ch measure
on desktop.

### Named Rules
**The Current-Stage-Only Rule.** Under 640px only the *current* stage is ever named. The
stage line is one sentence ("Grading · stage 4 of 8") above the capsule bar; the system never
renders an eight-label stepper on a phone.

**The No-Wrap Segment Rule.** *Below 640px* the filter capsule never breaks to a second row.
Down to 360px it is not an overflow box either — three pills measure ~247px and fit the
sheet — so the capsule stays the thin 38px control and the hit pseudo grows past it exactly
as on desktop (28px pill + 8px each way = the 44px floor). Only *below 360px* does the
capsule become the horizontally scrolling strip: scrollbar hidden, `overscroll-behavior-x:
contain`, a 22px shade riding whichever edge still has pills beyond it — and there the
overflow box clips the pseudo back to the capsule's own height, the narrowest-screen trade
(WCAG 2.5.8's 24px minimum still holds). Above 640px the capsule wraps (`flex-wrap: wrap`) —
the sheet is wide enough that a second row is rare, and the pseudo is layered at
`z-index: -1` precisely so a wrapped row cannot shadow the row above it.

**The Three-Band Row Rule.** A dashboard ledger row is three bands, top to bottom: identity +
value/status, the filmstrip contact sheet, and stage line + bar with its inline "View cards"
action (a footer line appears only when there is a ship date to state). Nothing else may be
added, and detail-only facts — stage entry dates, per-card grades, the full stepper — never
enter the dashboard row.

**The 16px Input Rule.** All text inputs, the search bar, and the owner tag go to 16px under
640px so iOS never zooms on focus.

## Elevation & Depth

Hybrid, split strictly by role. **Chrome is lensed glass; content is flat.** The toolbar, the
filter capsule, the settings segmented bar, and the two fixed corner orbs share one material:
translucent ground, `blur(16px) saturate(170%)`, a hairline border, an inset specular top rim,
an inset bottom falloff rim, and one soft cast shadow. Beneath them the ambient ground
(`body::before`, `position: fixed`, `z-index: -1`) lays two accent-derived radials in the top
corners — the layer that makes the glass read as a lens instead of a frosted rectangle.
Content lives in raised cards (16px radius, `--hair2` edge, one quiet cast shadow); inside a
card, elements — scan tiles, values, bars — carry no fill, tint, or shadow of their own.
Depth inside a card is expressed only by gray level.

Elevation is also **earned rather than assumed**: the sticky toolbar sits nearly flush at rest
and lifts to its full cast shadow only once an IntersectionObserver sentinel above it leaves
the viewport — the exact frame content starts sliding underneath. The transition runs 0.25s.

Modals, the search preview, and the lightbox are the exceptions that prove the rule: they are
*detached* surfaces floating above the sheet, so they take a solid surface fill plus a deep
shadow rather than glass. They materialize together — the scrim fades, its backdrop blur ramps
0 → 8px, and the sheet lands from `scale(.97)` — and exit faster than they enter.

### Shadow Vocabulary
- **Glass Lens** (`box-shadow: inset 0 1px 1px var(--rim), inset 0 -1px 1px var(--rimb), 0 10px 26px var(--shc)`):
  the chrome material. Both rims and the cast shadow, always together.
- **Toolbar At Rest** (`box-shadow: inset 0 1px 1px var(--rim), inset 0 -1px 1px var(--rimb), 0 1px 2px var(--shc3)`):
  the same lens with a whisper cast, for a bar that nothing has scrolled under yet.
- **Segment Lift** (`box-shadow: 0 1px 2px var(--shc3)`): the active pill inside a capsule.
  The smallest shadow in the system.
- **Popover** (`box-shadow: 0 14px 40px var(--shc2)`): the search preview.
- **Modal** (`box-shadow: 0 24px 60px var(--shc2)`): the settings and Discord sheets.
- **Lightbox** (`box-shadow: 0 24px 70px rgba(0,0,0,.45)`): the enlarged scan; the only
  fixed-value shadow, because it always sits on a dimmed backdrop.

### Named Rules
**The Glass-Is-Chrome Rule.** `backdrop-filter` appears on the toolbar, the filter/segment
capsules, the corner orbs, and overlay scrims. Never on a content row, a scan tile, or
anything holding data.

**The Dual-Rim Rule.** Every glass surface carries both rims — `--rim` on the top inset edge,
`--rimb` on the bottom. One rim alone is a frosted card; the pair is a lens. Neither may be
raised to the point of reading as a visible outline. **One sanctioned exception:** the solo
Archived pill in its pressed state (`.f.farch.fsolo.on`) drops both rims *and* its hairline
to transparent, because pressed it has to read as one solid accent lozenge and not as a
filled pill sitting inside a grey ring. It keeps its cast shadow — it is still floating at
the elevation it occupied a moment ago — and the border goes transparent rather than to zero
so the box geometry, and the height match against the sort pills, is untouched. A glass
surface may drop its rims only when it is *becoming* a filled control, never to simplify.

**The Earned-Elevation Rule.** A sticky surface may not cast a full shadow while nothing has
scrolled beneath it. Rest state is `0 1px 2px`; the full `0 10px 26px` is a state, flipped by
a sentinel, transitioned over 0.25s.

**The One-Card-Deep Rule** (supersedes the Bare-Content Rule, owner call 2026-08-08).
Content sits exactly one card deep: the submission card, the timeline card, the hint, the
gate. Nothing inside a card gets its own card, tint, border box, or shadow — nested cards
are always wrong. Separation inside a card is proximity and gray level.

**The Graceful Degradation Rule.** Every glass surface ships its fallbacks together:
`@supports not (backdrop-filter)` and `prefers-reduced-transparency: reduce` both swap to
`--glasssolid` via `background-color` only (never the shorthand, which would wipe the capsule's
track layer), the reduced-transparency branch drops overlay scrims to an opaque 72% black, and
the ambient ground is killed under reduced transparency, `prefers-contrast: more`, and
`@supports not (color-mix)`.

**The Named-Reduce Rule.** `prefers-reduced-motion: reduce` is a scoped, enumerated block, not
a global transition kill. It removes *travel* — the row settle, the bar run-out, the shimmer,
press-scale, the overlay scale landing and blur ramp, view-transition animations — and keeps
*feedback*: hover tints, focus rings, the toolbar's earned shadow, and a short opacity fade on
every overlay so "this is on top of that" still reads.

## Shapes

Corner language runs from square to circle by role, not by size. Every **single-line control is
a capsule** (999px): text inputs, the search bar, the filled button, the compact save button,
the destructive text button, filter pills, the search-preview tag, and the quiet circular hover
pills. Content-side surfaces stay square-ish on purpose. Ledger rows and settings blocks are
**radius 0** — they are rules on a sheet, not objects. Images take 6px (scan tiles, covers,
logo chip) and preview thumbnails 4px; a lightbox image takes 12px because it is presented
rather than listed. Preview rows and the quiet hover pill behind a text action take 8px. The
search preview panel and the modal sheet take 14px; the full toolbar takes 16px and the compact
search bar 14px. Corner orbs are 44px circles.

Borders are always exactly 1px and always `--hair` (or `--hair2` in a settings danger zone).
There is no second border weight and no colored border except the owner tag's focus underline
and its transient save states.

Every progress bar is a 4px capsule (2px radius) — track plus fill, nothing else. The fill is
`--bar` only while the sub is moving: an archived (`.card.arch`) or held (`.card.hold`) row
drops it to `--m1`, so grey agrees with the red hold pill instead of arguing with it.

### Named Rules
**The Hairline Rule.** One border weight (1px) and one border color (`--hair`) across the
entire system. A border that needs emphasis shifts to `--hairh` on hover, never to a thicker
stroke.

**The Square-Ledger Rule.** Rows, list containers, and settings blocks have zero radius.
Rounding a row turns it into a card, and this world has no cards.

**The Capsule-Control Rule.** If it is a single-line control the user acts on, it is a 999px
capsule and carries ~3px of extra side padding so text never crowds the round end. If it holds
content — a panel, a sheet, an image, a row — it is not.

## Components

### Buttons
- **Shape:** the filled primary and every pill-shaped control are capsules (999px); text
  actions are unshaped until hovered.
- **Bare element:** `button` is a **neutral reset only** — transparent, no color, no radius,
  no width, no margin; it keeps typography (inherited family, 15px/600) and the cursor. It
  carries no visual identity whatsoever.
- **Primary (`.fillbtn`):** the accent fill with a `#fff` label, capsule, full width, 12px
  padding, 12px top margin. Exactly one per form. The compact variant (`.sbtn`) is `auto`
  width, `11px 18px`, 13px.
- **Hover / Focus:** background deepens to `--ac-fill-hot` over 180ms; focus takes the global
  2px accent outline at 2px offset (inputs take it at zero offset).
- **Press:** `scale(.97)` over 140ms `ease-out`, set element-level because it carries no
  color and therefore cannot leak a fill. Orbs use `.94`.
- **Text buttons:** accent-as-text on transparent — "Archive", "View cards", "Undo",
  disclosure links. They carry an invisible padded hit box (`12px 8px` padding cancelled by an
  equal negative margin) so the resting layout is byte-identical to unpadded text. Hover is
  the colour deepen and nothing else — no painted fill (the hit box hangs over the stage bar
  and read as a stray sub-panel inside a card), no underline (tried and disliked; both owner
  calls 2026-08-08).
- **Stage-line pill (`.stage .view`):** the exception — the row's one link sits at the far
  end of the stage line as a visible quiet capsule (App Store's row action; a bar-row
  placement was tried and reverted same day, 2026-08-08). `--surface3` fill, `--ac-hot`
  label at 13/600 (the accent shade already clamped 4.5:1 against that fill), `7px 14px`,
  999px, baseline-aligned with the stage text. The bar below stays full width. Hover
  deepens the fill by 6% ink.
- **Destructive:** transparent ground, alert-red label, capsule radius so the focus ring
  follows the shape. It never becomes a filled red button.
- **Quiet save (`.sbtn.squiet`):** the destructive grammar in accent instead of red, for the
  settings saves demoted so one screen keeps one filled capsule (the verification code submit).

### Chips
- **Style:** a floating glass capsule (999px) holds borderless segments; the track is a faint
  tinted layer painted as a `background-image` inside the glass.
- **Solo pill (`.fsolo`):** the standalone Archived toggle is its own capsule — it carries the
  glass itself rather than riding in a wrapper, because a single pill inside a capsule prints
  a ring around nothing. It reads one rung quieter than the sort pills (12px/500 vs 13px) and
  lands at exactly 38px, the sort capsule's outer height at both breakpoints. It is the
  archived disclosure on all three list pages, and the dashboard's "N need owners" worklist
  link ("1 needs an owner" when a single card is untagged), which navigates away and so never
  sits inside the sort capsule.
- **Filter row (`.filterrow`):** sort capsule at one end, the solo pills paired in `.rowend` at
  the other. The row wraps at the same 10px gap, so on a phone the pair drops to a second line
  and the capsule keeps its full width instead of shrinking into a scroller. The person page
  runs the same row over its submission groups, sharing the dashboard's `psa_sort` choice.
- **Sort pills:** Newest, Order type, Return. Three, always the same three — a "Grades ready"
  fourth pill shipped briefly and was removed with the rest of the grades promotion
  (2026-08-02 owner ruling).
- **State:** inactive is muted 500-weight on transparent; active takes the `--segon` fill,
  accent-as-text, 600 weight, and the Segment Lift shadow. The Archived pill is the exception
  in both directions: pressed it takes `--ac-fill` with a `#fff` label (see the Opt-In Fill
  Rule) and drops its rims (see the Dual-Rim Rule), because it is a view switch and not a
  fourth sort choice.
- **Hit area:** each pill looks 30px tall (28px under 640px) and stays that way; a `::before`
  pseudo at `inset: -7px 0` (`-8px` under 640px) grows the target past the capsule to clear
  the 44px floor, vertically only, at `z-index: -1` so a wrapped row can never shadow the
  pill above it.
- **Search tag (`.pvtag`):** a quiet capsule chip, 11px/500, `3px 9px`, filled with
  `color-mix(in srgb, var(--ac-pale) var(--tagmix), transparent)` — 12% light, 18% dark,
  because a dark ground swallows a low-alpha wash. It is a category label, not a link.
- **Attention dot (`.schip.att`):** a 6px accent circle after the label on the settings
  account chip PSA is asking to verify; that chip also sorts to the head of its capsule. The
  dot is decorative, the words ride in a `.vh` span, and it stays accent, never red.
- **Press:** `scale(.97)`.

### Status Pills
The right-hand column of a dashboard row, right-aligned under the value, stacked at 3px. All
are 14px text with a 5px gap to an inline stroked SVG — no fill, no border, no capsule; a pill
here is a *word*, not a control. The column scans on two gray levels plus one red:
- **Dated ETA (`.pill`)**, muted: the default, "Back Sep 25". One vocabulary on every
  surface (`eta_words`): "Back" plus a short date, carrying the year whenever it is not this
  one ("Back Jan 20, 2027").
- **Shipped (`.pill.shipped`)**, ink with a muted icon: done, and real. The icon stays muted so
  the row's only ink outside the lot number is the fact itself.
- **Pending (`.pill.pending`)**, muted: "ETA pending", and "Was due Aug 20" once PSA has blown
  through the date. The class is a semantic hook only — a third, lighter status gray cannot
  clear 4.5:1 at 14px on the white sheet, so the clock icon and the label carry the
  difference, not a color step.
- **Hold (`.pill.hold`)**, alert red: the queue has stopped. **The only red in the column** —
  see the Reserved Red Rule for the grades pill that was tried here and removed. The pill stands
  alone: no explaining sentence on any surface (the owner, 2026-09-09 · the pill is enough). The
  detail page states the same alarm at the value rung, replacing its ETA figure with a red
  "On hold" (`.synced b.holdb`); a held sub rendering a normal ETA badge is a bug.
Grades-ready is not a pill and not a row footer line either (the owner, 2026-08-08): it is a
lowercase `.estnote` under the detail page's ETA badge, and nowhere else.

**The Hold Rule.** A hold never hides the return date: the dashboard row prints the hold pill
beside the return pill, and the detail badge leads with "On hold" above a "Back" line (T65).
The pill stands alone; the explanatory sentence was retired on 2026-09-09.

Archived rows carry no status pill at all: every archived sub is finished, the foot already
says so, and the extra pill made the column taller than the header and knocked the filmstrip
out of the rows' rhythm.

### Cards / Containers
The row is a **submission card**: `--surface` ground, 16px radius, `--hair2` edge, `0 2px
10px` cast shadow, `18px 16px` padding, 14px gap to the next card. Its only state is a hover
tint (`color-mix` of 4% ink over the surface) on pointer devices. Archived rows keep the full surface and carry
`grayscale(.55)` alone, in every view, lifting to full color on hover: an opacity wash fades the
card's own white and takes the ink under 4.5:1. The only true containers are detached surfaces —
the search preview panel (14px, 6px padding, solid `--surface`) and the modal sheet
(`min(460px, 94vw)`, 14px, `24px 24px 26px`).

**Failure reuses the 404 card**: a read that fails (locked or unreadable db) answers 500 with the
same gate box, titled "Something went wrong", never an empty dashboard.

### Filmstrip (signature)
Every dashboard row carries its own contact sheet: up to eight card fronts (`STRIP_MAX = 8`)
in line order, 84×117px at 6px radius with a hairline and a quiet-fill ground, 10px apart,
12px under the identity band. Past eight, the last tile becomes a **"+N" chip** — same box,
same radius, quiet placeholder ground, muted 14px/600 numeral — linking into the detail page,
so the strip is always one fixed-width run and never wraps. A sub with no imaged cards falls
back to its own cover thumb; with neither, the band is absent entirely rather than reserved.

It **scrolls at every width**, not only on phones: eight tiles measure 742px, so any sheet
narrower than ~782px — iPad portrait included — would otherwise push the whole page sideways.
The scrollbar is hidden, `overscroll-behavior-x: contain` keeps the gesture off the page, and
under 640px the strip bleeds to the row's full width (`margin: 10px -10px 0` with matching
padding) at 64×89px tiles, so the first tile starts at the text measure and the run continues
past the edge — the visual promise that there is more.

Each tile serves the stored thumbnail asset, not the `/small/` 380×636 scan the grid tiles
take: at 64-84px a row of eight of those cost the dashboard megabytes. Each tile is still a
real link to the large scan and opens the same lightbox the grid uses, matched
by the same `[href^="/img"]` selector. Every tile carries per-card alt text — the card's
subject, trimmed the same way the grid trims it — because eight focusable links per row is a
long walk otherwise; that walk is also why the dashboard has a skip link.

### Inputs / Fields
- **Style:** quiet gray fill, **no border**, capsule radius, 15px/400, `11px 16px`.
- **Focus:** a 2px accent outline at zero offset — the fill does not change.
- **Search:** the same capsule inset 36px on the left for an inline stroked SVG glyph in
  tertiary gray positioned 14px from the edge, clear of the curve. It lives inside the glass
  toolbar and is a real combobox: `role="combobox"`, `aria-expanded`, `aria-controls`, with a
  `role="listbox"` preview and `aria-activedescendant` tracking arrow-key travel.
- **Error:** a 12px alert-red message below the form with a reserved `min-height` so the layout
  never jumps when it appears. It is a `role="alert"` associated to the field by
  `aria-describedby`, and the field takes `aria-invalid` — the color is the least of it.
- **Disabled:** `opacity: .5` and the default cursor, nothing else. Submit buttons disable
  themselves in flight, so the dim *is* the loading state.

### Navigation
Navigation is the sticky glass toolbar: brand/logo and the 26px large title on the left, sync
status and controls on the right, search below. Back links are plain accent-as-text with a `←`
character and are history-aware. A page-level action shares that row, right-aligned in the sub
page's `.foot`/`.footacts` grammar: the person page's "Export CSV" is the one. The person page
pairs Back with a plain `Home` link in the same left group, because Back is history and hopping
person to person leaves it pointing at the previous person, not the dashboard.
Under 640px the toolbar wraps, the logo drops to 26px, and
the sync block collapses to a single inline 11px line. On any phone-sized viewport (640px wide
or under, or 500px tall or under, so landscape counts) the masthead condenses on scroll: the
brand row scrolls away and the search capsule alone stays pinned. Cross-page view transitions are the
root crossfade only (`@view-transition { navigation: auto }`), desktop-only: under 640px the
root is unnamed (`:root{view-transition-name:none}`) so phone navigations are instant swaps.
**The Unnamed-Glass Rule.** Never put a `view-transition-name` on a backdrop-filter surface:
when the destination page lacks its twin (detail pages have no toolbar; masthead and compact
bars are different bars), the glass snapshot floats through the navigation as a blurred
rectangle — shipped as a blur-flash on iPhone before this rule existed. Settings pages
disable navigation transitions entirely, where the layout differs enough that a crossfade
reads as lag.

### Accessibility Layer
Not a retrofit — a visible part of the system, and it has house styling.
- **Skip link (`.skip`):** the dashboard's first tab stop, parked off-screen and sliding to
  14px on focus. It is a glass-solid capsule with an accent label and a hairline — chrome
  grammar, because it is chrome.
- **Submission list (`#list`):** the dashboard's rows are a real list, `role="list"` on `#list`
  (only while rows exist) and `role="listitem"` per card, with each row's sub number as an `h2`
  under the masthead `h1`. Row headings, not ten tab stops apiece. That heading is also the
  row's link (`.numlink`), so it takes the pills' hit pseudo — `::before` at `inset: -11px 0`,
  growing the 22px line to the 44px floor vertically only, never across to the pills.
- **Live region (`.vh #live`):** a visually-hidden `aria-live="polite"` region on every list
  page. Saves, save failures, search result counts, and a sort pill's reversal are announced
  there. Two of the three pills keep their label when re-clicked, so the flip is speech only.
- **Lightbox:** a real dialog — `role="dialog"`, `aria-modal`, focus moves in on open and back
  to the opener on close, Escape closes, and Tab is held on the single close orb. The **scan
  itself is inert**: tapping the image does nothing, because the reveal has to survive being
  touched. The scrim and the `.lbx` close orb (44px, fixed dark circle, white glyph, top-right)
  are what close it. While it is open the page is **locked**: `overflow:hidden` on `body`, given
  back on close, plus `overscroll-behavior:contain` on `.lb` so a drag never chains through.
- **Disclosures:** the person and customer pages' archived toggles are disclosures and carry
  `aria-expanded` / `aria-controls`; the dashboard's is a VIEW SWITCH (it swaps which rows the
  always-visible list shows) and carries `aria-pressed` instead. All three use the solo-pill
  grammar. The dashboard's archived rows are not in the first paint: the pill fetches them
  from `/?arch=1` the first time it is switched on, and puts itself back to off if that fails.
- **Focus:** the global indicator is a 2px `--ring` outline at 2px offset (inputs at zero). The
  owner tag keeps its quiet accent underline for pointer focus and gets the full ring back on
  `:focus-visible`, because a 1px underline is not a focus indicator on the app's most-used
  control.
- **prefers-contrast: more** raises `--hair`, `--hairh`, `--m1`, and `--tert` per palette,
  emitted in the same three-block shape as the palettes themselves.

### Stage Bar (signature)
The product's signature component: one text line — current stage in accent-as-text at the
650 data weight, then "· stage N of 8" in muted — above a 4px capsule whose fill transitions
its width over 550ms on `cubic-bezier(.23, 1, .32, 1)`.

**An unknown status draws no bar.** A step the stage map does not carry prints "Status
unknown" on the stage line, muted and unbolded, with no capsule under it (`.stage.nobar`
drops the line's bottom margin, so the row keeps the same rhythm as a bar row).

**The run-out is earned, not ambient.** Each bar carries `data-k` (its sub number) and
`data-st` (its stage index); FX_JS keeps a `psa_stage` map in `localStorage` and knocks a bar
back to 0% — releasing it on the same 40ms stagger — **only for a sub whose stage differs from
the one this browser last saw**. A stage is recorded as *seen* only once its bar has actually
been on screen with the tab visible (IntersectionObserver, plus a `visibilitychange` gate):
committing every bar at render burned the signal twice over — an hourly reload of a hidden tab
played the run-out to an empty room and marked everything current, and a row thirty down could
advance, never be scrolled to, and never animate again. Every other bar renders at its served width with no travel.
First sight of a sub never animates: there is no baseline, so there is no claim. Replaying it
on every render, including the silent hourly reload, spent the product's one earned motion on
page loads — roughly 40 celebrations a week for an event that happens twice a month, which is
ambient, not earned. Archived rows render the fill in muted gray instead of accent. Reduced
motion returns before the knock, so the served width is never touched and there is no
zero-width frame.

### Owner Tag (signature)
An inline text field that is invisible until touched: transparent ground, transparent bottom
border, inherited type. Hover reveals a hairline underline; focus turns the underline accent;
a successful save flashes `--ok` green and a failure alert-red. Behavior is load-bearing:
**Enter saves and never navigates** — but that governs the *editing* state only. On a filled
readonly tag, Enter visits that person's page, mirroring the click; the tag's own label says
so ("Click or press Enter to open their cards, click again or type to rename"). A click on a tag on that person's own
page is a no-op. Tooltip and accessible name are the **same one sentence**, never two different
sets of instructions. Under `pointer:coarse` a pencil sits beside the field as the edit affordance,
since a tap navigates instantly; it hides on `.own:focus` so the underline runs full width
while editing, never on the row's `:focus-within`, which swallowed its own tap.

### Scan Tile (signature)
Image at a fixed 1.72/2.4 card ratio with a 6px radius and a hairline — no shadow, no
container. Below it: grade in Grade Red 600/14px, cert number in monospace micro, card name
clamped to two lines with a reserved **`min-height`** (40px — never a fixed height, which
clips the second line mid-glyph under text-only zoom), the set line demoted below it, value on
the 17/650 data rung, then the owner tag pinned to the bottom via `margin-top: auto`. Tiles
carry **no `content-visibility`** — its paint containment clipped everything that reaches past
the tile box (focus rings, the hover pill's negative-margin bleed), so it was removed; the
off-screen cost it targeted is handled in FX_JS instead, which lands the loading sweep only
when a still-loading tile approaches the viewport. While an image loads it carries a 1.1s
linear shimmer sweep that stops the instant the loaded class lands. A scan that fails to load
is swapped for the same `.ph` placeholder a card with no scan renders, anchor and all, so the
grid rhythm holds and the dead tile no longer opens the lightbox.

### Named Rules
**The Opt-In Fill Rule.** Filled accent identity is opt-in, per element. It lives on
`.fillbtn` and on exactly one other element: `.f.farch.on`, the pressed Archived pill, which
paints `--ac-fill` with a `#fff` label because Archived is a **view switch**, not a fourth
sort choice, and borrows the primary button's grammar to say so. That exception is written at
the rule in the stylesheet; a second one needs the same argument and the same comment. The
bare `button` element selector carries **only** neutral resets — no background, no color, no
radius, no width, no margin — and no `button:hover` rule may set a background or a color.
Attaching identity to the element selector once shipped a P1: every text action, filter pill,
and orb in the app inherited a blue capsule on hover. Specificity patches only move the fight
around; the fill is opt-in, permanently.

**The One Filled Element Rule.** A screen has at most one filled accent surface at a time —
the submit capsule on a form page, the pressed Archived pill on a list page (the two never
share a screen). Everything else that uses the accent uses it as text.

**The Revealed-Hit-Area Rule.** A padded text action shows its hit box on hover as a quiet
`--surface3` fill: 8px rounded for inline text actions (they sit inside a sentence of layout,
and a capsule would read as a permanent control), 999px circles for square-ish glyph actions.
The fill is what tells you the target you are about to hit.

**The Pointer-Only Hover Rule.** Every hover state lives inside `@media (hover: hover)`. Touch
devices never inherit a stuck hover.

**The Text-That-Looks-Like-A-Link Rule.** A line that carries link styling must be a link. When
the same string is rendered as static text, it takes `.sublink-static` — muted, 400 weight,
default cursor, and excluded from every hover rule by `:not(.sublink-static)`. Styling hooks
are classes; an inline `style` attribute is never one. For the same reason the two non-row
card variants (`.card.grp`, `.card.tlcard`) explicitly refuse the row hover tint: they are
layout containers wearing the row's class, not rows you can act on.

**The Two-Emoji Rule.** 👋 (the new-visitor hint) and 🎉 (the all-tagged empty state) are the
only emoji in the product. No emoji icons, no emoji in headings, no third emoji.

**The Inline-SVG Icon Rule.** Every icon is an inline stroked SVG at 12–17px with
`stroke: currentColor`, so it inherits its context's color. No icon fonts, no glyph characters
standing in for icons, no raster icons.

## Do's and Don'ts

### Do:
- **Do** derive every accent shade with `color-mix(in srgb, var(--ac) …)` so a store's two env
  colors propagate everywhere, ambient ground included.
- **Do** clamp a derived token against the ground it is actually painted on, not the ground
  behind that one.
- **Do** keep a row on screen, in its new state, while its Undo chip is up — a chip that lives
  inside the row cannot be reachable if the row leaves the view the moment it flips.
- **Do** give a destructive-ish action the same undo grammar the owner tag uses, and announce
  it. Reversibility belongs to the action that is hard to reverse, not the easy one.
- **Do** hand focus to the Undo chip when disabling the pressed button would drop it to body,
  and back to a real control when the chip goes away.
- **Do** put a state-changing control in the `.foot` line of the rows that need it — archiving
  is a dashboard action, not a detail-page pilgrimage.
- **Do** validate any env-supplied color against `#[0-9a-fA-F]{6}` before it reaches CSS.
- **Do** clamp every new accent-derived shade server-side against a named ground and a named
  target (4.5:1 for text, 3:1 for bars and focus rings) rather than trusting a tuned share.
- **Do** put white text only on `--ac-fill`, and deepen (never brighten) it on hover.
- **Do** paint focus indicators with `--ring` and the stage bar with `--bar`, never raw `--ac`.
- **Do** emit both the light and dark palettes on every page so the client toggle is instant.
- **Do** separate content with a 1px `--hair` rule and nothing else.
- **Do** give every glass surface both rims (`--rim` top, `--rimb` bottom) plus its cast shadow.
- **Do** keep Liquid Glass on the toolbar, the segmented capsules, and the corner orbs only.
- **Do** ship the `@supports not (backdrop-filter)`, `prefers-reduced-transparency`, and
  `@supports not (color-mix)` fallbacks with every new glass or ambient surface.
- **Do** put the filled identity on `.fillbtn` and leave the bare `button` selector a reset.
- **Do** reveal a padded text action's hit area on hover as a quiet `--surface3` fill.
- **Do** enumerate reduced-motion exemptions by name, keeping opacity fades on overlays.
- **Do** make a single-line control a 999px capsule and leave panels, sheets, and rows square-ish.
- **Do** scale tracking to size (−0.021em at 26px down to 0 at 13px) and reset it when a caption
  sits inside a tracked value.
- **Do** set monospace on cert numbers and keep tabular numerals everywhere else.
- **Do** name only the current stage under 640px.
- **Do** write in sentence case, in the system face.
- **Do** press-scale interactive elements (`.97`, orbs `.94`) — it is the system's tactility.
- **Do** give a horizontally scrolling strip a hidden scrollbar, `overscroll-behavior-x:
  contain`, and a mobile bleed to the row's full width.
- **Do** give every image in a strip or grid real alt text drawn from the card's own name.
- **Do** ship overlays as real dialogs: role, `aria-modal`, focus in and back out, Escape, and
  an explicit close control.
- **Do** announce saves, failures, and result counts through the page's `aria-live` region.
- **Do** attach form errors with `aria-describedby` + `role="alert"` and reserve their height.
- **Do** hook styling on a class (`.sublink-static`), never on an inline `style` attribute.

### Don't:
- **Don't** attach background, color, radius, width, or margin to the bare `button` selector,
  and never write a `button:hover` that paints.
- **Don't** put a box, tint, fill, border, or shadow on a content row or scan tile.
- **Don't** apply `backdrop-filter` to anything holding data.
- **Don't** let a sticky surface cast its full shadow before content has scrolled under it.
- **Don't** raise the ambient ground until you can name where it stops, and never build it from
  anything but `--ac` / `--ac2`.
- **Don't** load a webfont or add one to the repo; the system stack is the face.
- **Don't** use tracked uppercase, kickers, or eyebrow labels anywhere.
- **Don't** introduce a third brand color or a hand-picked accent shade outside `color-mix`.
- **Don't** use red for anything but a landed grade, an alert, or a hold, or green for anything
  but a saved owner tag.
- **Don't** add a second border weight or a colored border beyond the owner tag's focus underline.
- **Don't** round a ledger row; rounding turns it into a card and this world has none.
- **Don't** add a fourth type rung; a new size hangs off the caption tier or it does not ship.
- **Don't** kill motion with a blanket `*{transition-duration:.01ms}`; enumerate the travel and
  keep the feedback.
- **Don't** add a third emoji, an icon font, or a glyph character used as an icon.
- **Don't** add decorative motion — no glow, no spotlight, no parallax. The row settle, the bar
  run-out, the earned toolbar shadow, and the overlay materialize are the entire motion budget.
- **Don't** let the filter capsule wrap below 640px — there it scrolls, with a shade on each
  edge that still has pills beyond it.
- **Don't** let a filmstrip wrap or grow past eight tiles; past eight the last tile is a "+N"
  chip into the detail page.
- **Don't** add a fourth band to a dashboard row, and don't move a detail-only fact into one.
- **Don't** let tapping the enlarged scan close the lightbox; the image is inert and the scrim
  and close orb do the closing.
- **Don't** promote grades-ready into a colored pill, a badge, or a sort control. It was tried
  and rejected by the owner; the grade on the scan tile is the whole announcement.
- **Don't** reach for near-black-plus-violet "AI default" surfaces or any themed retro world;
  the dark ground is neutral gray, never blue-gray and never pure black.
</content>
</invoke>
