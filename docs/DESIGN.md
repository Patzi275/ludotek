# Design — Ludotek

The UI is a practical tool: a light, open page where the games are easy to scan. It uses the "Software" design system (light ground, dark tight headings, one electric-blue action color, white rounded cards), adapted to the app. The app is not a marketing page, so the hero diagram, pricing cards and editorial photos from that system are not used.

All of it lives in `ludotek/web/style.css`. Labels below are quoted in English; the French ones come from `fr.json`. Texts come from the translation catalogs (`ludotek/web/i18n/`): layouts must hold in every language, and English labels are often longer than French ones.

## Logo and icons

- `assets/logo.png` is the source: black pixel art on a 6×6 block grid, transparent background.
- It is only ever scaled by **integer factors with nearest-neighbour** (`script/make_icon.py`), so edges stay crisp at every size. Never resample it with smoothing.
- App icons (`assets/ludotek.ico`, `ludotek/web/favicon.png`) put the logo on a **white rounded tile**: the logo takes 6/8 of the side, with a 1/8 margin. The corner radius equals that margin, so the rounding never touches the logo. A 1px `--dp-color-rule` hairline keeps the tile visible on white. This way it reads on dark taskbars, dark Explorer windows and dark browser tabs.
- On dark backgrounds without a tile (the README in GitHub's dark theme), use `assets/logo-dark.png`, the same logo in white.

## Tokens

The `--dp-*` values in `:root` are authoritative. Do not change them locally; derive new values from them instead.

| Token | Value | Use |
| --- | --- | --- |
| `--dp-color-ground` | `#fcfcfd` | Page background (header, facts strip, toolbar) |
| `--dp-color-ground-muted` | `#f3f4f6` | Shared pale field behind the game grid |
| `--dp-color-panel` | `#ffffff` | Cards, dialogs, inputs, secondary buttons, badges |
| `--dp-color-ink` | `#16191f` | Primary text |
| `--dp-color-ink-secondary` | `#454c58` | Supporting text: paths, metadata, labels, hints |
| `--dp-color-rule` | `#dde0e6` | Hairline borders and rules |
| `--dp-color-accent` | `#074ce0` | Actions, selected states, small icons |
| `--dp-color-on-accent` | `#ffffff` | Text on accent |
| `--dp-color-field` | `#16191f` | Dark passages: toast, "server stopped" banner |
| `--dp-color-on-field` / `-secondary` | `#fcfcfd` / `#d0d4dd` | Text on dark field |
| `--dp-typography-body` | `16px` | Reading text (description and notes textareas), leading `1.6` |
| `--dp-typography-interface` | `15px` | Default UI text and controls |
| `--dp-typography-small` | `14px` | Chips, card buttons, lists |
| `--dp-typography-metadata` | `13px` | Card meta, paths, field labels |
| `--dp-typography-label` | `12px` | Badges, chip counts, hints |
| `--dp-spacing-grid-gap` | `24px` | Card grid gap (18px at ≤1050, 14px at ≤760) |
| `--dp-radius-panel` | `12px` | Cards and dialogs |
| `--dp-motion-interaction` / `-easing` | `160ms` / `ease-out` | Every hover/state transition |

Derived app values: `--accent-hover` (`#063fba`), `--radius-control` (8px, buttons and inputs), `--shadow-card` / `--shadow-lift` / `--shadow-modal`, `--warning` (`#a15c07`, duplicate badge dot only), `--danger` (`#b42318`, "Quit" hover only).

## Typography

- **Host Grotesk** for the title, dialog headings, card titles, big figures and disclosure summaries: bold (650–800), tight tracking (−0.015 to −0.05em), compact line-height.
- **Instrument Sans** for everything else: paragraphs, labels, controls.
- Both fonts are **bundled** in `ludotek/web/fonts/` (variable woff2, latin subset, which covers French accents and œ) and served by `server.STATIC`. The app must work offline, so never load them from Google Fonts. Licenses: `OFL-*.txt` next to the files. Titles in other scripts (Japanese, Cyrillic…) fall back to `sans-serif`.
- Labels and metadata are smaller but keep `ink-secondary` contrast (≈8:1 on white). Never lighten text below that.

## Color rules

- **Blue means "act here" or "selected".** Used for: the play/launch button of playable items (`ready`, `exe`), the main button of a dialog, the selected filter chip, a favorite star, the "New" badge, the playing status, focus rings. "Open archive" and "Open" stay as outlined secondary buttons.
- No other accent colors. The only exceptions are two small semantic signals: the amber dot of "Duplicate?" and the red hover of "Quit".
- Placeholder covers use a **quiet tint** per game (hue from the id, 16–22% saturation), with dark initials. Real covers keep their own colors and get no overlay.

## Layout

From top to bottom:

1. **Header** on `ground`: title + version + watched path, then "Settings", "Rescan", "Quit".
2. **Facts strip**: the stats as a ruled strip (hairline top and bottom, vertical rules between figures), not as cards.
3. **Sticky toolbar** on translucent `ground`: search, filter chips, sort, layout switcher.
4. **Library field** on `ground-muted`: the card grid, then the "Recently removed" disclosure.

Every band aligns on the same content width (max 1320px) through `--inline`. Keep it that way for new bands.

## Components

- **Buttons**: modest radius (8px), min height 40px (36px for the cover buttons in the details dialog), Instrument Sans 500/600. Secondary buttons are white and outlined; primary buttons are blue. Hover lifts by 1px and changes the fill; `:active` returns to rest.
- **Layout switcher**: one segmented control with four 16px icon buttons: small grid, medium grid (default), large grid, list. It has `role="group"` and a translated `aria-label`, each button has a translated `title` and `aria-label`, and the selected one is blue with `aria-pressed="true"`, like the chips.
- **Grid sizes**: each size sets `--card-min` (160 / 210 / 280px, smaller below 760px). Initials scale with the cover through `cqi` (the cover is a size container), so proportions hold at every size. The small grid hides descriptions and tightens the card; action labels get an ellipsis instead of overflowing.
- **List rows**: white panel rows (same border, radius and shadow as cards) with a 44px cover thumbnail, title (ellipsis) + meta + badges, status, then star, main action and details. Below 760px the status is hidden; below 480px the actions wrap under the title.
- **Chips** (filters): pill, white and outlined; the selected one is blue with `aria-pressed="true"`.
- **Cards**: white panel, 12px radius, hairline border, soft downward shadow; hover lifts 2px with a deeper shadow. A drop target gets a blue ring.
- **Badges** on covers: small white tiles with a colored dot (blue = playable, ink-secondary = archive, grey = folder/file, amber = duplicate). "New" is solid blue.
- **Favorite star**: white round tile, grey star; blue when on, with `aria-pressed`.
- **Disclosure** ("Recently removed"): native `<details>`, ruled rows, a "+" that rotates 45° when open.
- **Dialogs**: white panel, 12px radius, large soft shadow over a dimmed ink backdrop. Fields have a 13px label above them, white inputs and selects (including the language selector in Settings), and a blue border plus a soft blue ring on focus.
- **Toast and banner**: the dark passages (`field` background, `on-field` text).

## Motion

Only short hover and state transitions using the motion tokens. No entrance animations and nothing that loops. With `prefers-reduced-motion: reduce`, all transitions are removed and hover lifts are cancelled.

## Accessibility

- Visible focus everywhere: a 2px blue outline offset by 2px (`:focus-visible`), plus a ring on inputs.
- Toggle buttons expose their state with `aria-pressed` (chips, star). Dialogs keep `role="dialog"` and `aria-modal`.
- The JS shows and hides elements with the `hidden` attribute. `[hidden]{display:none!important}` makes sure component `display` rules never override it.
- Touch targets are at least 36px, usually 40px.

## Responsive

| Width | Changes |
| --- | --- |
| ≤ 1050px | Gutter 24px, grid gap 18px |
| ≤ 760px | Gutter 16px, gap 14px, smaller title and figures, card widths 130 / 170 / 230px, list status hidden, the details dialog stacks the cover above the info |
| ≤ 480px | Header buttons on one full-width row, facts in 2 columns, small and medium grids in 2 columns, large grid in 1, list actions under the title |

Check renders at 1280, 760 and 380px, in English and French, after any visual change: no horizontal scroll, no console errors, no raw translation key.
