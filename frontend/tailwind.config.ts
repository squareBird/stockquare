import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      screens: {
        // md/lg/xl defaults match spec breakpoints (768 / 1024 / 1280).
      },
    },
  },
  plugins: [],
};

export default config;
