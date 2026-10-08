import { useCurrentTime } from "../../ui/useCurrentTime";
import { useTheme } from "../../ui/theme/ThemeProvider";
import { Icon } from "../../ui/components/Icon";
import { useAppState } from "../../state/AppState";
import { useState } from "react";
import { router } from "expo-router";
import { View } from "react-native";

import { Row, styles } from "../../ui/components/Layout";
import { Chip, SmallButton } from "../../ui/components/Controls";
import { Copy, Eyebrow } from "../../ui/components/Typography";
import { ListItem } from "../../ui/components/Lists";
import { Page } from "../../ui/components/Page";
export default function Inbox() {
  const {
    plans,
    circles,
    ripples,
    openAvailability,
    rippleReply,
    setRippleReply,
    rsvp,
    settled,
    overlaps,
    overlapResponses,
    respondToOverlap,
  } = useAppState();
  const { theme } = useTheme();
  const now = useCurrentTime();
  const [replying, setReplying] = useState(false);
  const [invitationId] = useState(
    () => (plans.find((p) => p.rsvp !== "In") ?? plans[0])?.id,
  );
  const invitation = plans.find((p) => p.id === invitationId);
  return (
    <Page title="Inbox">
      <View style={{ marginTop: 6 }}>
        <Eyebrow>Answer today</Eyebrow>
      </View>
      {invitation && (
        <View style={{ gap: 12, paddingVertical: 16 }}>
          <Eyebrow>RSVP · your invitation</Eyebrow>
          <Copy size={15} bold>
            {invitation.title} — in?
          </Copy>
          <Row
            style={{
              gap: 4,
            }}
          >
            {(["In", "Maybe", "Out"] as const).map((choice) => (
              <View key={choice} style={{ flex: 1 }}>
                <Chip
                  title={choice === "In" ? "In ✓" : choice}
                  active={invitation.rsvp === choice}
                  onPress={() => rsvp(invitation.id, choice)}
                />
              </View>
            ))}
          </Row>
        </View>
      )}
      <View style={{ gap: 12, paddingVertical: 16 }}>
        <Row>
          <View style={{ flex: 1, gap: 4 }}>
            <Eyebrow>Ripple from Sara</Eyebrow>
            <Copy size={15} bold>
              Pottery on Sunday — 2 slots
            </Copy>
            {rippleReply && (
              <Copy size={12} muted>
                You replied: {rippleReply}
              </Copy>
            )}
          </View>
          <SmallButton
            title={replying ? "Done" : rippleReply ? "Edit" : "Reply"}
            onPress={() => setReplying(!replying)}
          />
        </Row>
        {replying && (
          <>
            <Copy size={13} muted>
              A slow morning, a little clay, coffee after.
            </Copy>
            <View style={styles.wrap}>
              {["Up for it", "Maybe", "Another time"].map((reply) => (
                <Chip
                  key={reply}
                  title={reply}
                  active={rippleReply === reply}
                  onPress={() => setRippleReply(reply)}
                />
              ))}
            </View>
          </>
        )}
      </View>
      {ripples.length > 0 && (
        <>
          <Eyebrow>Your ripples</Eyebrow>
          {ripples.map((ripple) => (
            <View
              key={ripple.id}
              style={{
                gap: 4,
                paddingVertical: 16,
                borderBottomWidth: 1,
                borderColor: theme.line,
              }}
            >
              <Copy size={15} style={{ fontWeight: "500" }}>
                {ripple.title}
              </Copy>
              <Copy size={12} muted>
                {circles.find((circle) => circle.id === ripple.circleId)?.name}{" "}
                · {ripple.slot || "Time still open"}
              </Copy>
              <Copy size={12} muted>
                {new Date(ripple.closesAt).getTime() > now
                  ? `No replies yet · closes in ${Math.ceil((new Date(ripple.closesAt).getTime() - now) / 3600000)} hours`
                  : "Closed"}
              </Copy>
            </View>
          ))}
        </>
      )}
      {openAvailability &&
        new Date(openAvailability.expiresAt).getTime() > now && (
          <ListItem
            open
            title="You’re Open"
            detail={`${openAvailability.interests.join(" · ")} · ${openAvailability.slot}`}
            icon="open"
            onPress={() => router.push("/go-open")}
          />
        )}
      <View style={{ marginTop: 8, gap: 6 }}>
        <Eyebrow>Overlaps · examples</Eyebrow>
        <Copy size={12} muted>
          Shared interests, a little time in common.
        </Copy>
      </View>
      <View>
        {overlaps.map((overlap) => {
          const response = overlapResponses[overlap.id];
          return (
            <View
              key={overlap.id}
              style={{
                gap: 12,
                paddingVertical: 18,
                borderBottomWidth: 1,
                borderColor: theme.line,
              }}
            >
              <Row style={{ alignItems: "flex-start" }}>
                <Icon name="sparkles" size={22} color={theme.accent} />
                <View style={{ flex: 1, gap: 4 }}>
                  <Copy size={15} style={{ fontWeight: "500" }}>
                    {overlap.title}
                  </Copy>
                  <Copy size={12} muted>
                    {overlap.slot} · {overlap.distance}
                  </Copy>
                </View>
              </Row>
              {response ? (
                <Row style={{ paddingLeft: 34 }}>
                  <Copy size={12} muted style={{ flex: 1 }}>
                    {response === "hi"
                      ? "Hi sent · waiting for a mutual hello"
                      : "Passed · quietly"}
                  </Copy>
                  <SmallButton
                    title="Undo"
                    ghost
                    onPress={() => respondToOverlap(overlap.id, null)}
                  />
                </Row>
              ) : (
                <Row style={{ paddingLeft: 34, gap: 8 }}>
                  <SmallButton
                    title="Say hi"
                    onPress={() => respondToOverlap(overlap.id, "hi")}
                  />
                  <SmallButton
                    title="Pass"
                    ghost
                    onPress={() => respondToOverlap(overlap.id, "passed")}
                  />
                </Row>
              )}
            </View>
          );
        })}
      </View>
      <Copy size={12} muted>
        A private Hello opens when you both say hi.
      </Copy>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Plan invitations</Eyebrow>
      </View>
      {plans.map((plan) => (
        <ListItem
          key={plan.id}
          open
          title={plan.title}
          detail={`${plan.people.length} people · ${plan.rsvp === "In" ? "You’re in" : plan.rsvp}`}
          icon={plan.icon}
          onPress={() =>
            router.push({ pathname: "/plan/[id]", params: { id: plan.id } })
          }
        />
      ))}
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Money</Eyebrow>
      </View>
      <ListItem
        open
        title={
          settled.length
            ? "Your latest balance is settled"
            : "Court + coffee · ₹180 each"
        }
        detail="See your balances across plans"
        icon="money"
        onPress={() => router.push("/splits")}
      />
      <Copy size={12} muted style={{ textAlign: "center", marginTop: 8 }}>
        Realtime only on plan day. The rest rides the 9 PM digest.
      </Copy>
    </Page>
  );
}
