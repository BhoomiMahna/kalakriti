/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Primary brand ramp — muted, natural sage green (not neon, not too dark).
        brand: {
          50: "#F4F6EF",
          100: "#E6ECDA",
          200: "#CCD9B9",
          300: "#ABBE8E",
          400: "#8AA267",
          500: "#647F45", // primary (white text passes contrast)
          600: "#51683A",
          700: "#43552F", // deep sage — headings / secondary-button text
          800: "#394829",
          900: "#303C25",
        },
        // Supporting handcrafted-marketplace neutrals.
        khaki: "#A9A778",
        cream: "#F5F2E9",
        ivory: "#FCFAF3",
        beige: "#E6E0D2",
        earth: "#8A7B5C",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
