import { plansForCircle } from "../../domain/plans";
import { useTheme } from "../../ui/theme/ThemeProvider";
import { useAppState } from "../../state/AppState";
import { router } from "expo-router";
import { Pressable, View } from "react-native";

import { Copy, Eyebrow } from "../../ui/components/Typography";
import { Icon } from "../../ui/components/Icon";
import { Page } from "../../ui/components/Page";
import { Row } from "../../ui/components/Layout";
import { SmallButton } from "../../ui/components/Controls";
export default function Circles() {
  const { circles, plans, wake } = useAppState();
  const { theme } = useTheme();
  const active = circles.filter((c) => !c.sleeping);
  const count = new Set(active.flatMap((c) => c.people)).size;
  return (
    <Page>
      <Row style={{ justifyContent: "space-between", marginTop: 10 }}>
        <Copy size={34} style={{ fontWeight: "500", letterSpacing: -1.35 }}>
          Circles
        </Copy>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="New circle"
          onPress={() => router.push("/new-circle")}
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
          <Icon name="add" />
        </Pressable>
      </Row>
      <View
        style={{
          paddingVertical: 20,
          borderBottomWidth: 1,
          borderColor: theme.line,
        }}
      >
        <View style={{ flex: 1, gap: 4 }}>
          <Eyebrow>Your circles</Eyebrow>
          <View
            accessible
            accessibilityLabel={`${active.length} active circles, ${count} people`}
          >
            <Row style={{ gap: 20 }}>
              <Row style={{ gap: 6 }}>
                <Copy size={20} bold>
                  {active.length}
                </Copy>
                <Icon name="active" size={20} color={theme.accent} />
              </Row>
              <Row style={{ gap: 6 }}>
                <Copy size={20} bold>
                  {count}
                </Copy>
                <Icon name="person" size={20} color={theme.muted} />
              </Row>
            </Row>
          </View>
        </View>
      </View>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Active</Eyebrow>
      </View>
      <View>
        {active.map((circle, i) => {
          const next = plansForCircle(plans, circle.id)[0];
          return (
            <Pressable
              key={circle.id}
              accessibilityRole="button"
              onPress={() =>
                router.push({
                  pathname: "/circle/[id]",
                  params: { id: circle.id },
                })
              }
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                gap: 14,
                minHeight: 82,
                paddingVertical: 19,
                borderBottomWidth: 1,
                borderColor: theme.line,
                opacity: pressed ? 0.7 : 1,
              })}
            >
              <View
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 14,
                  backgroundColor: [
                    theme.peach,
                    theme.lilacSoft,
                    theme.mintSoft,
                  ][i % 3],
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Copy size={12} bold>
                  {circle.id === "flat"
                    ? "402"
                    : circle.name
                        .split(" ")
                        .map((w) => w[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase()}
                </Copy>
              </View>
              <View style={{ flex: 1, gap: 3 }}>
                <Copy size={15} style={{ fontWeight: "500" }}>
                  {circle.name}
                </Copy>
                <Copy size={12} muted>
                  {circle.people.length} people ·{" "}
                  {next ? next.title : "quiet this week"}
                </Copy>
              </View>
              <Icon name="arrow" size={16} color={theme.muted} />
            </Pressable>
          );
        })}
      </View>
      {circles.some((c) => c.sleeping) && (
        <View style={{ marginTop: 8 }}>
          <Eyebrow>Sleeping</Eyebrow>
        </View>
      )}
      <View>
        {circles
          .filter((c) => c.sleeping)
          .map((circle) => (
            <View
              key={circle.id}
              style={{
                borderColor: theme.line,
                borderBottomWidth: 1,
                paddingVertical: 19,
                minHeight: 82,
              }}
            >
              <Row style={{ gap: 14 }}>
                <View
                  style={{
                    width: 42,
                    height: 42,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon name={circle.icon} color={theme.muted} />
                </View>
                <View style={{ flex: 1, gap: 3 }}>
                  <Copy size={15} style={{ fontWeight: "500" }}>
                    {circle.name}
                  </Copy>
                  <Copy size={12} muted>
                    {circle.people.length} people · taking a breather
                  </Copy>
                </View>
                <SmallButton
                  title="Wake"
                  ghost
                  onPress={() => wake(circle.id)}
                />
              </Row>
            </View>
          ))}
      </View>
      <Copy size={12} muted style={{ textAlign: "center", marginTop: 6 }}>
        Circles stay small: 3–15 people, invite-only.
      </Copy>
    </Page>
  );
}
