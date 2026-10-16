/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ivory: "#F7F3EA",
        paper: "#FCFAF5",
        charcoal: "#242321",
        "warm-gray": "#6F6A61",
        "deep-olive": "#3F4634",
        "muted-olive": "#59604A",
        sand: "#DED6C8",
        status: {
          success: "#4F6B50",
          "success-bg": "#EDF2EC",
          "success-border": "#C6D8C6",
          warning: "#9A6A32",
          "warning-bg": "#F7EFE4",
          "warning-border": "#E5D2B8",
          danger: "#8B3F3F",
          "danger-bg": "#F7EDED",
          "danger-border": "#E2BDBF",
          neutral: "#6F6A61",
          "neutral-bg": "#EFECE3",
          "neutral-border": "#DED6C8",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        serif: [
          '"Newsreader"',
          '"Source Serif 4"',
          '"Merriweather"',
          "Georgia",
          "serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"IBM Plex Mono"',
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
