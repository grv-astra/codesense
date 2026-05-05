module.exports = {
  theme: {
    extend: {
      colors: {
        // Your custom brand colors
        brand: {
          red: '#bf0000',
          dark: '#2d2d2d', 
          light: '#e5e5e5',
          white: '#ffffff',
        },
        // Alternative approach - override default colors
        primary: {
          DEFAULT: '#bf0000',
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
          950: '#bf0000', // Your exact red
        },
        // For backgrounds and surfaces
        surface: {
          DEFAULT: '#2d2d2d',
          light: '#e5e5e5',
          dark: '#1a1a1a', // Even darker variant if needed
        },
        // Text colors
        text: {
          primary: '#ffffff',
          secondary: '#e5e5e5',
          muted: '#a3a3a3',
        }
      },
      // You can also extend other theme properties
      backgroundColor: {
        'brand-red': '#bf0000',
        'brand-dark': '#2d2d2d',
        'brand-light': '#e5e5e5',
      },
      textColor: {
        'brand-red': '#bf0000',
        'brand-dark': '#2d2d2d', 
        'brand-light': '#e5e5e5',
      },
      borderColor: {
        'brand-red': '#bf0000',
        'brand-dark': '#2d2d2d',
        'brand-light': '#e5e5e5',
      },
      
      fontFamily: {
        custom: ['Chakra', 'sans-serif'],
      }
    },
  },
}
