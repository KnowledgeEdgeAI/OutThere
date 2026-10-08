import type { ReactNode } from "react";
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Copy } from "./Typography";
import { Icon } from "./Icon";
import { useTheme } from "../theme/ThemeProvider";

export function Page({
  children,
  title,
  subtitle,
  back = false,
  keyboard = false,
}: {
  children?: ReactNode;
  title?: string;
  subtitle?: string;
  back?: boolean;
  keyboard?: boolean;
}) {
  const { theme } = useTheme();
  const content = (
    <ScrollView
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{
        padding: 24,
        gap: 14,
        paddingTop: 12,
        paddingBottom: 130,
        width: "100%",
        maxWidth: 520,
        alignSelf: "center",
      }}
    >
      {back && (
        <Pressable
          onPress={() =>
            router.canGoBack() ? router.back() : router.replace("/")
          }
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={{
            minHeight: 44,
            width: 44,
            borderRadius: 22,
            backgroundColor: theme.glass,
            borderWidth: 1,
            borderColor: theme.glassEdge,
            alignItems: "center",
            justifyContent: "center",
            alignSelf: "flex-start",
          }}
        >
          <Icon name="back" />
        </Pressable>
      )}
      {title && (
        <View style={{ gap: 7 }}>
          <Copy
            size={34}
            style={{ fontWeight: "500", letterSpacing: -1.35, lineHeight: 40 }}
          >
            {title}
          </Copy>
          {subtitle && <Copy muted>{subtitle}</Copy>}
        </View>
      )}
      {children}
    </ScrollView>
  );
  return (
    <SafeAreaView
      edges={["top", "left", "right"]}
      style={{ flex: 1, backgroundColor: theme.background }}
    >
      <PageGlow />
      {keyboard ? (
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={{ flex: 1 }}
        >
          {content}
        </KeyboardAvoidingView>
      ) : (
        content
      )}
    </SafeAreaView>
  );
}
export function PageGlow() {
  const { theme } = useTheme();
  return (
    <View
      pointerEvents="none"
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: "100%",
        height: 340,
      }}
    >
      <Image
        accessible={false}
        source={require("../../../assets/page-glow.png")}
        resizeMode="stretch"
        style={{ width: "100%", height: "100%", tintColor: theme.glow }}
      />
    </View>
  );
}
