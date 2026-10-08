import type { ReactNode } from "react";
import { View, StyleSheet, type ViewStyle } from "react-native";
import { useTheme } from "../theme/ThemeProvider";

export function Row({
  children,
  style,
}: {
  children: ReactNode;
  style?: ViewStyle;
}) {
  return (
    <View
      style={[{ flexDirection: "row", alignItems: "center", gap: 12 }, style]}
    >
      {children}
    </View>
  );
}
export function Card({
  children,
  color,
  style,
}: {
  children: ReactNode;
  color?: string;
  style?: ViewStyle;
}) {
  const { theme } = useTheme();
  return (
    <View
      style={[
        {
          padding: 18,
          borderRadius: 22,
          gap: 12,
          backgroundColor: color ?? theme.surface,
          borderColor: theme.line,
          borderWidth: 1,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}
export const styles = StyleSheet.create({
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
