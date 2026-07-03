/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // AlignX 品牌色 — 深绿主色
        deepGreen: {
          DEFAULT: "#0F2A24",
          light: "#173a32",
        },
        // AlignX 品牌色 — 琥珀金强调色
        amberGold: {
          DEFAULT: "#C6A86E",
          light: "#D9C299",
        },
      },
    },
  },
  plugins: [],
};
