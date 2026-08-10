import { useTheme } from "@/contexts/use-theme"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  // Was reading next-themes' useTheme(), but next-themes' ThemeProvider is
  // never mounted anywhere in this app -- App.tsx wraps with its own custom
  // ThemeProvider (contexts/use-theme.tsx) instead. That made this always
  // resolve to next-themes' unrelated "system" default, completely
  // disconnected from the app's actual light/dark state -- e.g. the app
  // rendered dark (via its own .dark class) while the toast still rendered
  // with (mismatched) light-theme assumptions, or vice versa, producing
  // unreadable text/background combinations. Use the app's real theme state.
  const { isDarkMode } = useTheme()
  const theme: ToasterProps["theme"] = isDarkMode ? "dark" : "light"

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
