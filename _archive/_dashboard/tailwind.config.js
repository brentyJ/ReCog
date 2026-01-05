/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        
        // ====================================================================
        // RECOG THEME - Extended Palette
        // ====================================================================
        
        // Orange Palette - Cognitive Operations
        'orange-light': '#ff9955',
        'orange-mid': '#d97e4a',
        'orange-dark': '#a55d35',
        
        // Blue Palette - Structural Data
        'blue-light': '#8aa4d6',
        'blue-mid': '#6b8cce',
        'blue-dark': '#4a6fa5',
        'blue-muted': '#5879b0',
        
        // Tether States
        'tether-active': '#5fb3a1',
        'tether-pending': '#f39c12',
        'tether-inactive': '#718096',
        'tether-error': '#e74c3c',
        
        // Processing State
        'processing': '#d97e9b',
        
        // Special Effects
        'cyan-bright': '#00ffff',
        'magenta-bright': '#ff00ff',
        
        // Background Layers (for direct use)
        'bg-void': '#080a0e',
        'bg-surface': '#0c1018',
        'bg-tertiary': '#111620',
        'bg-elevated': '#161c28',
      },
      
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace'],
      },
      
      // Custom box shadows for glows
      boxShadow: {
        'glow-orange': '0 0 8px rgba(255, 153, 85, 0.4)',
        'glow-orange-lg': '0 0 12px rgba(255, 153, 85, 0.4)',
        'glow-blue': '0 0 8px rgba(107, 140, 206, 0.3)',
        'glow-blue-lg': '0 0 12px rgba(107, 140, 206, 0.3)',
        'glow-teal': '0 0 8px rgba(95, 179, 161, 0.4)',
        'glow-magenta': '0 0 8px rgba(217, 126, 155, 0.4)',
        'glow-cyan': '0 0 12px rgba(0, 255, 255, 0.4)',
      },
      
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "processing-pulse": {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
        "tether-pulse": {
          '0%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.05)' },
          '100%': { opacity: '0.4', transform: 'scale(1)' },
        },
      },
      
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "processing-pulse": "processing-pulse 2s ease-in-out infinite",
        "tether-pulse": "tether-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
