import { Pressable, View } from "react-native";
import { router } from "expo-router";
import { useAppState } from "../../state/AppState";
import type { Plan } from "../../domain/models";
import { formatTime } from "../format";
import { Copy } from "./Typography";
import { Icon } from "./Icon";
import { useTheme } from "../theme/ThemeProvider";

export function PlanCard({ plan }: { plan: Plan }) {
  const { theme } = useTheme();
  const { circles } = useAppState();
  const date = new Date(plan.startsAt);
  const circle = circles.find((c) => c.id === plan.circleId);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Open ${plan.title}`}
      onPress={() =>
        router.push({ pathname: "/plan/[id]", params: { id: plan.id } })
      }
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        gap: 14,
        paddingVertical: 18,
        borderBottomWidth: 1,
        borderColor: theme.line,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <View
        style={{
          width: 44,
          paddingVertical: 8,
          borderRadius: 12,
          backgroundColor: theme.wash,
          alignItems: "center",
        }}
      >
        <Copy size={9} muted style={{ letterSpacing: 0.8 }}>
          {date
            .toLocaleDateString(undefined, { weekday: "short" })
            .toUpperCase()}
        </Copy>
        <Copy
          size={24}
          color={theme.accent}
          style={{ lineHeight: 29, letterSpacing: -1 }}
        >
          {date.getDate()}
        </Copy>
      </View>
      <View style={{ flex: 1, gap: 5 }}>
        <Copy size={15} style={{ fontWeight: "500" }}>
          {plan.title}
        </Copy>
        <Copy size={12} muted>
          {formatTime(plan.startsAt)} · {plan.place}
          {"\n"}
          {circle?.name ?? "Just you"} · {plan.people.length} people ·{" "}
          {plan.rsvp === "In" ? "Going" : plan.rsvp}
        </Copy>
      </View>
      <Icon name="arrow" size={16} color={theme.muted} />
    </Pressable>
  );
}
