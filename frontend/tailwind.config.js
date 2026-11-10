/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        schnell: {
          primary: "#075D6B",
          secondary: "#0D7780",
          accent: "#18A6A0",
          bg: "#F4F7F9",
          card: "#FFFFFF",
          text: "#173042",
          muted: "#718096",
        },
      },
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          '"Inter"',
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(23, 48, 66, 0.06), 0 1px 2px -1px rgba(23, 48, 66, 0.04)",
        elevated: "0 10px 25px -5px rgba(7, 93, 107, 0.12), 0 4px 10px -4px rgba(23, 48, 66, 0.06)",
      },
    },
  },
  plugins: [],
};

