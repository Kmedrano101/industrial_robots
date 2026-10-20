import type { Config } from 'tailwindcss';

/**
 * Design tokens.
 *
 * Every colour the UI uses is a CSS variable declared in index.css, in an
 * RGB-triplet form so Tailwind's opacity modifiers keep working
 * (`bg-surface/80`). Light and dark values live on `:root` and `.dark`,
 * which means a component writes `bg-surface text-ink border-line` once
 * and never `bg-white dark:bg-gray-900 ...` pairs — the 57 ad-hoc colour
 * utilities the design audit counted collapse into this palette.
 *
 * Semantic, not descriptive: `ok/warn/danger` are reserved for operating
 * conditions (see lib/status.ts); `accent` is the single interactive hue.
 */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: v('c-bg'),           // app background
        surface: v('c-surface'), // cards, bars
        surface2: v('c-surface2'), // inset areas, segmented controls
        line: v('c-line'),       // borders / dividers
        ink: v('c-ink'),         // primary text
        muted: v('c-muted'),     // secondary text, labels
        faint: v('c-faint'),     // tertiary text, disabled
        accent: v('c-accent'),
        'accent-fg': v('c-accent-fg'),
        ok: v('c-ok'),
        warn: v('c-warn'),
        danger: v('c-danger'),
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
      },
      boxShadow: {
        card: '0 1px 2px rgb(0 0 0 / 0.06), 0 1px 1px rgb(0 0 0 / 0.04)',
        float: '0 8px 24px rgb(0 0 0 / 0.25)',
      },
      minHeight: {
        touch: '44px',
      },
      minWidth: {
        touch: '44px',
      },
    },
  },
  plugins: [],
};

export default config;
