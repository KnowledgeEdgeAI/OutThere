import type { ReactNode, ComponentProps } from "react";
import { Text, StyleSheet, type TextStyle } from "react-native";
import { useTheme } from "../theme/ThemeProvider";

export function Copy({
  children,
  size = 15,
  bold = false,
  muted = false,
  color,
  style,
  ...props
}: {
  children: ReactNode;
  size?: number;
  bold?: boolean;
  muted?: boolean;
  color?: string;
  style?: ComponentProps<typeof Text>["style"];
} & Omit<ComponentProps<typeof Text>, "children" | "style">) {
  const { theme } = useTheme();
  const flat = StyleSheet.flatten(style) as TextStyle | undefined;
  const weight = flat?.fontWeight ?? (bold ? "600" : "400");
  const fontFamily =
    Number(weight) >= 600 || weight === "bold"
      ? "DM Sans SemiBold"
      : Number(weight) >= 500
        ? "DM Sans Medium"
        : "DM Sans";
  return (
    <Text
      {...props}
      style={[
        {
          color: color ?? (muted ? theme.muted : theme.text),
          fontSize: size,
          lineHeight: size * 1.4,
          fontFamily: "DM Sans",
          fontWeight: bold ? "600" : "400",
        },
        style,
        { fontFamily, fontWeight: "normal" },
      ]}
    >
      {children}
    </Text>
  );
}
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <Copy size={10} muted bold style={{ letterSpacing: 1.4 }}>
      {typeof children === "string" ? children.toUpperCase() : children}
    </Copy>
  );
}
