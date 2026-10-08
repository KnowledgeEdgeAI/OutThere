import { useTheme } from "../ui/theme/ThemeProvider";
import { router } from "expo-router";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Copy } from "../ui/components/Typography";
import { Icon } from "../ui/components/Icon";
import { Row } from "../ui/components/Layout";
import { SmallButton } from "../ui/components/Controls";
export default function Create() {
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const close = () =>
    router.canGoBack() ? router.back() : router.replace("/");
  return (
    <View
      style={{
        flex: 1,
        justifyContent: "flex-end",
        backgroundColor: "rgba(20,26,26,.3)",
      }}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Close create menu"
        onPress={close}
        style={{ position: "absolute", inset: 0 }}
      />
      <View
        style={{
          marginHorizontal: 10,
          marginBottom: Math.max(insets.bottom, 12),
          borderRadius: 28,
          padding: 20,
          gap: 16,
          backgroundColor: theme.glass,
          borderWidth: 1,
          borderColor: theme.glassEdge,
        }}
      >
        <View
          style={{
            width: 36,
            height: 4,
            borderRadius: 2,
            backgroundColor: theme.line,
            alignSelf: "center",
            marginBottom: 4,
          }}
        />
        {[
          {
            title: "New plan",
            detail: "What · when · who — in one screen",
            icon: "add" as const,
            route: "/new-plan" as const,
            color: theme.peach,
          },
          {
            title: "Toss a ripple",
            detail: "The soft ask — a feeling and a slot",
            icon: "ripple" as const,
            route: "/new-ripple" as const,
            color: theme.lilacSoft,
          },
          {
            title: "Go Open",
            detail: "Free soon? Let nearby plans find you",
            icon: "open" as const,
            route: "/go-open" as const,
            color: theme.sunSoft,
          },
          {
            title: "New circle",
            detail: "Your people — invite-only, 3 to 15",
            icon: "people" as const,
            route: "/new-circle" as const,
            color: theme.mintSoft,
          },
        ].map((item) => (
          <Pressable
            key={item.title}
            accessibilityRole="button"
            onPress={() => router.replace(item.route)}
          >
            <Row style={{ minHeight: 60 }}>
              <View
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 16,
                  backgroundColor: item.color,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon name={item.icon} />
              </View>
              <View style={{ flex: 1, gap: 4 }}>
                <Copy size={16} bold>
                  {item.title}
                </Copy>
                <Copy size={12} muted>
                  {item.detail}
                </Copy>
              </View>
            </Row>
          </Pressable>
        ))}
        <SmallButton title="Cancel" ghost onPress={close} />
      </View>
    </View>
  );
}
