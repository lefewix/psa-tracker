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
  fill-quiet-dark: "#2e2f32"  # --surface3 (T119); --inp stays rgba(255,255,255,.08)
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
  scrim-dark: "rgba(0,0,0,.62)"
  segment-track: "rgba(0,0,0,.045)"
  segment-track-dark: "rgba(255,255,255,.05)"
  segment-on: "#ffffff"
  segment-on-dark: "rgba(255,255,255,.1)"
  grade-red: "#b12b2b"
  grade-red-dark: "#ff8779"
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
    lineHeight: 1.5
    letterSpacing: "normal"
  field-mobile:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
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
    lineHeight: 1.4
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
    fontSize: "11px"
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
    backgroundColor: "{colors.segment-track}"
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
    margin: "0 -9px"
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
  stage-late:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    fontWeight: 650
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

Depth exists in one place only: the chrome. The sticky toolbar and the settings segmented
bar are translucent, blurred, saturated, and **lensed** —
rimmed with a specular catch along the top edge and a falloff along the bottom, so they read
as curved glass rather than as frosted rectangles. Under them, and only visible through them,
sits an ambient ground: two very wide accent-derived radials pooled in the top corners that
give the lens something to refract. Depth otherwise lives in exactly one more
place: the content card — 16px radius, hairline-soft edge, one quiet cast shadow, separated
by gaps rather than rules. Inside a card everything stays flat: scans, values, stage bars
carry no fill, no tint, no shadow of their own. The material story is glass floats and
refracts; cards sit raised on the ground; content inside them does not move.

Character is delivered by motion and precision instead of ornament. Rows settle in on a
short staggered rise (cards only, `--t2`, 6px, 40ms per row off a served `--i` capped at 12; scan tiles fade in as
their image lands instead); a stage bar is knocked to zero and released to its served width **only
when that submission actually advanced since this browser last saw it**, so the one motion the
product exists for means "your cards moved" rather than "a page loaded"; the toolbar earns its
shadow only once content slides underneath it; overlays materialize by fading their scrim, ramping
their blur, and landing from 97%. Nothing else moves. Every transition names one of three
durations (`--t1` .15s state, `--t2` .25s overlays and the settle, `--t3` .55s the bar) and one
of two easings (`--e1` ease-out fades, `--e2` cubic-bezier(.23,1,.32,1) travel), set beside
`--ac` in THEME_VARS; only the loading loops (`sweep`, `pulse`) keep their own curves. (T178) The build ships both a light and a
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
  6% (light) / 11% (dark) into the wider top-right radial. Unset, it follows `PSA_ACCENT`
  (the default steel blue pair stays `#3a6fd8` / `#5b8def`).

### Tertiary
- **Grade Red** (`--grade`): the color of a grade landing. **One place only: the grade line of
  a scan tile.** A red "N grades landed" status pill and a red detail-page badge shipped
  briefly on 2026-08-01 and were removed the next day by owner ruling — see the Reserved Red
  Rule. It is the emotional payoff of the product; its scarcity is why it lands. And only a
  **PSA 10** gets it: at this store a 10 is the norm (603 of 715 graded cards), so painting
  every grade red spent the color on the ordinary. The grade rides in a small filled chip, not
  plain text: a 10 (any wording: "GEM MT 10" reads its last number) takes a 14% Grade Red tint under
  Grade Red ink; every other grade, non-numeric included, one neutral chip with body ink (T204). A tint, never a solid red block: a solid fill would be the badge the
  Reserved Red Rule already rejected. Chip size and its 21px line box never change, so the tier
  reads as a step down in temperature, not in importance.
- **Alert Red** (`--err` / `--holdtx`): form errors, destructive text actions, and the hold
  pill, which names PSA's reason when known ("Financial hold") and says "On hold" otherwise. Same family as Grade Red, distinct token, distinct job.
- **Saved Green** (`--ok`): one use only — the owner tag's underline flashing on a successful
  save. It is confirmation, never decoration, and never a status color anywhere else.

### Neutral
- **Paper White / Graphite** (`--bg`): the sheet, set on `<html>` so overscroll rubber-banding
  always reveals flat ground. Light is the flagship; dark is a neutral gray — never blue-gray,
  never pure black.
  The browser and installed-app chrome take the same ground: two `theme-color` metas keyed
  on `prefers-color-scheme`, matching the scheme the head script actually renders.
  The manifest's `background_color` (install splash) is the store theme's `--bg`; its maskable
  `/icon.svg` is the favicon fan on full-bleed accent, padded inside the safe circle.
- **Ink** (`--txt`): near-black on white, near-white on graphite. All primary text.
- **Muted** (`--m1`): secondary text — metadata, captions, ETA pills, empty states, the
  inactive filter label.
- **Muted Bar** (`--barmuted`): the held and archived stage-bar fill, 2.5 to 3:1 on the track,
  always quieter than the accent bar.
- **Tertiary Gray** (`--tert`): the search glyph and other non-text furniture.
- **Quiet Fill** (`--inp` / `--surface3`): input grounds and the hover pill behind text
  actions. **Skeleton** (`--sk`, `--txt` at 7%): the ground of a loading or dead scan tile. The only filled rectangles in content, and they carry no border.
- **Hairline** (`--hair`): every rule in the system — row separators, image borders, glass
  edges, filmstrip tiles — with `--hairh` as its hover state and `--hair2` as the softer
  variant used in exactly one place, the rule above a settings danger zone.
- **Track** (`--track`): the unfilled portion of the stage capsule.
- **Row Hover** (`--hovrow`): the only tint content ever receives, and only on pointer devices.
- **Glass Rims** (`--rim` / `--rimb`): the top specular catch and the bottom falloff. Both are
  sub-threshold on purpose — felt as curvature, never seen as an outline.
- **Scrim** (`--scrim`): the dim behind the lightbox and the modal sheets. One token, both
  overlays, an overlay never invents its own dim. Light 40% black, dark 62% so it still dims a
  dark ground (T139).

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
detail badge, and the owner rejected both on sight. The news is the grade's own chip under the
scan — a 14% tint, not a filled red banner about it. **Superseded in part, 2026-09-16 (T114):**
grades-ready is no longer a lowercase detail note, it is the stage word itself. The stage line
reads "Grades ready" instead of "Completing" on the dashboard row and the detail page. Still no
pill, no badge, no colour, no sort control.
Red is never a heading color, a hover state, an emphasis device, or an event announcement.
The PSA outage banner (`.hint.warn`, T128) is that alert: a 9% `--holdtx` tint and a 45% border
on the hint card. It says the cause in one plain sentence and links settings.

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
  (`--ok` under an hour, `--holdtx` an hour or more, `--m1` unknown) and one phrase at
  12.5/500 in one grammar, "Updated just now", "Updated 48 min ago", "Not updating since
  9:16 PM"; a live phrase ends on the clock time in plain sight ("Updated 48 min ago · 8:52
  PM", T169), the full date and time in its title. Phones show the short form (the clock
  alone when live, "Not updating" when stale) so the toolbar stays one row, under 360 the dot alone. No marker
  reads "Last update unknown" over submissions, "No sync yet" only on an empty account (T162).
- **Field** (400, 15px, 1.5): inputs, search, and the bare button reset (which sets 15/600).
- **Body** (400, 14px, 1.5): the default reading layer. Metadata lines, stage line, status
  pills, links, owner tags, card names, empty states. The stage name sits here too, at body
  size with the data rung's 650 weight (`.stage b`), the one place the two rungs cross.
  (Lifted from 13/1.45 on 2026-08-08 — owner found the sheet claustrophobic and the text small.)
- **Control** (500, 13px, 16px line box): control labels only — filter pills and the View
  pill. Stays at 13 because the capsule height arithmetic (38px at both
  breakpoints) is stated in the CSS and depends on the 16px line box. A 13px control without
  that arithmetic (the settings buttons, the skip link, the undo toast) leads at 1.4.
- **Caption** (400, 12px, 1.4): subtitles under a title, sync notes, service line, helper text.
  The masthead subtitle alone runs 12.5px — half a pixel is all it needs to stop reading as a
  caption under a 26px title.
- **Micro** (400, 12px, 1.4): the sub-figure line under a value, preview-row secondaries,
  section labels inside the search preview. Merged up from 11.5 (2026-08-08); the caption
  tier is now a single 12px rung.
- **Tag** (500, 11px, 1.0): the search-preview category chip. `line-height: 1` keeps its 3px
  of vertical padding from growing the row.
- **Cert** (monospace, 11px, 1.4): certification numbers on scan tiles. A prelim card falls back
  to the inherited face at 12px because there is no number to align.

### Named Rules
**The Three-Rung Rule.** There are exactly three hierarchy rungs: 26/700 masthead, 17/650
data, 14/400 body. Everything else (13 controls, 12 captions, 11 tags) hangs off the body
rung. A new size does not create a new rung.

**The Optical Tracking Rule.** Tracking is a function of size, never a style: 26px = −0.021em,
24px = −0.020em, 22px = −0.017em, 17px = −0.012em, 14px and below = 0. Nothing in this system
ever tracks positive. When a caption sits inside a tracked value (`.ledval span`), it resets
letter-spacing to normal, because tracking inherits and size does not.

**The Leading Ladder Rule.** Leading is a function of the rung, like tracking, and every rule
that sets a size states it (no `line-height: normal`, and `input`/`button` state theirs so the UA
default never leaks in): display 26/24/22px = 1.15, figure 17px (and the 15px tile value) = 1.3,
body and field 14-16px = 1.5, micro and caption 11-13px = 1.4, tag 11px = 1.0. Every 14px rule
leads at 1.5, the two-line tile name included (min-height 42px). Pixel line boxes are allowed
only where a capsule's height arithmetic depends on them (filter pills and the View pill 16px,
the grade chip 17px). The one documented exception to the size ramp is the 12.5px toolbar
subtitle and sync phrase (`.toolbar .sub`, `.sync`); it leads at the micro 1.4.

**The Px Ramp Rule.** Every size is px on purpose: the capsule arithmetic is stated in px, so
browser text-only zoom is a no-op here while page zoom works. If text-size settings are ever
wanted, the fix is a rem migration of the whole ramp, not a per-rule patch.

**The Accepted Small Text Rule.** These sit under 14px by decision and are not audit findings:
the 13px sort pills, filter chips and settings buttons, the 12px `.estnote` header notes
("PSA estimates · as of"), the "CAD · estimated" sub-figure line, captions, Prelim and
person-page labels, the 11px cert monospace, and the 12.5px phone sync line.

**The Incomplete Total Rule.** Every money total (dashboard row value, sub page value, person
page cost, coverage and value) gets a trailing "+" iff at least one card that should count has
no figure yet (`plus()`), with a `.vh` reason. The person page footnote defines it once.

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
(`16px 14px 88px` under 640px), the bottom carrying `env(safe-area-inset-bottom, 0px)`.
No control floats over the page (T208): the settings gear (store mode only) and the theme
toggle are `.lgout` icon actions in the dashboard toolbar, just before sign-out, and the theme
toggle also sits at the right of the settings header. Theme defaults to the OS and a choice
persists per browser (`psa_theme`); the gate, setup and 404 pages carry no toggle.

Content sits in **raised cards flush with the column**: each submission is a card at
`padding: 18px 16px`, `margin: 0 0 14px` (`16px 14px` / `12px` gap under 640px), 16px
radius, `--hair2` edge and a `0 2px 10px` cast shadow. The gap between cards is the
separator — no hairlines between or around the list, no closing rule. An empty state takes
the same card (`48px 20px` padding, `14px` top margin), never bare text on the ground.
Inside a card, the mobile filmstrip still bleeds to the card's own padding edge
(`-14px`) so the last tile runs off the card edge as the "there is more" cue. At every
width an overflowing strip also carries a 28px `mask-image` fade on whichever edge still has
tiles past it (`.sl` / `.sr`, set by the same FX_JS the filter capsule uses); a strip that
fits is never faded. The strip snaps (`x proximity`), settling a tile on its left edge.

The dashboard masthead is sticky with a negative `top` (FX_JS measures the brand row), so at
every width the brand row scrolls away and only the search field stays pinned (T209). Its
words carry the old 👋 tip: the placeholder is "Type your name to find your cards", and no
hint card sits above the list. Other toolbars stick at `top: 10px` (`z-index: 20`); each is
preceded by a 1px server-rendered sentinel (`.tbsentinel`, so a late app.js shifts nothing, T202) that drives its scroll-edge elevation. A fixed 26px ground band
(`html:has(.toolbar.raised)::before`, `z-index: 19`, the ambient layers sized to the viewport) masks
the gap and the corners above it once the bar is stuck, so no slice of a row shows over the glass; 10px under the
condensed masthead, whose glass already covers the top. The compact search bar on
/cards and /search bleeds 9px each side (padding plus border) so its field lines up with the
h1 and the groups; the glass hangs into the gutter. Scan grids are
`repeat(auto-fill, minmax(152px, 1fr))` with an 18px gutter, tightening to
`minmax(136px, 1fr)` and a 14px gutter under 640px. Scan tiles hold a fixed `1.72 / 2.4`
aspect ratio — a card's proportions — so the grid never reflows as images load.
The grade line is always present on a tile, empty at its 21px line box on an ungraded card,
so graded and ungraded neighbours in one row share a baseline.

Spacing rhythm runs on a coarse 2 / 4 / 7 / 10 / 14 / 18 / 24 ladder: 2px between a title
and its subtitle, 7–10px inside chips, 12–14px between row elements, 18–24px between sections.

**Breakpoints:** 640px, plus a 360px list fallback for the card grid. Under it the page-header `.synced` block goes full width and
left aligned, so its `.estnote` drops the `margin-left: auto` that right-aligns the 34ch measure
on desktop.
Under 360px a one-column tile ran about 600px tall, so not one whole card fit a 320 screen: each
`.gc` becomes a list row (56px scan floated left, grade chip, name, value and owner stacked right,
cert hidden, empty chip collapsed), about 115-128px tall. CSS only, same markup; 360px and up is untouched. (T173)

### Named Rules
**The Current-Stage-Only Rule.** Under 640px only the *current* stage is ever named. The
stage line is one sentence ("Grading · back Oct 18") above the capsule bar; the system never
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

Hybrid, split strictly by role. **Chrome is lensed glass; content is flat.** The toolbar and
the settings segmented bar share one material:
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
**The Glass-Is-Chrome Rule.** `backdrop-filter` appears on the toolbar, the settings segment
bar, and overlay scrims. The sort segment and the solo pills are a plain quiet fill (T209). Never on a content row, a scan tile, or
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
Content sits exactly one card deep: the submission card, the hint, the
gate. Nothing inside a card gets its own card, tint, border box, or shadow — nested cards
are always wrong. Separation inside a card is proximity and gray level.

**The Graceful Degradation Rule.** Every glass surface ships its fallbacks together:
`@supports not (backdrop-filter)` and `prefers-reduced-transparency: reduce` both swap to
`--glasssolid` via `background-color` only (never the shorthand, which would wipe the capsule's
track layer), the reduced-transparency branch drops overlay scrims to an opaque 72% black, and
the ambient ground is killed under reduced transparency, `prefers-contrast: more`, and
`@supports not (color-mix)`. Under `forced-colors: active` the stage bar keeps a CanvasText
outline on a Canvas track and a Highlight fill (`forced-color-adjust: none`).

**The Named-Reduce Rule.** `prefers-reduced-motion: reduce` is a scoped, enumerated block, not
a global transition kill. It removes *travel* — the row settle, the bar run-out, the shimmer,
press-scale, the overlay scale landing and blur ramp, view-transition animations — and keeps
*feedback*: hover tints, focus rings, the toolbar's earned shadow, and a short opacity fade on
every overlay so "this is on top of that" still reads.

## Shapes

Corner language runs from square to circle by role, not by size. Every **single-line control is
a capsule** (999px): text inputs, the search bar, the filled button, the compact save button,
the destructive text button, filter pills, the search-preview tag, and the quiet circular hover
pills. Content-side surfaces stay square-ish on purpose. Submission cards, the empty and hint
cards, and settings blocks are **16px raised cards** (the 2026-08-08 amendment retired the
square ledger); scan tiles are 12px wells. Images take 6px (scans on tiles, covers,
logo chip) and preview thumbnails 4px; a lightbox image takes 12px because it is presented
rather than listed. Preview rows and the quiet hover pill behind a text action take 8px. The
search preview panel and the modal sheet take 14px; the full toolbar takes 16px and the compact
search bar 14px.

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

**The Card Radius Rule.** Rows, list containers, and settings blocks are 16px raised cards;
scan tiles inside them are 12px wells. Nothing content-side goes to a capsule except the
grade chip.

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
- **Press:** `scale(.97)` over `--t1` `--e1`, set element-level because it carries no
  color and therefore cannot leak a fill.
- **Text buttons:** accent-as-text on transparent — "Archive", "View cards", "Undo",
  disclosure links. They carry an invisible padded hit box (`12px 8px` padding cancelled by an
  equal negative margin) so the resting layout is byte-identical to unpadded text. Hover is
  the colour deepen and nothing else — no painted fill (the hit box hangs over the stage bar
  and read as a stray sub-panel inside a card), no underline (tried and disliked; both owner
  calls 2026-08-08).
- **Archive undo chip:** "Archived · Undo" holds 10s, paused while hovered or keyboard focused. On
  touch it leaves the row for the thumb zone: fixed bottom-left, 20px off the edges, 44px,
  13px, a solid detached capsule (`--glasssolid`, hairline, `0 10px 26px` cast) (T144).
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
- **Style:** a plain capsule (999px) holds borderless segments: the faint `--segtrack` fill,
  a transparent 1px border, no glass, no rims (T209).
- **Solo pill (`.fsolo`):** the standalone Archived toggle is its own capsule — it carries the
  same quiet `--segtrack` fill itself rather than riding in a wrapper, because a single pill inside a capsule prints
  a ring around nothing. It reads one rung quieter than the sort pills (12px/500 vs 13px) and
  lands at exactly 38px, the sort capsule's outer height at both breakpoints. It is the
  archived disclosure on all three list pages. The dashboard's untagged count lives in the
  attention line (T150), not a pill.
  Under 640px the Archived label shortens to "Arch." and its side pad drops 14 -> 12px; the
  count always stays.
- **Filter row (`.filterrow`):** sort capsule at one end, the solo pills paired in `.rowend` at
  the other. The row wraps at the same 10px gap, so on a phone the pair drops to a second line
  and the capsule keeps its full width instead of shrinking into a scroller. The person page
  runs the same row over its submission groups, sharing the dashboard's `psa_sort` choice.
- **Sort pills:** Newest, Service, Return. Three, always the same three — a "Grades ready"
  fourth pill shipped briefly and was removed with the rest of the grades promotion
  (2026-08-02 owner ruling). Service sorts by tier fee, priciest first (unpriced last), and
  heads each tier with a `.tierhd` line at 14/650 `--m1`; other sorts drop the headers (T151).
  The active pill ends in a 5px `currentColor` chevron that turns up on reversal (`.rev`); the
  choice rides `?sort=&dir=` and the server renders it. Shipped rows sort last under Return (T152).
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
- **Moved dot (`.card.moved .num`, T191):** the same 6px accent dot after a row's sub number
  when its stage differs from this browser's `psa_stage` map. FX_JS keeps it in localStorage
  (`psa_new`) across reloads until that sub's page is opened; a first-seen sub never gets it,
  reduced motion sees it too. "moved since your last look" rides a `.vh` span. Not a pill.
- **Press:** `scale(.97)`.

### Status Pills
One status line per sub (T205): the ETA, Shipped, Late and Pending pills are gone. The date
rides the stage line ("Grading · back Oct 18", "late, due Aug 22" in `.stage .late`, ink at
650, T117; "ETA pending"), short dates never zero padded ("Oct 3"). A shipped row has no bar:
its stage line is the ship line, "Shipped · Sep 6 · UPS 1Z…", with Archive beside View cards.
The right-hand column of a dashboard row holds the value and, only for a hold, one pill:
- **Hold (`.pill.hold`)**, alert red: the queue has stopped. **The only red in the column** —
  see the Reserved Red Rule for the grades pill that was tried here and removed. The dashboard
  pill stands alone; the detail and person pages carry one muted sentence (`status_note`)
  saying PSA paused it (a code in `HOLD_LABELS`, e.g. a financial hold, names the submitter as
  the one who clears it; card owners are never asked to act), plus "PSA has not issued a new
  estimate." for a past-due date (T147, narrowing the 2026-09-09 ruling). The detail page
  states the alarm in its meta line, a red "On hold" (`b.holdb`) then "PSA ETA paused" (late or
  not) and the old date ("Was Nov 20"), the note sits under the stage bar, and that bar
  (`.dstage.hold`) mutes like the dashboard row's; a held sub printing a live ETA is a bug.
Grades-ready is still not a pill and not a row footer line (the owner, 2026-08-08). Since T114
(2026-09-16) it is not an `.estnote` under the detail badge either: `timeline_html` prints
"Grades ready" as the stage word in place of "Completing" on the dashboard row and the detail
page, and that is the whole treatment.

**The Hold Rule.** A hold never hides the return date: the dashboard row prints the hold pill
and the stage line keeps its date, and the detail badge leads with "On hold" above "Paused" and a muted
"Was <date>" note (T65, T147). The dashboard pill stands alone; the detail and person pages
carry one muted sentence.

Archived rows carry no status pill at all: every archived sub is finished, the foot already
says so, and the extra pill made the column taller than the header and knocked the filmstrip
out of the rows' rhythm.

### Cards / Containers
The row is a **submission card**: `--surface` ground, 16px radius, `--hair2` edge, `0 2px
10px` cast shadow, `18px 16px` padding, 14px gap to the next card. Its only state is a hover
tint (`color-mix` of 4% ink over the surface) on pointer devices. Archived rows keep the full surface and carry
`grayscale(.55)` alone, in every view, lifting to full color on hover: an opacity wash fades the
card's own white and takes the ink under 4.5:1. Archived card tiles (`.gc.arch`, on the sub page,
the person page and search alike) take the same whole-tile `grayscale(.55)`, so chip and value
read past with the scan; only the scan also dims to .5. Hover, or editing the owner tag, lifts
the grey. The only true containers are detached surfaces —
the search preview panel (14px, 6px padding, solid `--surface`) and the modal sheet
(`min(460px, 94vw)`, 14px, `24px 24px 26px`).

**The attention line** (T150) is one `.hint.attn` card above the filter row, `--m1` text, one
line: "1 on hold · 1 past due · 1 graded · 12 untagged". A count of one links its sub, several
stay plain (no filtered view), untagged links `/cards?owner=unassigned`. Zeros drop out; all zero
renders no card. Every signed-in session sees it. No red, no pills.

**Failure reuses the 404 card**: a read that fails (locked or unreadable db) answers 500 with the
same gate box, titled "Something went wrong", never an empty dashboard.

**The gate field rests unfocused** (no autofocus, so no ring until it is tapped or tabbed to);
only the retry after an error lands focused. `.err` reserves its full 18px line box so an error
never grows the card, and a `.gbox` holding an `.err` drops its bottom pad to 14px to give that
empty line back (T169).

**The gate keeps a standing line** under the error rung, a `.setupnote` reading "Ask the store
for the password.", so a visitor who cannot get in is told who to ask before they guess. Lockout
copy names the wait ("paused for 15 minutes"), never "a few minutes".
Sign-out lands on `/?out`, where a `.setupnote` above the field reads "You’re signed out."; the
page then rewrites its URL to `/`, so a reload shows the plain gate.

### Filmstrip (signature)
Every dashboard row carries its own contact sheet: up to eight card fronts (`STRIP_MAX = 8`)
in line order, 84×117px at 6px radius with a hairline and a quiet-fill ground, 10px apart,
12px under the identity band. Past eight, the last tile becomes a **"+N" chip** — same box,
same radius, quiet placeholder ground, muted 14px/600 numeral — linking into the detail page,
so the strip is always one fixed-width run and never wraps. A sub with no imaged cards falls
back to its own cover thumb; with neither, the band is absent entirely rather than reserved.
Strip tiles and the chip carry `tabindex="-1"`: the strip is a preview, "View cards" is the
keyboard route (T158). Detail and person grid tiles stay tabbable.

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
- **Disabled:** `opacity: .5` and the default cursor, nothing else.
- **In flight:** a submit button is never disabled (it would drop its value); 150 ms into the
  POST it takes `.busy` (an opacity pulse, pointer-events none, `aria-busy`) and a second submit
  is dropped. Any same-origin navigation slower than 250 ms shows a 3px `--bar` sweep fixed at
  the top edge (a pulse under reduced motion); `pageshow` clears both. (T198)

### Navigation
Navigation is the sticky glass toolbar: brand/logo and the 26px large title on the left, sync
status and controls on the right, search below. Every inner page (detail, person, unassigned, search, settings) builds its header with one
helper, `page_head` (T206): a top `.foot.footbare` row with "← Back" (`#backlk`, history-aware)
on the left and the page's one action across from it (Archive, Export CSV, the theme toggle on
settings, nothing on search), then an `.hrow` of the h1, one muted meta line, and at most one
figure on the right. On the detail page the meta line carries service, cards and the return
window, or the ship date and tracking, or the hold; the estimated value is the figure; the
stage line and bar follow the header bare (`.dstage`, no card). The person page keeps its
three-figure totals row (T211) as that right slot and has one back link, no Home.
In dark the toolbar logo (30px, 26px on phones) takes `--logotb`, a contrast lift that keeps
the fan's three card planes apart on graphite; light and the 72px gate mark are untouched.
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
  to the opener on close, Escape closes, and Tab is held inside the dialog. The **scan
  itself is inert**: tapping the image does nothing, because the reveal has to survive being
  touched. The scrim and the `.lbx` close orb (44px, fixed dark circle, white glyph, top-right)
  are what close it. While it is open the page is **locked**: `overflow:hidden` on `body`, given
  back on close, plus `overscroll-behavior:contain` on `.lb` so a drag never chains through.
  `main` is `inert` while it is open. One `.lbcap` line under the scan carries name, grade, a
  "Cert N" link to PSA's public cert page (none for a prelim), value and a "3 / 8" counter, read
  from the tile's `data-gr` / `data-cert` / `data-val`; Tab cycles that link and the orb.
  Arrow keys and a sideways swipe page within the same `.grid` or `.strip`, never across. (T157)
- **Disclosures:** the person and customer pages' archived toggles are disclosures and carry
  `aria-expanded` / `aria-controls`; the dashboard's is a VIEW SWITCH (it swaps which rows the
  always-visible list shows) and carries `aria-pressed` instead. All three use the solo-pill
  grammar. The dashboard's archived rows are not in the first paint: the pill fetches them
  from `/?arch=1` the first time it is switched on, and puts itself back to off if that fails.
  Switched on, a `.tierhd` line above the list reads "Archived · N submissions" and `#live`
  says the count; switched off, `#live` says "Showing N submissions". The sub page puts
  Archived on its own `.sub` line under the subtitle.
- **Focus:** the global indicator is a 2px `--ring` outline at 2px offset (inputs at zero). The
  owner tag keeps its quiet accent underline for pointer focus and gets the full ring back on
  `:focus-visible`, because a 1px underline is not a focus indicator on the app's most-used
  control.
- **prefers-contrast: more** raises `--hair`, `--hairh`, `--m1`, and `--tert` per palette,
  emitted in the same three-block shape as the palettes themselves.

### Stage Bar (signature)
The product's signature component: one text line — current stage in accent-as-text at the
650 data weight, then "· back Oct 18" in muted (T205: no "stage N of 8"; shipped drops the
bar and reads the ship line) — above a 4px capsule whose fill transitions
its width over 550ms on `cubic-bezier(.23, 1, .32, 1)`.
Detail pages print "· since Sep 12, 23 days" in place of the ETA, which their meta line holds (days in the current stage, none once shipped),
kept on one line by `.stage span span{white-space:nowrap}`; dashboard rows never carry it (T130).

**An unknown status draws no bar.** A step the stage map does not carry prints "Status
unknown" on the stage line, muted and unbolded, with no capsule under it (`.stage.nobar`
drops the line's bottom margin, so the row keeps the same rhythm as a bar row).

**The person page leads with cards (T211).** Its header figures sit in one `.tots .trow` row,
value, coverage, grading cost; the footnote folds behind a `<details>` "How these are counted".
Under 640px Discord pings rides the name line and the gaps to search and sort tighten, so the
first group starts under 300px at 390.

**Person page groups sit in a two-column grid (T120).** Above 640px the sub groups fill two
equal columns inside `.wrap`, in date order (no dense packing); a group of 3+ cards spans both.
Tiles keep `.grid`'s auto-fill, so a half column runs them 2-up; the status note runs under both
header columns, and the stage bar spans its group as on the dashboard.

**The run-out is earned, not ambient.** Each bar carries `data-k` (its sub number) and
`data-st` (its stage index); FX_JS keeps a `psa_stage` map in `localStorage` and knocks a bar
back to `scaleX(0)` with its transition off (width stays served inline, origin left, so the
run-out never lays out) — releasing it on the same 40ms stagger — **only for a sub whose stage differs from
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
while editing, never on the row's `:focus-within`, which swallowed its own tap. With a mouse
the pencil shows on the tile's hover or focus, sits at half opacity at rest on a filled tag so
the control is findable, and hides while the field is editable (T134).
The "Saved · Undo" or retry chip sits inside the row in the pencil's place, on the tag's
baseline, so a save never changes the tile's height; Enter and Escape hand keyboard focus
back to the tag, not the body (T136).
A save still in flight after 300 ms turns the underline `--m1` (`.saving`) until it
lands; no spinner, no extra row (T201).
On the unassigned worklist, Enter on a filled tag saves and opens the next untagged field for
typing (focus never passes through body), so a run of tags is one keyboard pass; not on touch (T190).
Every tag shares one page-level `<datalist id="owners">` of the names in use, so typing
offers existing people; the picker arrow is hidden in Chrome and Safari (T135).

### Scan Tile (signature)
Each tile is an **inset well**: `--surface3` (opaque `#2e2f32` in dark, one colour on any ground)
under a 1px `--hair`, 12px radius, 10px padding. A grid straight on the page ground (`/sub`, `/search`)
paints the tile `--surface` and its neutral chips `--surface3`, as light `--surface3` is the ground's grey (T119).
Tiles carry **no shadow** — a well inside a raised card is still one card deep, and a second shadow
would make it a nested card. Inside it the image sits in one fixed **380/635 box** — the ratio of a
slabbed PSA scan — under `object-fit: contain` on a transparent ground, so it is **never
cropped**: PSA's `/small/` renditions are not one shape (a slab is 380x635, a raw prelim photo
380x527, and some graded certs still ship a raw-card photo at 380x528), and the old
`1.72/2.4` + `cover` sliced the label off the top and bottom of every slab. A shorter image
centres in the same-height box with the well showing above and below — the well **is** the
letterbox, which is why the box is transparent and why tiles stay uniform whatever PSA sends.
The image keeps its 6px radius but carries **no hairline of its own** (the well already draws the edge; two rules 10px
apart read as a double line). Bare images on the card's own surface at an 18px gap were what
the owner saw on 2026-09-16 — "the page is a bit too flat, and cards get visually muddled" — so the
grid gap dropped to 12px, the track grew by the well's padding to hold the image width, and
`.card` stepped its shadow one notch to `0 4px 14px`. The neutral grade chips moved off
`--surface3` to `--surface` for the same reason: the well wears their old ground. Below the
image: the grade as a small filled chip (13px/500, 1px 7px, fully rounded, a 1px
border) in two tiers (T204) — a 14% Grade Red tint for any 10 behind a 45% Grade Red border, one
neutral `--surface` chip with `--txt` and a `--hairh` border for every other grade — hugging its own text and sitting in a
reserved 21px line box, which an ungraded card still emits empty so a grid row keeps one
baseline — card name
clamped to two lines with a reserved **`min-height`** (40px — never a fixed height, which
clips the second line mid-glyph under text-only zoom), **no set line** (the name carries the
subject; the set is read on the detail header, not scanned in a grid), value at 15/600 in
**`--ac-pale`** — one step below the 17/650 data rung, which a well holding six things could
not afford, and in Accent as Text because the value is the tile's **second reveal** after the
grade: six greys in one well read as a single block (the owner, 2026-09-16: "still too uniform,
needs another color"). It measures 4.84:1 light and 7.16:1 dark on the well; the `CAD` caption
stays `--m1` and the owner tag stays `--txt`, so the accent lands once. Then
the owner tag pinned to the bottom via `margin-top: auto`, with no bottom pad of its own so the
well's 10px matches the 10px above the scan. The chip takes `margin-left: -8px` (pad plus rim), so
its rim hangs into the gutter and its label sits on the name's first glyph (360px and up). (T174) The rhythm between them is tight
by intent: 8px above the chip, 4px above the cert and the value. the owner, 2026-09-16, on the
first pass: "better, but within each card pill it's still a bit much."
**Five things a tile (T207):** scan, grade chip, name, value, owner. The cert number lives in
the lightbox caption (name, grade, cert, value); "Not graded yet" is said once in the sub
header (detail meta, person group meta), never per tile; the owner line is gone on that
owner's own person page; a search tile is the detail tile plus one "Open sub #N" link, no
service line. Tiles
carry **no `content-visibility`** — its paint containment clipped everything that reaches past
the tile box (focus rings, the hover pill's negative-margin bleed), so it was removed; the
off-screen cost it targeted is handled in FX_JS instead, which lands the loading sweep only
when a still-loading tile approaches the viewport. While an image loads, grid or filmstrip, it
sits on `--sk` and carries a 1.15s linear sweep in `--sh2` (a highlight, white in light) after
a .3s delay, and the image fades in over .25s when the loaded class lands. A scan that fails to
load is swapped for the same `.ph` placeholder (on `--sk`, no sweep) a card with no scan renders,
anchor and all, so the grid rhythm holds and the dead tile no longer opens the lightbox; a dead
filmstrip thumb becomes an empty chip-sized box, so the strip keeps its height. (T197)
Fetched lists never read empty: 120 ms into the Archived fetch `#list` gets up to three
`.skcard` rows (number line, meta line, five `.skt` tiles, bar line), and a closed search preview
opens on three `.skrow` rows after 200 ms; an open one dims its stale rows with `.busy`. Skeletons
are `.sk` blocks on `--sk` under the `pulse`, which stays under reduced motion. (T199)
A wait the page already handles leads with `.waitdot`, a 7px `--ac-pale` dot on the same pulse:
"Signing in now" while a PSA code is armed (Send code hides until the field arrives) and the
empty dashboard's first sync, which also reloads itself every 30 s while psa-scan runs. (T202)

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
card variant (`.card.grp`) explicitly refuses the row hover tint: it is a
layout container wearing the row's class, not a row you can act on.

**The One-Emoji Rule.** 🎉 (the all-tagged empty state) is the only emoji in the product; the
👋 hint card retired with T209. No emoji icons, no emoji in headings, no second emoji.

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
  The chip reads "Archived · Undo" and stands in for the row's own button until it goes; the
  row stays grey under the cursor while it is up (`.card.arch:has(.undo):hover`).
- **Do** give a destructive-ish action the same undo grammar the owner tag uses, and announce
  it. Reversibility belongs to the action that is hard to reverse, not the easy one.
- **Do** hand focus to the Undo chip when disabling the pressed button would drop it to body,
  and back to a real control when the chip goes away.
- **Do** put a state-changing control in the `.foot` line of the rows that need it — archiving
  is a dashboard action, not a detail-page pilgrimage.
  The `.est` text takes the free width (`flex:1 1 0`) so the control stays on the ship date's
  line, and `.tlink` never wraps, so a narrow foot breaks between fields, never mid number.
- **Do** validate any env-supplied color against `#[0-9a-fA-F]{6}` before it reaches CSS.
- **Do** clamp every new accent-derived shade server-side against a named ground and a named
  target (4.5:1 for text, 3:1 for bars and focus rings) rather than trusting a tuned share.
- **Do** put white text only on `--ac-fill`, and deepen (never brighten) it on hover.
- **Do** paint focus indicators with `--ring` and the stage bar with `--bar`, never raw `--ac`.
- **Do** emit both the light and dark palettes on every page so the client toggle is instant.
- **Do** separate content with a 1px `--hair` rule and nothing else.
- **Do** give every glass surface both rims (`--rim` top, `--rimb` bottom) plus its cast shadow.
- **Do** keep Liquid Glass on the toolbar and the segmented capsules only.
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
- **Do** press-scale interactive elements (`.97`) — it is the system's tactility.
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
