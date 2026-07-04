/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html", // Sesuaikan jika folder template Flask Anda bernama lain
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0a192f',
          800: '#112240',
          700: '#233554',
        },
        teks: {
          utama: '#ccd6f6',
          terang: '#e6f1ff',
          aksen: '#64ffda',
        }
      },
      fontFamily: {
        'body': ['Poppins', 'sans-serif'],
      }
    }
  },
  plugins: [],
}
