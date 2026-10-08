import { View } from "react-native";
import type { Plan } from "../../domain/models";
import { useAppState } from "../../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { formatDate, formatTime } from "../format";
import { Action, Chip, SmallButton } from "../components/Controls";
import { Avatars } from "../components/Avatars";
import { Card, Row, styles } from "../components/Layout";
import { Copy, Eyebrow } from "../components/Typography";
import { RouteMap } from "../route/RouteMap";
import { PinnedPlace } from "./PinnedPlace";

export function Live({
  plan,
  onOpenChat,
}: {
  plan: Plan;
  onOpenChat: () => void;
}) {
  const demo = useAppState();
  const { theme } = useTheme();
  const id = plan.id;
  const circle = demo.circles.find((c) => c.id === plan.circleId);
  const hasArrived = demo.arrived.includes(id);
  const voted = demo.coffeeVotes.includes(id);
  return (
    <>
      <Row>
        <View
          style={{
            backgroundColor: theme.accent,
            borderRadius: 16,
            paddingHorizontal: 12,
            paddingVertical: 6,
          }}
        >
          <Copy size={10} bold color={theme.background}>
            {new Date(plan.startsAt).toDateString() ===
            new Date().toDateString()
              ? "● PLAN DAY"
              : "UPCOMING"}
          </Copy>
        </View>
      </Row>
      <Copy size={31} style={{ fontWeight: "500", letterSpacing: -1 }}>
        {plan.title}
      </Copy>
      <Copy size={13} muted>
        {formatDate(plan.startsAt)} · {formatTime(plan.startsAt)} · {plan.place}
      </Copy>
      <Card color={theme.wash} style={{ borderColor: theme.washEdge }}>
        <Eyebrow>{circle?.name ?? "Your people"} · meeting up</Eyebrow>
        <Copy size={22} style={{ fontWeight: "500", letterSpacing: -0.5 }}>
          {hasArrived ? "You’re here ✓" : `${plan.people.length} people going`}
        </Copy>
        <Avatars people={plan.people} />
        <Action
          title={hasArrived ? "You’re here — see you in a bit" : "I’m here"}
          icon="pin"
          onPress={() => demo.markArrived(id)}
        />
      </Card>
      <Eyebrow>Quick update</Eyebrow>
      <View style={styles.wrap}>
        {["At the meeting point ✓", "5 min late"].map((update) => (
          <Chip
            key={update}
            title={update}
            onPress={() => {
              demo.send(id, update);
              onOpenChat();
            }}
          />
        ))}
      </View>
      {plan.stops?.length ? (
        <>
          <Eyebrow>
            {plan.stops.length > 1 ? "Your route" : "When & where"}
          </Eyebrow>
          <RouteMap stops={plan.stops} />
          {plan.stops.map((stop, index) => (
            <Row key={stop.id} style={{ paddingVertical: 8 }}>
              <Copy size={13} color={theme.accent}>
                {index + 1}
              </Copy>
              <View style={{ flex: 1, gap: 3 }}>
                <Copy size={14}>{stop.place}</Copy>
                {!!stop.address && (
                  <Copy size={11} muted>
                    {stop.address}
                  </Copy>
                )}
                <Copy size={12} muted>
                  {formatDate(stop.startsAt)} · {formatTime(stop.startsAt)}
                </Copy>
              </View>
            </Row>
          ))}
        </>
      ) : (
        <>
          <Eyebrow>Pinned spot</Eyebrow>
          <PinnedPlace place={plan.place} iconSize={20} />
        </>
      )}
      <Card>
        <Eyebrow>Poll · closes at start</Eyebrow>
        <Row>
          <Copy size={15} bold style={{ flex: 1 }}>
            Filter coffee after?
          </Copy>
          <SmallButton
            title={voted ? "Yes · 5 ✓" : "Yes · 4"}
            onPress={() => demo.vote(id)}
          />
        </Row>
      </Card>
      <Eyebrow>Your RSVP</Eyebrow>
      <Row style={{ gap: 4 }}>
        {(["In", "Maybe", "Out"] as const).map((choice) => (
          <View key={choice} style={{ flex: 1 }}>
            <Chip
              title={choice}
              active={plan.rsvp === choice}
              onPress={() => demo.rsvp(id, choice)}
            />
          </View>
        ))}
      </Row>
      <Copy size={12} muted style={{ textAlign: "center" }}>
        Updates post quietly to chat, so latecomers catch up.
      </Copy>
    </>
  );
}
