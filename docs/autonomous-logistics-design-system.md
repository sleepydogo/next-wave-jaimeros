# Autonomous Logistics AI — Design System

## Visual direction

- Modern B2B operational-tech aesthetic: minimal, high-contrast, and grid-driven.
- White surfaces alternate with near-black sections for product, analytics, and operational data.
- Bright blue is reserved for actions, active states, icons, charts, and emphasis.
- Base presentation canvas: `1920 × 1080` (16:9).

## Color tokens

Values sampled from the rendered Canva design.

```css
:root {
  --color-ink: #231F20;
  --color-ink-soft: #333333;
  --color-white: #FFFFFF;
  --color-surface-muted: #F5F5F5;

  --color-primary: #0077FC;
  --color-primary-300: #67ACFC;
  --color-primary-200: #B2D6FF;
  --color-primary-100: #E5F1FE;

  --color-border: #E8E8E8;
  --color-text-muted: #6B6B6B;
  --color-text-on-dark: #FFFFFF;
}
```

### Usage

- Primary background: `#FFFFFF`
- Dark dashboard / product section: `#231F20`
- Dark card: `#333333`
- Neutral card: `#F5F5F5`
- CTA, active icon, chart highlight and link: `#0077FC`
- Chart scale: `#E5F1FE` → `#B2D6FF` → `#67ACFC` → `#0077FC`

The hero uses a photographic blur rather than a flat exported gradient. Use this frontend approximation:

```css
.hero-glow {
  background:
    radial-gradient(48% 85% at 38% -18%, #173483 0%, transparent 68%),
    radial-gradient(40% 72% at 88% -8%, #14C8C9 0%, transparent 70%),
    #FFFFFF;
}
```

## Typography

Canva did not expose the original font family through MCP. The visual match is a clean neo-grotesque sans.

```css
:root {
  --font-display: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --font-ui: "Helvetica Neue", Helvetica, Arial, sans-serif;
}
```

For a web-font substitute, use `Manrope` (preferred) or `Inter`.

```css
.display {
  font-family: var(--font-display);
  font-size: clamp(3rem, 6.5vw, 7.5rem);
  font-weight: 500;
  line-height: 0.95;
  letter-spacing: -0.055em;
}

.h1 {
  font-size: clamp(2.25rem, 4.2vw, 5rem);
  font-weight: 500;
  line-height: 1.02;
  letter-spacing: -0.045em;
}

.h2 {
  font-size: clamp(1.25rem, 2vw, 2.5rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.035em;
}

.body {
  font-size: 1rem;
  font-weight: 500;
  line-height: 1.45;
}

.meta {
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
}
```

## Layout

- Base horizontal margin: `100px` on a 1920px canvas (about `5.2vw`).
- Header starts about `60px` from the top.
- Footer lives about `70–90px` from the bottom.
- Three-column content grid with `24–32px` gaps.
- Card corner radius: `24–32px`.
- Card padding: `32–40px`.
- Suggested web container: max `1440px`.

```css
.page-shell {
  width: min(100%, 1440px);
  margin-inline: auto;
  padding-inline: clamp(24px, 5.2vw, 100px);
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.card {
  border-radius: 24px;
  padding: 32px;
}
```

## Components

### Header

- Small blue isotipo + black wordmark on the left.
- Compact circular blue action on the right.
- Minimal border treatment; use whitespace instead.

### Buttons

```css
.button-primary {
  background: var(--color-primary);
  color: var(--color-white);
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  font: 700 0.875rem/1 var(--font-ui);
}

.button-secondary {
  background: transparent;
  color: var(--color-ink);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 12px 18px;
}
```

### Cards and data visualization

- Use `#333333` cards on dark sections.
- Use blue, dark, and muted-gray cards for grouped problem statements.
- Use rounded bars and the four blue tones for charts.
- Use thin outline icons; Lucide with `strokeWidth={1.75}` or `2` matches the deck.

## Accessibility and usage rules

- Prefer `#231F20` for small text on light backgrounds.
- `#0077FC` is suited to actions, links, icons and large white type; validate contrast before using it for small text on white.
- Do not rely on color alone for status; pair it with labels and icons.
- Preserve generous whitespace. Avoid heavy shadows, dense borders, and always-on gradients.
- Use people photography only in human/team/closing contexts. Product interfaces should favor maps, event states, timelines, and operational data.
