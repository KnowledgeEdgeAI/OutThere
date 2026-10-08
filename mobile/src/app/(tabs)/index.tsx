import { agendaForDay } from "../../domain/plans";
import { useTheme } from "../../ui/theme/ThemeProvider";
import { useAppState } from "../../state/AppState";
import { router } from "expo-router";
import { Linking, Pressable, View } from "react-native";

import { Avatars } from "../../ui/components/Avatars";
import { Card, Row } from "../../ui/components/Layout";
import { Copy, Eyebrow } from "../../ui/components/Typography";
import { Icon } from "../../ui/components/Icon";
import { Page } from "../../ui/components/Page";
import { PlanCard } from "../../ui/components/PlanCard";
import { SectionHeading } from "../../ui/components/Lists";
import { SmallButton } from "../../ui/components/Controls";
import { formatTime } from "../../ui/format";
export default function Tonight() {
  const { plans, arrived, markArrived, rippleReply } = useAppState();
  const { theme } = useTheme();
  const today = new Date();
  const { live, next } = agendaForDay(plans, today);
  return (
    <Page>
      <Row style={{ justifyContent: "space-between" }}>
        <Eyebrow>
          {today.toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </Eyebrow>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Your profile"
          onPress={() => router.push("/you")}
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            backgroundColor: theme.glass,
            borderWidth: 1,
            borderColor: theme.glassEdge,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Copy size={11} bold>
            DG
          </Copy>
        </Pressable>
      </Row>
      <Row
        style={{
          justifyContent: "space-between",
          alignItems: "flex-end",
          marginTop: 8,
          flexWrap: "wrap",
          gap: 4,
        }}
      >
        <Copy
          size={37}
          style={{ fontWeight: "500", letterSpacing: -1.6, lineHeight: 43 }}
        >
          Your plans
        </Copy>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push("/new-plan")}
          style={{ minHeight: 44, justifyContent: "center" }}
        >
          <Copy size={12} color={theme.accent}>
            ＋ Make a plan
          </Copy>
        </Pressable>
      </Row>
      <SectionHeading title="Today" detail="Indiranagar" />
      {live ? (
        <Card
          color={theme.wash}
          style={{ padding: 20, borderColor: theme.washEdge, gap: 8 }}
        >
          <Row style={{ gap: 7 }}>
            <View
              style={{
                width: 6,
                height: 6,
                borderRadius: 3,
                backgroundColor: theme.positive,
              }}
            />
            <Copy size={10} color={theme.positive}>
              {new Date(live.startsAt) <= today
                ? "Happening now"
                : "Later today"}{" "}
              · {formatTime(live.startsAt)}
            </Copy>
          </Row>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Open ${live.title}`}
            onPress={() =>
              router.push({ pathname: "/plan/[id]", params: { id: live.id } })
            }
          >
            <Copy
              size={27}
              style={{ fontWeight: "500", letterSpacing: -0.8, marginTop: 4 }}
            >
              {live.title}
            </Copy>
          </Pressable>
          <Copy size={13} muted>
            {live.place}
          </Copy>
          <View style={{ marginTop: 8 }}>
            <Avatars people={live.people} />
          </View>
          <Row style={{ marginTop: 12, gap: 10 }}>
            <View style={{ flex: 1 }}>
              <SmallButton
                title={arrived.includes(live.id) ? "You’re here ✓" : "I’m here"}
                onPress={() => markArrived(live.id)}
              />
            </View>
            <View style={{ flex: 1 }}>
              <SmallButton
                title="Directions ↗"
                ghost
                onPress={() =>
                  Linking.openURL(
                    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(live.place)}`,
                  )
                }
              />
            </View>
          </Row>
        </Card>
      ) : (
        <Copy size={13} muted style={{ paddingVertical: 16 }}>
          A little room in your day. Make a plan with your people.
        </Copy>
      )}
      <View>
        <SectionHeading
          title="Up next"
          detail={`${next.length} ${next.length === 1 ? "plan" : "plans"}`}
        />
        {next.map((plan) => (
          <PlanCard key={plan.id} plan={plan} />
        ))}
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/inbox")}
      >
        <Row style={{ paddingVertical: 16, gap: 14 }}>
          <Copy size={25} color={theme.accent}>
            {rippleReply ? "01" : "02"}
          </Copy>
          <View style={{ flex: 1, gap: 4 }}>
            <Copy size={13} style={{ fontWeight: "500" }}>
              {rippleReply
                ? "One thing waiting on you"
                : "A couple of things need you"}
            </Copy>
            <Copy size={12} muted>
              {rippleReply ? "Plan RSVP" : "Plan RSVP · Sara’s ripple"}
            </Copy>
          </View>
          <Icon name="arrow" size={16} color={theme.muted} />
        </Row>
      </Pressable>
      <Copy size={12} muted>
        The rest can wait for your 9 PM digest.
      </Copy>
    </Page>
  );
}
