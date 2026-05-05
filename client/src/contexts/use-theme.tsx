import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
 
interface ThemeContextType {
  isDarkMode: boolean;
  toggleTheme: () => void;
}
 
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
 
export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
 
interface ThemeProviderProps {
  children: ReactNode;
}
 
export const ThemeProvider = ({ children }: ThemeProviderProps) => {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check if we're in a browser environment
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      if (saved) {
        return saved === 'dark';
      }
      // Default to system preference
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });
 
  useEffect(() => {
    // Apply theme to document
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
   
    // Save to localStorage
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);
 
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };
 
  return (
    <ThemeContext.Provider value={{ isDarkMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};