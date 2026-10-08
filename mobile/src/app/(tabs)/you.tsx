import { useTheme } from "../../ui/theme/ThemeProvider";
import { useAppState } from "../../state/AppState";
import { router } from "expo-router";
import { View } from "react-native";

import { Copy, Eyebrow } from "../../ui/components/Typography";
import { ListItem } from "../../ui/components/Lists";
import { Page } from "../../ui/components/Page";
export default function You() {
  const { circles, settled } = useAppState();
  const { theme } = useTheme();
  return (
    <Page>
      <View style={{ gap: 20, paddingTop: 16, paddingBottom: 16 }}>
        <View
          style={{
            width: 70,
            height: 70,
            borderRadius: 35,
            backgroundColor: theme.washStrong,
            borderWidth: 1,
            borderColor: theme.washEdge,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Copy size={22} bold color={theme.accent}>
            DG
          </Copy>
        </View>
        <View style={{ gap: 3 }}>
          <Copy size={34} style={{ fontWeight: "500", letterSpacing: -1.35 }}>
            Divya
          </Copy>
          <Copy size={12} muted>
            {circles
              .filter((c) => !c.sleeping)
              .map((c) => c.name)
              .slice(0, 2)
              .join(" · ")}
          </Copy>
        </View>
      </View>
      <Eyebrow>Yours</Eyebrow>
      <View>
        <ListItem
          open
          title="Account"
          detail="Sign in · profile · connected devices"
          icon="person"
          onPress={() => router.push("/account")}
        />
        <ListItem
          open
          title="Scrapbook"
          detail="Good times, kept together"
          icon="album"
          onPress={() => router.push("/scrapbook")}
        />
        <ListItem
          open
          title="Your balances"
          detail={
            settled.length
              ? "See your settled and open balances"
              : "Across every plan"
          }
          icon="money"
          onPress={() => router.push("/splits")}
        />
        <ListItem
          open
          title="Safety"
          detail="Your privacy and check-ins"
          icon="lock"
          onPress={() => router.push("/privacy")}
        />
        <ListItem
          open
          title="Appearance & device"
          detail="Theme · local formats · daily digest"
          icon="person"
          onPress={() => router.push("/device")}
        />
        <ListItem
          open
          title="Who sees what"
          detail="Your people, plans and privacy"
          icon="people"
          onPress={() => router.push("/privacy")}
        />
      </View>
    </Page>
  );
}
