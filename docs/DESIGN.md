# Design — Ludotek

The UI is a practical tool: a light, open page where the games are easy to scan. It uses the "Software" design system (light ground, dark tight headings, one electric-blue action color, white rounded cards), adapted to the app. The app is not a marketing page, so the hero diagram, pricing cards and editorial photos from that system are not used.

All of it lives in `ludotek/web/style.css`. Texts come from the translation catalogs (`ludotek/web/i18n/`): layouts must hold in every language, and English labels are often longer than French ones.

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

Derived app values: `--accent-hover` (`#063fba`), `--radius-control` (8px, buttons and inputs), `--shadow-card` / `--shadow-lift` / `--shadow-modal`, `--warning` (`#a15c07`, duplicate badge dot only), `--danger` (`#b42318`, "Quitter" hover only).

## Typography

- **Host Grotesk** for the title, dialog headings, card titles, big figures and disclosure summaries: bold (650–800), tight tracking (−0.015 to −0.05em), compact line-height.
- **Instrument Sans** for everything else: paragraphs, labels, controls.
- Both fonts are **bundled** in `ludotek/web/fonts/` (variable woff2, latin subset, which covers French accents and œ) and served by `server.STATIC`. The app must work offline, so never load them from Google Fonts. Licenses: `OFL-*.txt` next to the files. Titles in other scripts (Japanese, Cyrillic…) fall back to `sans-serif`.
- Labels and metadata are smaller but keep `ink-secondary` contrast (≈8:1 on white). Never lighten text below that.

## Color rules

- **Blue means "act here" or "selected".** Used for: the play/launch button of playable items (`ready`, `exe`), the main button of a dialog, the selected filter chip, a favorite star, the "Nouveau" badge, the playing status, focus rings. "Ouvrir l'archive" and "Ouvrir" stay as outlined secondary buttons.
- No other accent colors. The only exceptions are two small semantic signals: the amber dot of "Doublon ?" and the red hover of "Quitter".
- Placeholder covers use a **quiet tint** per game (hue from the id, 16–22% saturation), with dark initials. Real covers keep their own colors and get no overlay.

## Layout

From top to bottom:

1. **Header** on `ground`: title + watched path, then "Réglages", "Rescanner", "Quitter".
2. **Facts strip**: the stats as a ruled strip (hairline top and bottom, vertical rules between figures), not as cards.
3. **Sticky toolbar** on translucent `ground`: search, filter chips, sort.
4. **Library field** on `ground-muted`: the card grid, then the "Disparus récemment" disclosure.

Every band aligns on the same content width (max 1320px) through `--inline`. Keep it that way for new bands.

## Components

- **Buttons**: modest radius (8px), min height 40px (36px for the cover buttons in the details dialog), Instrument Sans 500/600. Secondary buttons are white and outlined; primary buttons are blue. Hover lifts by 1px and changes the fill; `:active` returns to rest.
- **Chips** (filters): pill, white and outlined; the selected one is blue with `aria-pressed="true"`.
- **Cards**: white panel, 12px radius, hairline border, soft downward shadow; hover lifts 2px with a deeper shadow. A drop target gets a blue ring.
- **Badges** on covers: small white tiles with a colored dot (blue = playable, ink-secondary = archive, grey = folder/file, amber = duplicate). "Nouveau" is solid blue.
- **Favorite star**: white round tile, grey star; blue when on, with `aria-pressed`.
- **Disclosure** ("Disparus récemment"): native `<details>`, ruled rows, a "+" that rotates 45° when open.
- **Dialogs**: white panel, 12px radius, large soft shadow over a dimmed ink backdrop. Fields have a 13px label above them, white inputs, and a blue border plus a soft blue ring on focus.
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
| ≤ 760px | Gutter 16px, gap 14px, smaller title and figures, the details dialog stacks the cover above the info |
| ≤ 480px | Header buttons on one full-width row, facts in 2 columns, grid in 2 columns, smaller initials |

Check renders at 1280, 760 and 380px, in English and French, after any visual change: no horizontal scroll, no console errors, no raw translation key.
