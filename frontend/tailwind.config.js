/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'navy-900': '#0A0E17',
        'navy-800': '#121A2F',
        'navy-700': '#1B2744',
        'electric-blue': '#00F0FF',
        'neon-purple': '#B026FF',
        'subtle-cyan': '#45F5E4',
      },
      fontFamily: {
        sans: ['Inter', 'Poppins', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-primary': 'linear-gradient(135deg, #00F0FF 0%, #B026FF 100%)',
      }
    },
  },
  plugins: [],
}
