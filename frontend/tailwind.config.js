/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          950: '#0B0F17',
          900: '#0F1420',
          850: '#121826',
          800: '#161C2C',
          700: '#1D2436',
          600: '#262E42',
          500: '#3A4358',
        },
        ink: {
          100: '#EDEFF5',
          300: '#C4CADA',
          500: '#8892A6',
          700: '#5B6478',
        },
        beacon: {
          400: '#F0B457',
          500: '#E8A33D',
          600: '#C9852A',
          950: '#3A2A10',
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
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        beacon: '0 0 0 1px rgba(232,163,61,0.25), 0 8px 24px -8px rgba(232,163,61,0.25)',
      },
      borderRadius: {
        card: '10px',
      },
    },
  },
  plugins: [],
}
