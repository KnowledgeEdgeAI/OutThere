import { createContext, useContext, type ReactNode } from "react";
import { useColorScheme } from "react-native";
import { usePathname } from "expo-router";
import { useAppState } from "../../state/AppState";
import { moodForPath, themeForMood, type Theme } from "./tokens";

const ThemeContext = createContext<{ theme: Theme; isDark: boolean } | null>(
  null,
);

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const { appearance } = useAppState();
  const scheme = useColorScheme();
  const path = usePathname();
  const isDark =
    appearance === "Dark" || (appearance === "System" && scheme === "dark");
  return (
    <ThemeContext.Provider
      value={{ theme: themeForMood(isDark, moodForPath(path)), isDark }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeOverride({
  theme,
  children,
}: {
  theme: Theme;
  children: ReactNode;
}) {
  const { isDark } = useTheme();
  return (
    <ThemeContext.Provider value={{ theme, isDark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("AppThemeProvider is missing");
  return value;
}
