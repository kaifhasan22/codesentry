/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          950: 'rgb(var(--base-950) / <alpha-value>)',
          900: 'rgb(var(--base-900) / <alpha-value>)',
          850: 'rgb(var(--base-850) / <alpha-value>)',
          800: 'rgb(var(--base-800) / <alpha-value>)',
          700: 'rgb(var(--base-700) / <alpha-value>)',
          600: 'rgb(var(--base-600) / <alpha-value>)',
          500: 'rgb(var(--base-500) / <alpha-value>)',
        },
        ink: {
          100: 'rgb(var(--ink-100) / <alpha-value>)',
          300: 'rgb(var(--ink-300) / <alpha-value>)',
          500: 'rgb(var(--ink-500) / <alpha-value>)',
          700: 'rgb(var(--ink-700) / <alpha-value>)',
        },
        beacon: {
          400: 'rgb(var(--beacon-400) / <alpha-value>)',
          500: 'rgb(var(--beacon-500) / <alpha-value>)',
          600: 'rgb(var(--beacon-600) / <alpha-value>)',
          950: 'rgb(var(--beacon-950) / <alpha-value>)',
        },
        severity: {
          critical: '#E5484D',
          high: '#F2994A',
          medium: '#EAC54F',
          low: '#4FB4DE',
          info: '#8892A6',
        },
      },
      fontFamily: {
        display: ['"IBM Plex Mono"', 'monospace'],
        sans: ['"IBM Plex Mono"', 'monospace'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        beacon: '0 0 0 1px rgba(224,43,43,0.25), 0 8px 24px -8px rgba(224,43,43,0.22)',
      },
      borderRadius: {
        card: '4px',
      },
    },
  },
  plugins: [],
}
