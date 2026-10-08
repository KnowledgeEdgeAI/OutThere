import { Live } from "../../ui/plan-room/Live";
import { Chat, ChatComposer } from "../../ui/plan-room/Chat";
import { Album } from "../../ui/plan-room/Album";
import { Money } from "../../ui/plan-room/Money";
import { useTheme, ThemeOverride } from "../../ui/theme/ThemeProvider";
import { useAppState } from "../../state/AppState";
import { useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { themeForMood } from "../../ui/theme/tokens";
import { PlanTabBar, planTabItems, type RoomTab } from "../../ui/navigation";

import { Row } from "../../ui/components/Layout";
import { Copy } from "../../ui/components/Typography";
import { Icon } from "../../ui/components/Icon";
import { Page, PageGlow } from "../../ui/components/Page";
export default function PlanRoom() {
  const { id, roomTab } = useLocalSearchParams<{
    id: string;
    roomTab?: RoomTab;
  }>();
  const demo = useAppState();
  const { isDark } = useTheme();
  const plan = demo.plans.find((p) => p.id === id);
  const [tab, setTab] = useState<RoomTab>(
    roomTab && ["Live", "Chat", "Album", "Money"].includes(roomTab)
      ? roomTab
      : "Live",
  );
  const theme = themeForMood(isDark, planTabItems[tab].mood);
  const scroll = useRef<ScrollView>(null);
  if (!plan) return <Page back title="Plan not found" />;
  return (
    <ThemeOverride theme={theme}>
      <SafeAreaView
        edges={["top", "bottom", "left", "right"]}
        style={{ flex: 1, backgroundColor: theme.background }}
      >
        <PageGlow />
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={{ flex: 1 }}
        >
          <Row style={{ paddingHorizontal: 20, minHeight: 54 }}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Go back"
              onPress={() =>
                router.canGoBack() ? router.back() : router.replace("/")
              }
              style={{
                width: 44,
                height: 44,
                borderRadius: 22,
                backgroundColor: theme.glass,
                borderWidth: 1,
                borderColor: theme.glassEdge,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="back" />
            </Pressable>
            <Copy
              size={17}
              style={{ flex: 1, textAlign: "center", fontWeight: "500" }}
            >
              {plan.title}
            </Copy>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Plan settings"
              onPress={() =>
                router.push({
                  pathname: "/plan/settings",
                  params: { id: plan.id },
                })
              }
              style={{
                width: 44,
                height: 44,
                borderRadius: 22,
                backgroundColor: theme.glass,
                borderWidth: 1,
                borderColor: theme.glassEdge,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="settings" />
            </Pressable>
          </Row>
          <PlanTabBar selected={tab} onSelect={setTab} />
          <ScrollView
            showsVerticalScrollIndicator={false}
            ref={scroll}
            keyboardShouldPersistTaps="handled"
            onContentSizeChange={() => {
              if (tab === "Chat")
                scroll.current?.scrollToEnd({ animated: true });
            }}
            contentContainerStyle={{
              padding: 24,
              paddingBottom: 32,
              gap: 14,
              maxWidth: 520,
              width: "100%",
              alignSelf: "center",
            }}
          >
            {tab === "Live" && (
              <Live plan={plan} onOpenChat={() => setTab("Chat")} />
            )}
            {tab === "Chat" && <Chat plan={plan} />}
            {tab === "Album" && <Album />}
            {tab === "Money" && <Money planId={id} />}
          </ScrollView>
          <ChatComposer planId={id} active={tab === "Chat"} />
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ThemeOverride>
  );
}
