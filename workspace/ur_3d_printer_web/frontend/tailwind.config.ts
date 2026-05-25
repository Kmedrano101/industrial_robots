import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'print-active': '#22c55e',
        'print-paused': '#eab308',
        'print-error': '#ef4444',
        'print-idle': '#6b7280',
        'print-loading': '#3b82f6',
      },
    },
  },
  plugins: [],
};

export default config;
