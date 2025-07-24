/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./static/**/*.{js,jsx,ts,tsx,html}",
    "./templates/**/*.html",        // אם רלוונטי
    "./static/global.css"
  ],
  
    theme: {
      extend: {
        colors: {
          background: 'var(--background)',
          foreground: 'var(--foreground)',
          card: 'var(--card)',
          'card-foreground': 'var(--card-foreground)',
          popover: 'var(--popover)',
          'popover-foreground': 'var(--popover-foreground)',
          primary: 'var(--primary)',
          'primary-foreground': 'var(--primary-foreground)',
          secondary: 'var(--secondary)',
          'secondary-foreground': 'var(--secondary-foreground)',
          muted: 'var(--muted)',
          'muted-foreground': 'var(--muted-foreground)',
          accent: 'var(--accent)',
          'accent-foreground': 'var(--accent-foreground)',
          destructive: 'var(--destructive)',
          'destructive-foreground': 'var(--destructive-foreground)',
          border: 'var(--border)',
          input: 'var(--input)',
          ring: 'var(--ring)',
          chart: {
            1: 'var(--chart-1)',
            2: 'var(--chart-2)',
            3: 'var(--chart-3)',
            4: 'var(--chart-4)',
            5: 'var(--chart-5)',
          },
          sidebar: 'var(--sidebar)',
          'sidebar-foreground': 'var(--sidebar-foreground)',
          'sidebar-primary': 'var(--sidebar-primary)',
          'sidebar-primary-foreground': 'var(--sidebar-primary-foreground)',
          'sidebar-accent': 'var(--sidebar-accent)',
          'sidebar-accent-foreground': 'var(--sidebar-accent-foreground)',
          'sidebar-border': 'var(--sidebar-border)',
          'sidebar-ring': 'var(--sidebar-ring)',
        },
        fontFamily: {
          sans: 'var(--font-sans)',
          serif: 'var(--font-serif)',
          mono: 'var(--font-mono)',
        },
        borderRadius: {
          lg: 'var(--radius)',
          md: 'calc(var(--radius) - 2px)',
          sm: 'calc(var(--radius) - 4px)',
          xl: 'calc(var(--radius) + 4px)',
        },
        boxShadow: {
          '2xs': 'var(--shadow-2xs)',
          xs: 'var(--shadow-xs)',
          sm: 'var(--shadow-sm)',
          DEFAULT: 'var(--shadow)',
          md: 'var(--shadow-md)',
          lg: 'var(--shadow-lg)',
          xl: 'var(--shadow-xl)',
          '2xl': 'var(--shadow-2xl)',
        },
      },
    },
    plugins: [],
  } 