import { useTheme } from "../ui/theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { router } from "expo-router";
import { View } from "react-native";

import { Card, Row } from "../ui/components/Layout";
import { Copy, Eyebrow } from "../ui/components/Typography";
import { ListItem } from "../ui/components/Lists";
import { Page } from "../ui/components/Page";
export default function Splits() {
  const { plans, settled } = useAppState();
  const { theme } = useTheme();
  const open = plans.filter((p) => !settled.includes(p.id));
  return (
    <Page back title="Your balances">
      <Row style={{ alignItems: "stretch" }}>
        <Card color={theme.peach} style={{ flex: 1, borderWidth: 0 }}>
          <Eyebrow>Your share</Eyebrow>
          <Copy size={32}>₹{open.length * 180}</Copy>
          <Copy size={12} muted>
            {open.length} open {open.length === 1 ? "plan" : "plans"}
          </Copy>
        </Card>
        <Card color={theme.mintSoft} style={{ flex: 1, borderWidth: 0 }}>
          <Eyebrow>Settled</Eyebrow>
          <Copy size={32}>₹{(plans.length - open.length) * 180}</Copy>
          <Copy size={12} muted>
            {plans.length - open.length} plans
          </Copy>
        </Card>
      </Row>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>By plan</Eyebrow>
      </View>
      {plans.map((plan) => (
        <ListItem
          key={plan.id}
          title={plan.title}
          detail={
            settled.includes(plan.id) ? "All settled" : "₹180 sample share"
          }
          icon="money"
          onPress={() =>
            router.push({
              pathname: "/plan/[id]",
              params: { id: plan.id, roomTab: "Money" },
            })
          }
        />
      ))}
      <Copy size={12} muted style={{ textAlign: "center", marginTop: 8 }}>
        Sample balances only. No payments are made.
      </Copy>
    </Page>
  );
}
