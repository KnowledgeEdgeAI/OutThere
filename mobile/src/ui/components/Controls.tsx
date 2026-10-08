import { Pressable, TextInput, type TextInputProps } from "react-native";
import { Copy } from "./Typography";
import { Row } from "./Layout";
import { Icon, type IconName } from "./Icon";
import { useTheme } from "../theme/ThemeProvider";

export function Action({
  title,
  onPress,
  icon = "arrow",
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  icon?: IconName;
  disabled?: boolean;
}) {
  const { theme } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        {
          padding: 17,
          borderRadius: 18,
          backgroundColor: theme.accent,
          opacity: disabled ? 0.4 : pressed ? 0.75 : 1,
        },
      ]}
    >
      <Row style={{ justifyContent: "center" }}>
        <Copy color={theme.background} bold>
          {title}
        </Copy>
        <Icon name={icon} color={theme.background} />
      </Row>
    </Pressable>
  );
}
export function Chip({
  title,
  active = false,
  onPress,
}: {
  title: string;
  active?: boolean;
  onPress: () => void;
}) {
  const { theme } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: 44,
        alignItems: "center",
        justifyContent: "center",
        paddingHorizontal: 14,
        paddingVertical: 10,
        borderRadius: 22,
        backgroundColor: active ? theme.text : theme.soft,
        borderWidth: 1,
        borderColor: theme.line,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Copy size={13} bold color={active ? theme.background : theme.text}>
        {title}
      </Copy>
    </Pressable>
  );
}
export function Field(props: TextInputProps) {
  const { theme } = useTheme();
  return (
    <TextInput
      placeholderTextColor={theme.muted}
      {...props}
      style={[
        {
          backgroundColor: theme.surface,
          color: theme.text,
          padding: 17,
          borderRadius: 18,
          borderWidth: 1,
          borderColor: theme.line,
          fontSize: 16,
          fontFamily: "DM Sans",
          minHeight: 55,
        },
        props.style,
      ]}
    />
  );
}
export function SmallButton({
  title,
  onPress,
  ghost = false,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  ghost?: boolean;
  disabled?: boolean;
}) {
  const { theme } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: 44,
        paddingHorizontal: 16,
        borderRadius: 14,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: ghost ? "transparent" : theme.accent,
        borderWidth: ghost ? 1 : 0,
        borderColor: theme.line,
        opacity: disabled ? 0.45 : pressed ? 0.7 : 1,
      })}
    >
      <Copy size={13} bold color={ghost ? theme.text : theme.background}>
        {title}
      </Copy>
    </Pressable>
  );
}
