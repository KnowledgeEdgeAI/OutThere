import type { ReactNode } from "react";
import { Pressable, View } from "react-native";
import { Copy } from "./Typography";
import { Row } from "./Layout";
import { Icon, type IconName } from "./Icon";
import { useTheme } from "../theme/ThemeProvider";

export function SectionHeading({
  title,
  detail,
}: {
  title: string;
  detail?: string;
}) {
  const { theme } = useTheme();
  return (
    <Row
      style={{
        justifyContent: "space-between",
        paddingBottom: 12,
        borderBottomWidth: 1,
        borderColor: theme.line,
        marginTop: 12,
      }}
    >
      <Copy size={15} bold>
        {title}
      </Copy>
      {detail && (
        <Copy size={11} muted>
          {detail}
        </Copy>
      )}
    </Row>
  );
}
export function ListItem({
  title,
  detail,
  icon,
  onPress,
  color,
  trailing,
  open = false,
}: {
  title: string;
  detail?: string;
  icon?: IconName;
  onPress: () => void;
  color?: string;
  trailing?: ReactNode;
  open?: boolean;
}) {
  const { theme } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        gap: 14,
        minHeight: open ? 76 : undefined,
        paddingVertical: open ? 18 : 16,
        paddingHorizontal: open ? 0 : 16,
        borderRadius: open ? 0 : 18,
        borderWidth: open ? 0 : 1,
        borderBottomWidth: 1,
        borderColor: theme.line,
        backgroundColor: open ? "transparent" : (color ?? theme.surface),
        opacity: pressed ? 0.7 : 1,
      })}
    >
      {icon && (
        <View
          style={{
            width: open ? 24 : 32,
            height: 32,
            borderRadius: 16,
            backgroundColor: open ? "transparent" : theme.washStrong,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon
            name={icon}
            size={open ? 22 : 18}
            color={open ? theme.muted : theme.accent}
          />
        </View>
      )}
      <View style={{ flex: 1, gap: 3 }}>
        <Copy
          size={open ? 15 : 14}
          bold={!open}
          style={open ? { fontWeight: "500" } : undefined}
        >
          {title}
        </Copy>
        {detail && (
          <Copy size={12} muted>
            {detail}
          </Copy>
        )}
      </View>
      {trailing ?? <Icon name="arrow" size={16} color={theme.muted} />}
    </Pressable>
  );
}
