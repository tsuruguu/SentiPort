/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        dockwise: {
          navy: '#0E2A42',
          steel: '#3A5A78',
          mist: '#E8EEF2',
          panel: 'rgba(255,255,255,0.92)',
          accentGreen: '#5BAE6B',
          accentBlue: '#3D6E96',
          accentRed: '#E0584F',
          accentYellow: '#F2D060',
          highlightPink: '#F6C9C4',
        },
      },
      fontFamily: {
        display: ['"Playfair Display"', 'serif'],
        body: ['"Inter"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

