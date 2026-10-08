import { useTheme } from "../ui/theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { router } from "expo-router";
import { View } from "react-native";

import { Card, Row } from "../ui/components/Layout";
import { Copy, Eyebrow } from "../ui/components/Typography";
import { Icon } from "../ui/components/Icon";
import { ListItem } from "../ui/components/Lists";
import { Page } from "../ui/components/Page";
export default function Scrapbook() {
  const { plans } = useAppState();
  const { theme } = useTheme();
  return (
    <Page back title="Scrapbook">
      <Card color={theme.mintSoft} style={{ borderWidth: 0 }}>
        <Copy size={15} bold>
          Good times, kept together
        </Copy>
        <Copy size={12} muted>
          Illustrated sample memories from your plans.
        </Copy>
      </Card>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Pinned</Eyebrow>
      </View>
      <Row style={{ gap: 10 }}>
        {(["sun", "racket", "coffee"] as const).map((icon, i) => (
          <View
            key={icon}
            style={{
              flex: 1,
              aspectRatio: 1,
              borderRadius: 18,
              backgroundColor: [theme.sunSoft, theme.mintSoft, theme.peach][i],
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name={icon} size={30} color={theme.accent} />
          </View>
        ))}
      </Row>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Recent plans</Eyebrow>
      </View>
      {plans.map((plan) => (
        <ListItem
          key={plan.id}
          title={plan.title}
          detail="Open the plan album"
          icon={plan.icon}
          onPress={() =>
            router.push({
              pathname: "/plan/[id]",
              params: { id: plan.id, roomTab: "Album" },
            })
          }
        />
      ))}
    </Page>
  );
}
